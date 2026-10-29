# 011 · Catálogo: avalúos y documentos oficiales

| Campo | Valor |
|---|---|
| **Número** | 011 |
| **Estado** | En revisión |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-29 |
| **Apps afectadas** | `catalogo`; configuración de almacenamiento en `config/settings` |
| **Rama** | `feature/011-avaluos-documentos` |
| **Pull request** | — |

---

## 1. Problema

La agencia necesita guardar dos cosas de cada propiedad:

- **Cuánto vale con el tiempo**: los avalúos de un perito, que muestran la
  plusvalía.
- **Sus papeles**: escrituras, licencias, planos y certificaciones, con su
  fecha de vencimiento cuando la tienen.

Hoy no hay dónde registrarlos. La spec 003 los dejó fuera porque faltaba
decidir dónde guardar los archivos en producción, donde Render no tiene disco
persistente.

## 2. Alcance

**Incluye:**
- Los modelos `Avaluo` y `DocumentoOficial`, con su API, auditoría y permisos.
- Subir y descargar archivos con **Supabase Storage** en producción y el disco
  local en desarrollo y pruebas (§10).
- Avalúos ficticios en `cargar_demo_catalogo`.

**No incluye:**
- **Indexar los documentos oficiales en el RAG.** La spec 005 solo procesa
  Markdown, y estos son PDF e imágenes. Se agrega si sobra tiempo, con la
  ingesta del rol D (#25).
- **El reporte de documentos por vencer:** es de la spec de reportes del rol D.
  Esta spec deja el filtro `?vence_antes=` que ese reporte puede usar.
- **Que los contratos apunten a sus documentos:** cada spec de contratos agrega
  su campo `documento` (§10).
- `EventoPropiedad`, que sigue en "solo si sobra tiempo".
- **Documentos de demostración:** se suben a mano en la demostración (§10).

## 3. Reglas de negocio

**Avalúos**

1. Un avalúo es de una propiedad. Tiene fecha, valor mayor que cero con su
   moneda, perito y metodología.
2. La fecha no puede ser futura.
3. **Los avalúos no se editan.** El historial es la plusvalía: si uno tiene un
   error, se desactiva (borrado lógico, auditado) y se registra el correcto.
4. El documento que respalda un avalúo, si lo hay, debe ser de la **misma
   propiedad**.

**Documentos oficiales**

5. Un documento es de una propiedad. Tiene tipo (`ESCRITURA`, `LICENCIA`,
   `PLANO`, `CERTIFICACION`, `AVALUO`, `CONTRATO`, `OTRO`), nombre, fecha de
   emisión, fecha de vencimiento opcional y emisor.
6. **Archivos aceptados:** PDF, JPG o PNG, de hasta **10 MB**.
   - El tipo se comprueba por el contenido del archivo, no solo por la
     extensión.
7. **El archivo no se reemplaza.** Se pueden editar sus datos (nombre, fechas,
   emisor). Una versión nueva es un documento nuevo, y el anterior se
   desactiva.
8. **El archivo se guarda con un nombre generado:**
   `documentos/<código de propiedad>/<uuid>.<extensión>`.
   - El nombre original se guarda aparte, para mostrarlo.
   - Así dos archivos llamados `escritura.pdf` no chocan y nadie adivina la ruta
     de otro.
9. **Desactivar un documento no borra su archivo** (CLAUDE.md §7). Un documento
   que respalda un avalúo activo no se desactiva.
10. **Descargar exige sesión.** El archivo nunca es público:
    - la API responde con una **URL firmada que vence en 5 minutos**
      (`docs/arquitectura.md` §9);
    - el bucket de Supabase es **privado**.

**Permisos** (esquema de la spec 004)

11. Registran y desactivan avalúos y documentos `ADMINISTRADOR` y `GERENTE`.
    Todos los roles autenticados leen y descargan, igual que el catálogo
    (regla 8 de la spec 003).

## 4. Modelo de datos

### `catalogo.Avaluo` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `propiedad` | FK `Propiedad` | `PROTECT`, `related_name="avaluos"` |
| `fecha` | DateField | No futura (regla 2) |
| `valor` | DecimalField(18, 2) | > 0, constraint |
| `moneda` | FK `core.Moneda` | `PROTECT` |
| `perito` | CharField(150) | |
| `metodologia` | CharField(150) | Comparativo, costo de reposición… (texto libre) |
| `documento` | FK `DocumentoOficial` | Opcional, `PROTECT` (regla 9) |
| `observaciones` | TextField | Opcional |

### `catalogo.DocumentoOficial` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `propiedad` | FK `Propiedad` | `PROTECT`, `related_name="documentos"` |
| `tipo` | CharField, enum `TipoDocumento` | Regla 5 |
| `nombre` | CharField(200) | |
| `archivo` | FileField | Ruta generada (regla 8) |
| `nombre_original` | CharField(255) | El nombre con que se subió |
| `tipo_contenido` | CharField(50) | `application/pdf`, `image/jpeg`, `image/png` |
| `tamano_bytes` | PositiveIntegerField | ≤ 10 MB (regla 6) |
| `fecha_emision` | DateField | |
| `fecha_vencimiento` | DateField | Opcional, ≥ `fecha_emision` (constraint) |
| `emisor` | CharField(150) | Registro, municipalidad, notario… |

**Cambios respecto de `docs/modelo-datos.md`**, que se actualiza en el PR de
implementación:

- `archivo_url` pasa a `archivo` (un `FileField`). Se guarda la ruta, no una
  URL: la URL firmada cambia en cada descarga.
- `subido_por` y `fecha_carga` se quitan, porque `creado_por` y `creado_en` de
  `ModeloBase` guardan lo mismo.
- `estado_indexacion` se pospone con el RAG (§2).
- `contrato_venta` y `contrato_compra` se quitan: la relación va al revés (§10).

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| GET, POST | `/api/v1/propiedades/{id}/avaluos/` | Leer: todos · Registrar: regla 11 |
| GET, DELETE | `/api/v1/avaluos/{id}/` | DELETE desactiva (regla 3) |
| GET, POST | `/api/v1/propiedades/{id}/documentos/` · POST como `multipart/form-data` · filtros `?tipo=`, `?vence_antes=AAAA-MM-DD` | Leer: todos · Subir: regla 11 |
| GET, PATCH, DELETE | `/api/v1/documentos/{id}/` · PATCH solo nombre, fechas y emisor (regla 7) | Regla 11 para escribir |
| GET | `/api/v1/documentos/{id}/descarga/` → `{ "url", "vence_en_segundos": 300 }` | Todos |

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `ARCHIVO_NO_PERMITIDO` | Tipo distinto de PDF, JPG o PNG, o más de 10 MB (regla 6) | 400 |
| `DOCUMENTO_DE_OTRA_PROPIEDAD` | El documento del avalúo es de otra propiedad (regla 4) | 409 |
| `DOCUMENTO_EN_USO` | Se desactiva un documento que respalda un avalúo activo (regla 9) | 409 |

## 6. Servicios y selectores

```python
# catalogo/services.py  (transaction.atomic y registrar_auditoria)
def registrar_avaluo(*, propiedad, datos: dict, autor, ip) -> Avaluo
def desactivar_avaluo(*, avaluo, autor, ip) -> None
def subir_documento(*, propiedad, archivo: UploadedFile, datos: dict, autor, ip) -> DocumentoOficial
def actualizar_documento(*, documento, datos: dict, autor, ip) -> DocumentoOficial
def desactivar_documento(*, documento, autor, ip) -> None
def generar_url_descarga(*, documento) -> str     # URL firmada de 5 minutos (regla 10)

# catalogo/selectors.py
def listar_avaluos(*, propiedad: Propiedad | None = None) -> QuerySet[Avaluo]
def listar_documentos(*, propiedad: Propiedad | None = None) -> QuerySet[DocumentoOficial]
```

**Orden en `subir_documento`.** El almacenamiento no forma parte de la
transacción de la base, así que:

1. Se valida el archivo (regla 6).
2. Se sube el archivo.
3. Se guarda el registro y su auditoría en la transacción.
4. Si el paso 3 falla, se intenta borrar el archivo recién subido.

En el peor caso queda un archivo huérfano en el bucket, pero nunca un registro
que apunte a un archivo inexistente.

**Configuración** (`config/settings`):

- `STORAGES["default"]` usa `django-storages` con su backend S3, apuntando a
  Supabase, cuando `STORAGE_BACKEND=s3`.
- Con `STORAGE_BACKEND=local` (desarrollo y pruebas), usa `FileSystemStorage`
  en `media/`, que no se sube al repositorio.
- Variables nuevas en `.env.example`, sin valor: `STORAGE_ENDPOINT_URL`. Junto a
  las que ya existen: `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`,
  `STORAGE_SECRET_KEY` y `STORAGE_REGION`.

## 7. Auditoría

| Operación | Acción | Valores |
|---|---|---|
| Registrar avalúo | `CREAR` | Todos sus campos |
| Subir documento | `CREAR` | Sus datos, el nombre original, el tipo, el tamaño y la ruta guardada, pero nunca el contenido |
| Editar documento | `ACTUALIZAR` | Solo los campos que cambian |
| Desactivar avalúo o documento | `ELIMINAR` | `activo`: `true` → `false` |

Las descargas no se auditan: son lecturas.

## 8. Criterios de aceptación

- [ ] Un gerente registra un avalúo y aparece en el historial de la propiedad,
      del más reciente al más antiguo
- [ ] Un avalúo con fecha futura o valor 0 se rechaza (400)
- [ ] Un avalúo con el documento de otra propiedad: 409
      `DOCUMENTO_DE_OTRA_PROPIEDAD`
- [ ] Un gerente sube un PDF y lo descarga con la URL firmada; la URL deja de
      servir después de 5 minutos
- [ ] Un `.exe` renombrado a `.pdf`, o un PDF de 11 MB: 400
      `ARCHIVO_NO_PERMITIDO`
- [ ] Dos archivos con el mismo nombre no se pisan
- [ ] En producción, el archivo queda en el bucket privado de Supabase, y su URL
      sin firmar no se puede abrir
- [ ] Desactivar un documento que respalda un avalúo activo: 409
      `DOCUMENTO_EN_USO`
- [ ] Agente, contabilidad y consulta leen y descargan, y reciben 403 al
      escribir
- [ ] `?vence_antes=` devuelve solo los documentos que vencen antes de esa fecha
- [ ] Toda escritura queda en la bitácora
- [ ] `ruff`, `pytest`, `makemigrations --check` y el esquema OpenAPI pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Modelo | Valor > 0; vencimiento ≥ emisión |
| Servicio | Avalúo con fecha futura y con documento ajeno; subir con tipo y tamaño inválidos; nombre generado; desactivar documento en uso |
| Servicio | Si falla el guardado del registro, el archivo subido se borra |
| API | Subida `multipart`, descarga con URL, matriz de permisos, filtro de vencimiento |
| Manual, producción | Subida y descarga contra Supabase; la URL sin firmar se rechaza |

Las pruebas usan el almacenamiento local en una carpeta temporal: nunca tocan
Supabase.

## 10. Decisiones y alternativas descartadas

**Supabase Storage para los archivos** (decidido por A, 2026-10-29). Cierra la
decisión abierta de `CLAUDE.md` §9.

| Opción | Por qué no se eligió, o por qué sí |
|---|---|
| **Supabase Storage** | Elegido. Gratis hasta 1 GB, bucket privado y API compatible con S3, que permite usar el backend estándar de `django-storages` sin código propio. Si algún día se cambia de proveedor, solo cambian las variables |
| Backblaze B2 | Más espacio (10 GB), pero 1 GB alcanza de sobra para la demostración |
| Guardarlos en Neon | Sin proveedor nuevo, pero consume los 0.5 GB de la base y contradice `docs/arquitectura.md` §9 |
| Disco de Render | No es persistente: los archivos se pierden en cada despliegue |

*Limitaciones aceptadas del plan gratuito:*

- Supabase pausa un proyecto tras una semana sin actividad, y se reactiva
  desde su panel. Antes de la defensa se abre el panel.
- El tamaño máximo por archivo es de 50 MB, por encima de los 10 MB de la
  regla 6.

**Dependencias nuevas:** `django-storages` y `boto3`. Es la integración estándar
de Django con almacenamientos compatibles con S3; escribirla a mano sería más
código que defender. Se fijan con `==` y pasan `pip-audit`.

**URL firmada en lugar de pasar el archivo por la API.** Que Django descargue
el archivo de Supabase y lo reenvíe ocuparía el único proceso de gunicorn
durante toda la descarga. Con la URL firmada, el navegador descarga directo de
Supabase, y la API solo decide quién puede.

*Riesgo a comprobar en el incremento 1:* que Supabase acepte las URL firmadas
que genera `boto3`. Si no las acepta, la descarga pasa por la API y la §5
cambia en el mismo PR.

**La relación con los contratos va al revés.** `docs/modelo-datos.md` ponía en
`DocumentoOficial` llaves hacia `ContratoVenta` y `ContratoCompra`. Pero esos
contratos ya apuntan a `Propiedad`, así que se formaría un ciclo:

```
catalogo → ventas → catalogo
```

Es el problema anotado en `docs/roadmap.md`. Aquí se resuelve como ya lo hacen
`Avaluo` y `PagoConstructora`: el que necesita un documento apunta a él.

- `ContratoVenta` y `ContratoCompra` agregan un campo `documento` opcional en
  sus specs.
- Así `catalogo` no depende de `ventas` ni de `compras`.
- **Se pide la conformidad de B y C en la revisión.**

**Avalúos que no se editan.** El valor del historial es mostrar cómo cambió el
precio en el tiempo. Si se pudiera editar, la plusvalía podría reescribirse sin
dejar rastro visible en el historial. El error se corrige con
desactivar y registrar de nuevo, y los dos pasos quedan en la bitácora.

**Sin documentos de demostración.** `seed_demo` corre en cada arranque, y subir
archivos a Supabase en cada despliegue gastaría cuota y tiempo de arranque. Los
avalúos sí se cargan, porque son solo datos.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-29 (Claude Code, rol A).** A eligió Supabase Storage entre las
tres opciones que planteó el agente (Supabase, Backblaze B2 y la base de Neon).
El agente redactó el borrador a partir de:

- `docs/modelo-datos.md` §2;
- `docs/arquitectura.md` §9;
- el problema del ciclo anotado en `docs/roadmap.md`;
- las specs 003 y 005;
- la configuración de `STORAGES` en `config/settings/prod.py`.

Propuso invertir la relación con los contratos para evitar el ciclo.

**Plan de implementación:**
1. Almacenamiento: dependencias, `STORAGES` por variable, bucket en Supabase y
   la prueba de la URL firmada.
2. Avalúos: modelo, servicios, API y datos de demostración.
3. Documentos: modelo, subida, descarga, desactivación y filtros.
4. Cierre con los criterios de §8 en producción.
