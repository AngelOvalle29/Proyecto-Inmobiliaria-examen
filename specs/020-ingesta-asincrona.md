# 020 · Ingesta asíncrona de los documentos del agente

| Campo | Valor |
|---|---|
| **Número** | 020 |
| **Estado** | Implementada (falta la verificación en producción) |
| **Autor** | Douglas (rol A), con acuerdo de C y D |
| **Revisor** | Angel (rol C, dueño de `ia`) y Nathaly (rol D, dueña de la mensajería) |
| **Fecha** | 2026-11-01 |
| **Apps afectadas** | `ia` (modelo, servicios, tareas, API), `config` (rutas de Celery), `scripts/iniciar.sh` (colas del worker) y `frontend/` (`paginas/asistente`) |
| **Rama** | `feature/020-ingesta-asincrona` |
| **Pull request** | — |

---

## 1. Problema

El agente responde con los documentos de la agencia (spec 005), pero hoy solo
se cargan con el comando `cargar_demo_ia`, y la indexación corre dentro de ese
proceso. Una gerente que actualiza la política de comisiones no tiene cómo
subirla, y si se pudiera, la petición esperaría varios segundos a Gemini.

La rúbrica pide al menos un flujo con RabbitMQ **conectado a una acción real
del sistema** (`docs/requisitos.md` §5, 2 puntos). Este es ese flujo: subir o
reemplazar un documento del agente encola su indexación. La API responde de
inmediato, y el worker trocea, pide los vectores a Gemini e indexa.

El rol A toma esta spec para que D se concentre en los reportes y Power BI. Lo
acordaron C y D el 2026-11-01.

## 2. Alcance

**Incluye:**
- **API** para subir, reemplazar, reindexar y desactivar documentos del agente.
- **Tarea de Celery** `ia.indexar_documento`, en la cola `documentos`, con
  reintentos.
- **Estado de la indexación** guardado en el documento, para mostrarlo (no hay
  backend de resultados, `docs/arquitectura.md` §6).
- **El worker consume la cola `documentos`** (`scripts/iniciar.sh`).
- **Pantalla** *Documentos del asistente*: lista con el estado, subir,
  reemplazar, reindexar y desactivar.

**No incluye:**
- **Documentos oficiales del catálogo** (spec 011): son escrituras, contratos y
  licencias con datos personales, que no se envían a la capa gratuita de Gemini
  (`CLAUDE.md` §11). Además son PDF o imágenes, y extraerles el texto pediría
  una dependencia nueva. Ver §10.
- **PDF y otros formatos:** solo Markdown, como la spec 005 (§2).
- **Notificaciones por correo** (cola `notificaciones`): siguen en "solo si sobra
  tiempo" del plan.
- **`cargar_demo_ia`:** sigue indexando en el mismo proceso. Se corre al preparar
  la demo, cuando quizá el worker no está arriba, y así no depende de él.

**Depende de #62**, que crea `DocumentoRAG`, `crear_documento_rag`,
`actualizar_contenido_documento` e `indexar_documento`. Se implementa cuando
se fusione.

## 3. Reglas de negocio

**Subir y reemplazar**

1. **Un documento se sube como archivo Markdown** (`.md`), en UTF-8, de hasta
   **200 KB**, con título, tipo (`TipoDocumentoRAG`) y país opcional. El título
   es único (`DOCUMENTO_RAG_DUPLICADO`, spec 005).
   - 200 KB son unas 50 páginas de texto: sobra para una política, y limita los
     vectores que se piden a Gemini por documento.
   - Un archivo que no es texto UTF-8, o vacío, responde 400
     `ARCHIVO_NO_PERMITIDO`. Es una excepción propia de `ia`
     (`ArchivoRAGNoPermitido`) con el mismo código que la del catálogo: importar
     la de `catalogo` crearía una dependencia `ia → catalogo` que hoy no existe
     (revisión de C en #74).
2. **Reemplazar** sube otro archivo para el mismo documento: si el texto cambió,
   sube la versión (`actualizar_contenido_documento`, spec 005). Si es igual, no
   cambia nada ni se encola.
3. **No se suben datos personales.** Son documentos de la agencia (políticas,
   manuales, requisitos legales, plantillas) que el agente público lee y envía
   a Gemini. La pantalla lo advierte (spec 005, regla 10).

**Indexación por la cola**

4. **Crear o reemplazar deja el documento `PENDIENTE` y encola su indexación**
   después del commit (`transaction.on_commit`). Si se encolara antes, el worker
   podría buscar el documento antes de que exista en la base.
5. **La tarea es una cáscara delgada** (`docs/arquitectura.md` §6): recibe el id
   y llama a `indexar_documento` de la spec 005, sin lógica propia.
6. **Reintentos:** si Gemini no está disponible (`ProveedorIANoDisponible`), la
   tarea reintenta hasta **3 veces** con espera creciente (1, 2 y 4 minutos).
   - El proveedor ya reintenta por su cuenta dentro de cada intento (spec 005,
     regla 9). La espera de la tarea cubre caídas más largas, como una cuota
     agotada por minuto.
7. **Si se agotan los reintentos**, el documento queda en `ERROR` con el motivo,
   y conserva sus fragmentos anteriores, si los tenía (spec 005, regla 7).
   Reindexar lo vuelve a encolar.
8. **Si el texto cambió mientras se indexaba** (`DocumentoModificadoDuranteIndexacion`),
   la tarea termina sin reintentar: el cambio encoló su propia indexación, que
   es la que vale.
9. **Si el documento ya no existe o está desactivado**, la tarea termina sin
   hacer nada.
10. **Un mensaje no se pierde si el worker se reinicia** a mitad de una tarea
    (Render lo reinicia en cada despliegue): la tarea confirma el mensaje al
    terminar (`acks_late`), y RabbitMQ lo vuelve a entregar. Indexar dos veces
    es seguro, porque reemplaza los fragmentos (spec 005, regla 7).

**Estado y lectura**

11. **Estados:** `PENDIENTE` (sin indexar su versión actual), `INDEXADO` y
    `ERROR`. Solo los `INDEXADO` tienen fragmentos de su versión actual. Uno
    `PENDIENTE` o en `ERROR` sigue respondiendo con los fragmentos que tenía.
    - `PENDIENTE` no garantiza que haya un mensaje en la cola: `cargar_demo_ia`
      sin `IA_API_KEY` deja los documentos así, sin encolarlos (revisión de C en
      #74). Por eso reindexar vale en cualquier estado (regla 12).
12. **Reindexar** encola de nuevo el documento, **en cualquier estado**, y lo
    deja `PENDIENTE`. Si ya había un mensaje en la cola, el documento se indexa
    dos veces, y eso es seguro (regla 10). Así un documento nunca queda
    atascado: si no avanza, se reindexa.
13. **Desactivar** saca el documento de las respuestas sin borrar sus fragmentos
    (spec 005, regla 4).

**Permisos**

14. Suben, reemplazan, reindexan y desactivan `ADMINISTRADOR` y `GERENTE`. Los
    mismos roles ven la lista. El público solo usa el agente.

## 4. Modelo de datos

### `ia.DocumentoRAG` (spec 005): dos campos nuevos

| Campo | Tipo | Nota |
|---|---|---|
| `estado_indexacion` | CharField, enum `EstadoIndexacion` | `PENDIENTE`, `INDEXADO`, `ERROR`. Por defecto `PENDIENTE` (regla 11) |
| `error_indexacion` | CharField(255) | Vacío salvo en `ERROR`: el motivo, sin datos del documento |

La migración marca como `INDEXADO` los documentos que ya tienen
`fecha_indexacion`, para que los de la demo no aparezcan pendientes.

`fecha_indexacion` y `version` quedan como están. `docs/modelo-datos.md` se
actualiza en el PR de implementación. Es el `estado_indexacion` que la spec 011
(§4) dejó pospuesto para el RAG.

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| GET, POST | `/api/v1/documentos-agente/` · POST como `multipart/form-data` (`archivo`, `titulo`, `tipo`, `pais`) · filtros `?tipo=`, `?estado_indexacion=`, `?buscar=` (título) | Regla 14 |
| GET, PATCH, DELETE | `/api/v1/documentos-agente/{id}/` · PATCH multipart con `archivo` (regla 2) · DELETE desactiva (regla 13) | Regla 14 |
| POST | `/api/v1/documentos-agente/{id}/reindexar/` → 202 | Regla 14 |

POST responde **201** con el documento en `PENDIENTE`: el documento existe, lo
que falta es indexarlo. Reindexar responde **202 Accepted**: solo encola.

**Ejemplo de respuesta** (`GET /documentos-agente/3/`):

```json
{
  "id": 3,
  "titulo": "Política de comisiones",
  "tipo": "POLITICA",
  "pais": null,
  "version": 2,
  "estado_indexacion": "PENDIENTE",
  "error_indexacion": "",
  "fecha_indexacion": "2026-11-01T16:05:00Z",
  "fragmentos": 6,
  "actualizado_en": "2026-11-01T18:40:12Z"
}
```

`fragmentos` cuenta los que hay en la base, de la última versión indexada. La
lista no incluye el texto completo; el detalle tampoco, porque no hace falta
para ninguna pantalla.

**Errores:** no hay códigos nuevos.
- `DOCUMENTO_RAG_DUPLICADO` (409) ya existe en la spec 005.
- `ARCHIVO_NO_PERMITIDO` (400) usa el mismo código que la spec 011, con una
  excepción propia de `ia` (regla 1). Aquí cubre un archivo que no es Markdown
  UTF-8 o pasa de 200 KB.

## 6. Servicios, selectores y tareas

```python
# ia/services.py  (transaction.atomic y registrar_auditoria)
def subir_documento_rag(*, archivo, titulo, tipo, pais, autor, ip) -> DocumentoRAG
def reemplazar_documento_rag(*, documento, archivo, autor, ip) -> DocumentoRAG
def reindexar_documento_rag(*, documento, autor, ip) -> DocumentoRAG
def desactivar_documento_rag(*, documento, autor, ip) -> None
def marcar_error_indexacion(*, documento_id, motivo) -> None
def encolar_indexacion(*, documento_id) -> None   # transaction.on_commit (regla 4)

# ia/selectors.py
def listar_documentos_rag(*) -> QuerySet[DocumentoRAG]   # con el conteo de fragmentos

# ia/tasks.py
@shared_task(name="ia.indexar_documento", bind=True, acks_late=True,
             reject_on_worker_lost=True, max_retries=3)
def indexar_documento_tarea(self, documento_id: int) -> None
```

- **`ia/exceptions.py`** agrega `ArchivoRAGNoPermitido(ErrorDominio)`, con
  código `ARCHIVO_NO_PERMITIDO` y estado 400 (regla 1).
- **`subir_documento_rag` y `reemplazar_documento_rag`** leen el archivo como
  UTF-8 y llaman a `crear_documento_rag` o `actualizar_contenido_documento` de
  la spec 005, que ya auditan. Después ponen `PENDIENTE` y llaman a
  `encolar_indexacion`.
- **`indexar_documento`** (spec 005) agrega una línea: al guardar los
  fragmentos, deja `INDEXADO` y borra `error_indexacion`.
- **`encolar_indexacion`** importa la tarea dentro de la función. `tasks.py`
  importa `services.py`, así que importarla arriba haría un ciclo.
- **La tarea** hace `retry(countdown=60 * 2**intento)` ante
  `ProveedorIANoDisponible`. Si se agotan los reintentos, llama a
  `marcar_error_indexacion`. Ante `DocumentoModificadoDuranteIndexacion`, o si
  el documento no existe, registra el motivo en el log y termina (reglas 8 y 9).

**Celery** (`config/settings/base.py` y `scripts/iniciar.sh`):
- `CELERY_TASK_ROUTES = {"ia.*": {"queue": "documentos"}}`. La tarea de
  diagnóstico de `core` sigue en la cola por defecto.
- El worker pasa a `celery -A config worker -Q celery,documentos …`. Sin `-Q`,
  solo consume la cola por defecto y las indexaciones se quedarían esperando
  para siempre.

**Frontend** (spec 010):

```
src/api/ia/consultas.ts          useDocumentosAgente(filtros), con refetchInterval
                                 de 5 s mientras algún PENDIENTE se haya modificado
                                 hace menos de 10 minutos (§10)
src/api/ia/mutaciones.ts         subir, reemplazar, reindexar y desactivar
src/paginas/asistente/
  ListaDocumentosAgente.tsx      TablaDatos: título, tipo, país, versión, estado,
                                 fragmentos, fecha de indexación; filtro por estado
  DialogoDocumentoAgente.tsx     subir y reemplazar, con el campo 'archivo' (.md)
menu.ts                          grupo Asistente: "Documentos del asistente"
                                 (admin y gerente)
```

## 7. Auditoría

| Acción | Quién | Valores |
|---|---|---|
| Subir | El usuario | Título, tipo, país y versión (ya lo hace `crear_documento_rag`) |
| Reemplazar | El usuario | Versión anterior y nueva (ya lo hace `actualizar_contenido_documento`) |
| Reindexar | El usuario | `estado_indexacion` anterior y `PENDIENTE` |
| Desactivar | El usuario | `activo` |
| Indexar | `None` (la cola) | Fragmentos antes y después, y la versión (ya lo hace `indexar_documento`) |
| Error de indexación | `None` (la cola) | `estado_indexacion: ERROR` y el motivo |

Así la bitácora registra el inicio del flujo (subir, reemplazar o reindexar) y
su fin (indexar o error), como pide `docs/arquitectura.md` §6. El paso a paso
del worker va al log de Render.

## 8. Criterios de aceptación

- [ ] Subir un `.md` responde 201 en menos de un segundo, con el documento
      `PENDIENTE`; con el worker corriendo, pasa a `INDEXADO` y el agente
      responde con él
- [ ] Con el worker detenido, el documento queda `PENDIENTE`; al arrancarlo, se
      indexa sin volver a subirlo (el mensaje esperó en RabbitMQ)
- [x] Reemplazar con otro texto sube la versión y vuelve a indexar; con el mismo
      texto no cambia nada
- [x] Con Gemini caído (sin `IA_API_KEY`), la tarea reintenta 3 veces y el
      documento queda en `ERROR` con el motivo; reindexar lo recupera
- [x] Un archivo que no es Markdown UTF-8, o de más de 200 KB, responde 400
      `ARCHIVO_NO_PERMITIDO`; un título repetido, 409 `DOCUMENTO_RAG_DUPLICADO`
- [ ] Con `cargar_demo_ia` sin `IA_API_KEY`, los documentos quedan `PENDIENTE`;
      reindexar con la llave puesta los deja `INDEXADO`
- [x] Reindexar un documento `PENDIENTE` lo vuelve a encolar sin error
- [x] Desactivar saca el documento de las respuestas del agente
- [x] `AGENTE`, `CONTABILIDAD` y `CONSULTA` reciben 403 y no ven la entrada del
      menú
- [x] La pantalla actualiza el estado sola mientras haya un `PENDIENTE` reciente,
      y deja de consultar cuando no
- [x] Cada acción queda en la bitácora de auditoría (§7)
- [ ] En producción, el log de Render muestra la tarea `ia.indexar_documento`
      recibida en la cola `documentos` y terminada
- [x] `pytest`, `ruff`, `npm run lint`, `npm run typecheck` y `npm run build`
      pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Servicio | Subir deja `PENDIENTE` y encola después del commit (`django_capture_on_commit_callbacks`); si la transacción falla, no encola |
| Servicio | Reemplazar con el mismo texto no encola |
| Tarea | Éxito: llama a `indexar_documento` y el documento queda `INDEXADO` |
| Tarea | `ProveedorIANoDisponible`: reintenta; al agotar los reintentos queda `ERROR` con el motivo y conserva los fragmentos |
| Tarea | `DocumentoModificadoDuranteIndexacion` y documento inexistente: termina sin reintentar |
| Servicio | Reindexar un `PENDIENTE` lo vuelve a encolar |
| API | 201 al subir, 400 por archivo, 409 duplicado, 202 al reindexar en cualquier estado, 403 por rol |
| Manual | Cada criterio de §8, en local (RabbitMQ de `docker compose` y `celery -A config worker -Q celery,documentos` en otra terminal) y en producción |

Las pruebas usan el proveedor falso de la spec 005 y nunca llaman a Gemini.
`CELERY_TASK_ALWAYS_EAGER` (`config/settings/test.py`) ejecuta la tarea en el
mismo proceso.

## 10. Decisiones y alternativas descartadas

- **Documentos del agente y no documentos oficiales.** El plan inicial
  (`docs/requisitos.md` §5) hablaba de "al subir un documento oficial". Se
  descarta por dos razones: los oficiales llevan datos personales (nombres,
  números de documento, montos de una venta) que no pueden ir a la capa
  gratuita de Gemini, y son PDF o fotos escaneadas, cuyo texto pediría una
  dependencia y, en las fotos, reconocimiento de texto. Los documentos del
  agente son Markdown de la agencia, pensados para el RAG.
- **El estado en el modelo y no en un backend de resultados.** Celery puede
  guardar el resultado de cada tarea, pero eso pide Redis, que se dejó fuera
  (`docs/arquitectura.md` §6). La pantalla necesita saber si el documento está
  indexado, no qué devolvió la tarea, y eso vive mejor en el documento.
- **`transaction.on_commit` y no encolar dentro de la transacción.** Si la
  transacción se revierte, no queda un mensaje huérfano; y el worker nunca lee
  un documento que todavía no existe.
- **`acks_late`.** Por defecto Celery confirma el mensaje al recibirlo; si el
  worker se reinicia a mitad de la tarea, el mensaje se pierde y el documento
  queda `PENDIENTE` para siempre. Con `acks_late` se confirma al terminar.
  Repetir es seguro, porque indexar reemplaza los fragmentos.
- **Consultar cada 5 segundos mientras haya un pendiente reciente.** Lo más
  simple que muestra el flujo sin WebSockets. Una indexación tarda segundos, y
  con los reintentos, unos 7 minutos como máximo (regla 6). Un pendiente de
  hace más de 10 minutos ya no va a cambiar solo: la pantalla deja de consultar,
  y quien lo vea lo reindexa. Sin ese límite, un documento atascado haría
  consultar a la pantalla para siempre (revisión de C en #74).
- **Reindexar en cualquier estado, sin un error `INDEXACION_EN_CURSO`.** Se
  pensó en rechazar reindexar un pendiente para no encolar dos veces. Pero el
  estado no garantiza que haya un mensaje en la cola (regla 11), y un rechazo
  dejaría el documento sin salida. Indexar dos veces es seguro (regla 10).
- **Archivo `.md` y no un campo de texto.** "Subir un documento" es la acción
  que describe el plan, y reutiliza el campo `'archivo'` de `FormularioDatos`
  (spec 014).
- **Cuotas.** Cada subida es un mensaje en CloudAMQP (cuota de 1 millón al mes)
  y una llamada de embeddings por lote a Gemini. El límite de 200 KB acota los
  vectores por documento.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-01 (Claude Code, rol A).** El agente midió el avance contra la
rúbrica y señaló que la mensajería (2 puntos) no tenía ningún flujo. Propuso
que A la tomara, por haber montado Celery y el worker en la spec 002, y C y D
lo confirmaron. Para el borrador, el agente revisó:
- la spec 005 y el código de #62 (`indexar_documento`, la versión y la
  detección de cambios durante la indexación);
- `docs/arquitectura.md` §6 y la issue #25;
- `scripts/iniciar.sh`, donde vio que el worker solo consume la cola por
  defecto;
- la configuración de Celery en `config/settings`.

Las razones para no usar los documentos oficiales (§10) son una propuesta del
agente, a validar en la revisión.

**Revisión de C (Angel) en #74**, dos cambios aplicados:
1. Un documento podía quedar `PENDIENTE` para siempre, si `cargar_demo_ia` corre
   sin `IA_API_KEY`. Reindexar vale ahora en cualquier estado (regla 12), y la
   pantalla deja de consultar después de 10 minutos (§10). De las dos opciones
   que propuso C se eligió esta, porque no toca `cargar_demo_ia` y sirve para
   cualquier pendiente atascado, no solo el del demo.
2. `ARCHIVO_NO_PERMITIDO` con una excepción propia de `ia` (regla 1), sin
   importar `catalogo`.

**Implementación (2026-11-02, Claude Code, rol A)**, en tres commits:
1. Campos y migración, servicios, la tarea, las rutas de Celery y las colas del
   worker, con 19 pruebas.
2. La API, con 13 pruebas.
3. La pantalla *Documentos del asistente* y su entrada de menú.

Ajustes durante la implementación:
- **`TipoDocumentoRAG` y `EstadoIndexacion` en `ENUM_NAME_OVERRIDES`:** el
  tipo salía en el esquema como `Tipo8e7Enum`. De paso, el esquema bajó de 2
  avisos a 1 (el que queda es de `compras`).
- **`crear_documento_rag` y `actualizar_contenido_documento` reciben `ip`**,
  opcional, para que la subida desde la API la audite (`CLAUDE.md` §8).
- **`EmbeddingConDimensionIncorrecta` deja el documento en `ERROR` sin
  reintentar:** es un error de configuración, y reintentar daría lo mismo.
- **Las pruebas de la API usan un cliente que ejecuta los `on_commit` al
  terminar cada petición**: la transacción de la prueba nunca se confirma, y
  sin eso no se vería qué se encoló.

**Verificación local**, con RabbitMQ de `docker compose` y un worker con
`-Q celery,documentos`, sin `IA_API_KEY`:
- la API responde 201 con el documento `PENDIENTE`; el worker recibe la tarea en
  la cola `documentos` y programa el reintento a 60 s;
- un documento desactivado se omite en el reintento siguiente;
- en la pantalla: el aviso "Indexando en la cola…" y la consulta cada 5 s, el
  error con su motivo, reindexar, desactivar con confirmación, y `CONSULTA` sin
  la entrada ni la página.

Quedan para producción, con la llave, los criterios del paso a `INDEXADO` y del
log de Render. El del worker detenido no se probó.

**Plan de implementación** (después de #62):
1. Campos y migración; servicios, tarea, rutas de Celery y cola del worker;
   pruebas.
2. API y sus pruebas.
3. Pantalla y menú; verificación de §8 en local y en producción.
