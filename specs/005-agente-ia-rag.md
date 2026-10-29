# 005 · Agente de IA: proveedor, RAG y consulta pública con citas

| Campo | Valor |
|---|---|
| **Número** | 005 |
| **Estado** | En revisión |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `ia` (incluido su comando `cargar_demo_ia`), `config/settings` (variables de IA y límite de peticiones) |
| **Rama** | `feature/005-agente-ia-rag` |
| **Pull request** | — |

---

## 1. Problema

Quien visita el sitio de la agencia tiene preguntas que hoy solo responde un
agente de ventas: qué documentos necesita para comprar en su país, cómo es el
proceso de compra, qué políticas tiene la agencia sobre reservas o descuentos.
La agencia ya tiene esa información escrita en manuales y políticas, pero nadie
la consulta fuera de horario.

Esta spec crea un agente que responde esas preguntas **usando solo los
documentos de la agencia** y que **siempre dice de qué documento y sección sacó
la respuesta**. Si los documentos no contienen la respuesta, lo dice en lugar de
inventarla.

Cubre los requisitos 2 (agente de IA) y 3 (RAG con citación) de
`docs/requisitos.md`, que juntos valen 2 puntos. Es el modo público del plan de
una semana (`docs/roadmap.md`).

## 2. Alcance

**Incluye:**
- Interfaz `ProveedorIA` e implementación de Gemini, según `docs/arquitectura.md` §7
- Modelos `DocumentoRAG` y `FragmentoRAG`, con embeddings en pgvector
- Servicio de indexación: troceo por secciones, embeddings y guardado
- Selector de búsqueda por similitud de coseno
- Servicio que orquesta la consulta pública: recuperar, preguntar al modelo y
  devolver respuesta con citas
- Endpoint público `POST /api/v1/agente/consultas/` con límite de peticiones
- Cuatro documentos ficticios y el comando `cargar_demo_ia`
- Auditoría de la creación e indexación de documentos

**No incluye:**
- **Herramientas del agente sobre selectores** (propiedades disponibles,
  precios): spec propia del sábado 31, cuando existan los selectores de
  `catalogo`.
- **Modo interno con permisos:** solo si sobra tiempo, según el plan.
- **Bitácora del agente (`LogAgenteIA`):** la crea el rol D en `auditoria` (#23).
  Esta spec deja el punto de llamada listo (§7).
- **Ingesta por la cola de RabbitMQ:** la crea el rol D (#25). Su tarea de Celery
  llamará a `indexar_documento(documento_id=...)` de esta spec, que ya recibe
  solo un identificador (`docs/arquitectura.md` §6).
- **Relación con `DocumentoOficial`:** ese modelo aún no existe (lo crea A en una
  spec posterior). Se agrega el campo cuando exista.
- **PDF y otros formatos:** solo Markdown (`.md`). Ver §10.
- **Llamar a `cargar_demo_ia` desde `seed_demo`:** `seed_demo` vive en `core`, de
  A. Se le pide en un PR aparte, con la misma regla que la spec 004.
- Pantalla del agente: va sobre la base del frontend.

## 3. Reglas de negocio

1. El agente responde **solo** con información de los fragmentos recuperados. No
   usa conocimiento general del modelo.
2. Toda respuesta con información lleva al menos una cita con **documento y
   sección**.
3. Si ningún fragmento supera el umbral de similitud (§6), el agente responde que
   no tiene información sobre eso, con `sin_informacion: true`, y **no llama al
   modelo de lenguaje**. Así no gasta cuota ni le da al modelo la oportunidad de
   inventar.
4. Solo se consultan documentos **activos**. Desactivar un documento lo saca de
   las respuestas sin borrar sus fragmentos.
5. Un documento se trocea por sus encabezados `##`. Cada fragmento guarda el
   texto del encabezado como `seccion`. El texto anterior al primer `##` queda en
   la sección `Introducción`.
6. Una sección de más de 1,500 caracteres se divide por párrafos en fragmentos
   de hasta 1,500 caracteres. Cada fragmento nuevo repite el último párrafo del
   anterior (solapamiento), para no cortar una idea a la mitad.
7. Reindexar un documento reemplaza todos sus fragmentos en una sola transacción.
   Nunca quedan fragmentos de dos versiones mezclados.
8. La pregunta tiene entre 3 y 500 caracteres.
9. Si Gemini no responde (503, 429 o tiempo agotado), se reintenta hasta 3 veces
   con espera creciente. Si sigue fallando, la API responde 503
   `AGENTE_NO_DISPONIBLE`, nunca un 500.
10. Los documentos del demo son ficticios. **No se envían datos personales reales
    a Gemini** (`CLAUDE.md`): en la capa gratuita, Google usa el contenido para
    mejorar sus productos.

## 4. Modelo de datos

```
ia → core, auditoria
```

### `ia.DocumentoRAG` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `titulo` | CharField(200) | Único |
| `tipo` | CharField, enum `TipoDocumentoRAG` | `POLITICA`, `MANUAL`, `LEGAL`, `PLANTILLA`, `FICHA_PROPIEDAD` |
| `pais` | FK `core.Pais` | Opcional, `PROTECT`. Vacío si aplica a todos los países |
| `contenido_fuente` | TextField | El Markdown completo. Ver §10 |
| `version` | PositiveIntegerField | Empieza en 1; sube cuando cambia el contenido |
| `fecha_indexacion` | DateTimeField | Nulo hasta la primera indexación |

Si `ModeloBase` no trae `activo`, se agrega aquí (regla 4).

Respecto de `docs/modelo-datos.md`: `archivo_url` se reemplaza por
`contenido_fuente` y `documento_oficial` se pospone (§2). Se actualiza ese
documento en el mismo PR de implementación.

### `ia.FragmentoRAG` (no hereda `ModeloBase`, ver §10)

| Campo | Tipo | Nota |
|---|---|---|
| `documento` | FK `DocumentoRAG` | `CASCADE`, `related_name="fragmentos"` |
| `orden` | PositiveIntegerField | Posición dentro del documento |
| `seccion` | CharField(255) | Texto del encabezado `##` (regla 5) |
| `contenido` | TextField | Texto del fragmento |
| `tokens` | PositiveIntegerField | Estimado: caracteres ÷ 4 |
| `embedding` | `VectorField(dimensions=768)` | De la librería `pgvector` |

**Constraints:** único (`documento`, `orden`).
**Índices:** `documento`, y un índice **HNSW** sobre `embedding` con
`vector_cosine_ops`.

La extensión `vector` ya existe en la base: la habilita la migración
`core.0003_extension_vector` (spec 002).

## 5. API

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| POST | `/api/v1/agente/consultas/` | Hacer una pregunta al agente | Público, `throttle_scope = "agente"` |

**Límite:** `"agente": "10/min"` por IP en `DEFAULT_THROTTLE_RATES`. Usa la misma
caché en PostgreSQL y la misma regla de IP que el login (spec 001).

**Ejemplo de petición:**

```json
{ "pregunta": "¿Qué documentos necesito para comprar una casa en Guatemala?" }
```

**Ejemplo de respuesta 200:**

```json
{
  "respuesta": "Necesitas tu DPI vigente y una constancia de ingresos [1]. Si compras con financiamiento, el banco pide además un avalúo [2].",
  "sin_informacion": false,
  "citas": [
    {
      "numero": 1,
      "documento": "Requisitos legales de compraventa – Guatemala",
      "seccion": "Documentos del comprador",
      "tipo": "LEGAL",
      "extracto": "El comprador presenta su Documento Personal de Identificación vigente…"
    },
    {
      "numero": 2,
      "documento": "Manual de procesos de venta",
      "seccion": "Compras con financiamiento",
      "tipo": "MANUAL",
      "extracto": "Cuando la compra se financia, la entidad bancaria solicita…"
    }
  ]
}
```

**Respuesta 200 sin información (regla 3):**

```json
{
  "respuesta": "No encontré información sobre eso en los documentos de la agencia. Te recomiendo contactar a un agente.",
  "sin_informacion": true,
  "citas": []
}
```

Los marcadores `[n]` de la respuesta apuntan al `numero` de cada cita. El
`extracto` son los primeros 200 caracteres del fragmento, para que la pantalla
muestre la fuente.

**Errores:**

| Código | Situación | HTTP |
|---|---|---|
| `VALIDACION` | Falta la pregunta o no cumple la regla 8 | 400 |
| `DEMASIADAS_PETICIONES` | Se superó el límite de 10 por minuto | 429 |
| `AGENTE_NO_DISPONIBLE` | Gemini no respondió tras los reintentos (regla 9) | 503 |

`AgenteNoDisponible` hereda de `ErrorDominio` (`apps/core/exceptions.py`), así
el manejador global ya la traduce al formato uniforme.

## 6. Servicios y selectores

**Proveedor** (`apps/ia/proveedores/`). Solo aquí se importa el SDK de Gemini.

```python
# base.py — la interfaz de docs/arquitectura.md §7, con un parámetro agregado
class ProveedorIA(ABC):
    def generar_respuesta(self, *, mensajes: list[Mensaje],
                          herramientas: list[Herramienta] | None = None) -> RespuestaIA
    def generar_embedding(self, *, texto: str, tarea: TareaEmbedding) -> list[float]
    def generar_embeddings_lote(self, *, textos: list[str], tarea: TareaEmbedding) -> list[list[float]]

class ProveedorIANoDisponible(Exception):
    """El proveedor no respondió tras los reintentos. El servicio la traduce."""

# gemini.py
class ProveedorGemini(ProveedorIA):
    """Usa IA_MODELO, IA_MODELO_EMBEDDINGS y siempre output_dimensionality =
    IA_DIMENSION_EMBEDDINGS. Reintenta 503, 429 y tiempo agotado (regla 9).
    Lotes de embeddings de hasta 100 textos (confirmar el límite al implementar)."""

# fabrica.py
def obtener_proveedor() -> ProveedorIA
    """Instancia el proveedor según IA_PROVEEDOR."""
```

`TareaEmbedding` (`DOCUMENTO`, `CONSULTA`) le dice al proveedor para qué es el
vector. Gemini da mejores resultados si sabe si está indexando un documento o
buscando con una pregunta. Se actualiza `docs/arquitectura.md` §7 en el mismo PR.

**Servicios** (`apps/ia/services.py`):

```python
def crear_documento_rag(*, titulo: str, tipo: TipoDocumentoRAG, contenido_fuente: str,
                        pais: Pais | None, autor: Usuario | None) -> DocumentoRAG
    """Crea el documento sin indexar. Audita CREAR."""

def actualizar_contenido_documento(*, documento: DocumentoRAG, contenido_fuente: str,
                                   autor: Usuario | None) -> DocumentoRAG
    """Si el texto cambió, sube la versión y audita ACTUALIZAR. Si no cambió, no hace nada."""

def indexar_documento(*, documento_id: int) -> int
    """Trocea (reglas 5 y 6), pide los embeddings en lote y reemplaza los
    fragmentos en una transacción (regla 7). Devuelve cuántos fragmentos creó.
    Los embeddings se piden ANTES de abrir la transacción: es una llamada de red
    lenta y no debe mantener la transacción abierta. Recibe un id para que la
    tarea de Celery de #25 pueda llamarla sin cambios."""

def responder_consulta_publica(*, pregunta: str) -> RespuestaAgente
    """Vectoriza la pregunta, recupera fragmentos y, si alguno supera el umbral,
    pide la respuesta al modelo con instrucciones de citar [n]. Traduce
    ProveedorIANoDisponible a AgenteNoDisponible."""
```

`responder_consulta_publica` va en `services.py` aunque hoy no escribe, porque
escribirá la bitácora del agente en cuanto exista #23.

**Selectores** (`apps/ia/selectors.py`):

```python
def buscar_fragmentos_similares(*, embedding: list[float], limite: int = 5,
                                distancia_maxima: float) -> list[FragmentoRAG]
    """Los fragmentos de documentos activos más cercanos por distancia de
    coseno, solo los que no pasan de distancia_maxima, del más al menos cercano."""
```

**Umbral:** `IA_DISTANCIA_MAXIMA`, con valor por defecto `0.6`. Se ajusta con los
documentos del demo durante la implementación y el valor final queda anotado en
§11.

**Instrucción al modelo:** responder en español, solo con los fragmentos dados,
citar con `[n]` y decir que no sabe si los fragmentos no alcanzan (reglas 1 y 2).
El texto exacto vive en `apps/ia/instrucciones.py`, para poder revisarlo.

**Comando:** `python manage.py cargar_demo_ia` lee los cuatro `.md` de
`apps/ia/documentos_demo/`:

| Archivo | Tipo | País |
|---|---|---|
| `politica-comercial.md` | `POLITICA` | — |
| `manual-procesos-venta.md` | `MANUAL` | — |
| `requisitos-compraventa-guatemala.md` | `LEGAL` | Guatemala |
| `requisitos-compraventa-mexico.md` | `LEGAL` | México |

Es idempotente: crea los documentos nuevos, actualiza los que cambiaron y
**solo indexa los nuevos o cambiados**. Si `IA_API_KEY` está vacía, avisa y
termina sin error. Así no rompe el arranque en producción ni gasta cuota de
Gemini en cada despliegue.

## 7. Auditoría

| Acción | Cuándo | Valores |
|---|---|---|
| `CREAR` sobre `ia_documento_rag` | `crear_documento_rag` | título, tipo, país |
| `ACTUALIZAR` sobre `ia_documento_rag` | Cambia el contenido o se reindexa | versión anterior y nueva; cantidad de fragmentos |

Se llama a `registrar_auditoria` dentro de la transacción del servicio, como en
la spec 001. El usuario es `None` cuando lo ejecuta el comando o la cola.

Las **consultas** al agente no se registran en esta spec: van en la bitácora del
agente (#23, rol D). El punto de llamada queda marcado con un comentario en
`responder_consulta_publica`, con lo que esa bitácora necesitará: pregunta,
fragmentos usados, respuesta, tokens y duración.

El panel de Django muestra `DocumentoRAG` y `FragmentoRAG` en **solo lectura**:
editarlos ahí saltaría los servicios y la auditoría.

## 8. Criterios de aceptación

- [ ] El SDK de Gemini solo se importa dentro de `apps/ia/proveedores/`.
- [ ] `obtener_proveedor()` devuelve `ProveedorGemini` con `IA_PROVEEDOR=gemini`.
- [ ] Todo embedding guardado tiene 768 dimensiones. Si el proveedor devuelve
      otra cantidad, la indexación falla con un error claro y no guarda nada.
- [ ] Un documento con 3 secciones `##` cortas produce 3 fragmentos, cada uno con
      su `seccion` correcta.
- [ ] Una sección de más de 1,500 caracteres se divide con solapamiento (regla 6).
- [ ] Reindexar reemplaza todos los fragmentos. Si el proveedor falla a la
      mitad, quedan los fragmentos anteriores intactos (regla 7).
- [ ] La búsqueda no devuelve fragmentos de documentos inactivos (regla 4).
- [ ] Sin fragmentos sobre el umbral, la respuesta es `sin_informacion: true` y
      el modelo de lenguaje **no** se llama (regla 3; se verifica con un
      proveedor falso).
- [ ] Con fragmentos, la respuesta trae citas con documento, sección y extracto.
- [ ] Si el proveedor falla siempre, el endpoint responde 503
      `AGENTE_NO_DISPONIBLE`.
- [ ] La pregunta de 2 caracteres o de 501 responde 400 `VALIDACION`.
- [ ] La petición 11 en un minuto desde la misma IP responde 429.
- [ ] El endpoint funciona sin token.
- [ ] `cargar_demo_ia` corrido dos veces seguidas no crea duplicados ni llama a
      Gemini la segunda vez. Con `IA_API_KEY` vacía, termina sin error.
- [ ] Crear y reindexar un documento queda en la bitácora del sistema.
- [ ] Las pruebas no llaman a Gemini: usan un proveedor falso con vectores fijos.
- [ ] `ruff`, `makemigrations --check` y `pytest` pasan (`docs/convenciones.md` §1.1).

## 9. Pruebas

- **Servicios:** troceo (reglas 5 y 6), indexación y su reemplazo atómico, umbral
  sin llamar al modelo, traducción del error del proveedor, idempotencia del
  comando.
- **Selectores:** orden por cercanía, umbral y exclusión de inactivos, con
  vectores fijos.
- **API:** caso feliz, pregunta inválida, límite de peticiones y 503.
- **Proveedor Gemini:** los reintentos, simulando las respuestas del SDK. No se
  llama a la red en ninguna prueba.

## 10. Decisiones y alternativas descartadas

**Modelo `gemini-3.5-flash-lite`.** Se probó el 2026-10-28 con la llave del
proyecto. `gemini-flash-latest` respondió 503 por alta demanda y
`gemini-3.8-flash` no respondió en 60 segundos. El lite respondió al instante.
Para el RAG basta: el modelo resume fragmentos que ya se le entregan, no
necesita razonar en profundidad. Va en `IA_MODELO` y cambiarlo es editar una
variable, sin tocar código.

**Versión fija y no un alias `-latest`.** Un alias puede cambiar de
comportamiento sin aviso, por ejemplo el día de la defensa. Una versión fija
podría retirarse, pero para una entrega del 3 de noviembre ese riesgo es mínimo.

**768 dimensiones.** `gemini-embedding-001` devuelve 3,072 por defecto. Se piden
768 con `output_dimensionality`; el modelo está entrenado para conservar casi
toda la calidad al reducir. Además, los índices HNSW e IVFFlat de pgvector
admiten como máximo 2,000 dimensiones en el tipo `vector`: con 3,072 no se
podría indexar. Probado: la llave devolvió 768.

**HNSW en lugar de IVFFlat.** IVFFlat necesita datos para entrenar sus listas
antes de crear el índice. HNSW se crea vacío y funciona desde el primer
fragmento, que es nuestro caso.

**Solo Markdown.** La sección se toma del encabezado `##` sin heurísticas. Leer
PDF exigiría otra librería y adivinar dónde empieza cada sección.

**El texto en la base y no un archivo.** El almacenamiento de archivos en
producción es una decisión abierta del equipo (`CLAUDE.md`) y Render no tiene
disco persistente (spec 002). Guardar el Markdown en `contenido_fuente` permite
reindexar sin depender de esa decisión.

**`FragmentoRAG` sin `ModeloBase` y con `CASCADE`.** Un fragmento no es una
entidad de negocio: es un dato derivado que se regenera desde
`contenido_fuente`. No lo edita una persona, así que los campos de rastro no
dicen nada, y la regla de borrado lógico aplica al documento, no a sus pedazos.

**Umbral antes de llamar al modelo.** Si la búsqueda no encuentra nada cercano,
no se le pregunta al modelo. Ahorra cuota de la capa gratuita y elimina el caso
más común de respuesta inventada.

**Se devuelven todas las fuentes recuperadas.** Las citas son los fragmentos que
se le entregaron al modelo, numerados, y la respuesta los referencia con `[n]`.
Filtrar solo los que el modelo citó dependería de leer bien su texto, que es
menos confiable.

**Dependencias nuevas** (en `requirements/base.txt`, con su justificación):
`google-genai`, el SDK oficial de Gemini, y `pgvector`, que da `VectorField`,
`HnswIndex` y `CosineDistance` para Django. Las dos están previstas en el stack
de `CLAUDE.md`.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-28, preparación y borrador (Claude, rol C).** El agente leyó
`CLAUDE.md`, `docs/arquitectura.md` §6 y §7, `docs/modelo-datos.md`,
`docs/requisitos.md`, `docs/roadmap.md`, las specs 001, 003 y 004 y la estructura
vacía de `apps/ia`.

Antes de escribir se verificó con la llave real:
- Que la llave de AI Studio (formato `AQ.`, el nuevo de Google) autentica.
- Que `gemini-embedding-001` con `output_dimensionality=768` devuelve 768 valores.
- La lista de modelos disponibles; que `gemini-flash-latest` respondía 503 y
  `gemini-3.8-flash` no respondía en 60 s, mientras `gemini-3.5-flash-lite`
  respondió 200.

Decisiones tomadas por el integrante C entre opciones planteadas por el agente:
modelo lite con versión fija, documentos solo en Markdown, documentos demo con
comando propio y endpoint público con límite de peticiones. Las demás
decisiones de §10 son propuestas del agente que se validan en la revisión.

**Plan de implementación (un commit por incremento):**

1. Dependencias, variables de entorno y `ProveedorIA` con la implementación de
   Gemini y sus pruebas de reintentos
2. Modelos `DocumentoRAG` y `FragmentoRAG`, migración con índice HNSW y panel de
   solo lectura
3. Servicios de documentos e `indexar_documento`, con auditoría y pruebas del
   troceo
4. Selector de búsqueda por similitud
5. `responder_consulta_publica` y su instrucción al modelo
6. Endpoint `/agente/consultas/` con límite de peticiones
7. Documentos demo y `cargar_demo_ia`; ajuste del umbral
8. Cierre: actualizar `docs/arquitectura.md` §7, `docs/modelo-datos.md` y
   `.env.example`, verificar criterios y completar esta sección

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.