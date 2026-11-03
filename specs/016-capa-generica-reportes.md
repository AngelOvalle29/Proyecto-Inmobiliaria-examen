# 016 · Capa genérica de reportes y primeras exportaciones

| Campo | Valor |
|---|---|
| **Número** | 016 |
| **Estado** | Implementada |
| **Autor** | Nathaly Saraí Reyes Cifuentes (rol D), con apoyo de Codex |
| **Revisor** | AngelOvalle29 (rol C), aprobación del PR #61 sobre `dc258e5` |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `reportes`; lecturas de `catalogo`, `core` y `auditoria`; frontend |
| **Rama** | Documentación: `docs/015-016-bloque-d`; implementación propuesta: `feature/016-capa-generica-reportes` |
| **Pull request** | [#61](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/61) (spec); implementación en [#77](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/77) |

## 1. Problema

Hay datos comerciales y de catálogo, pero `reportes` aún es un esqueleto. Se
necesita construir una sola vez la consulta con filtros, la vista previa y los
exportadores, para añadir los reportes restantes sin repetir infraestructura.

## 2. Alcance

**Incluye:** catálogo paginado con metadatos de filtros y columnas, estructura
`Reporte` de `docs/reportes.md`, exportadores openpyxl y WeasyPrint, pantalla
genérica con TanStack Query y tres reportes sobre datos existentes:

| Reporte | Filtros | Agregaciones |
|---|---|---|
| R05 Inventario disponible | País, ciudad, tipo, moneda, precio mínimo/máximo y área mínima/máxima | Cantidad, área y valor de lista por ciudad, tipo y moneda |
| R16 Documentos por vencer | Tipo, país, días de anticipación | Cantidad vencida y por vencer |
| R17 Bitácora de auditoría | Usuario, entidad, acción, fecha desde/hasta | Cantidad por entidad y acción |

**No incluye:** generación pesada por Celery, vistas `bi`, tablero `.pbix`,
ni los otros 12 reportes mínimos. Se especifican por incrementos posteriores;
este incremento **no cierra #24** ni cumple por sí solo el mínimo de 15.

## 3. Reglas de negocio

Reglas del incremento aprobado en el PR #61; su cumplimiento se comprobará
durante la implementación.

1. Cada reporte declara slug, título, columnas, filtros y roles. Un slug
   desconocido devuelve 404. El catálogo solo muestra reportes autorizados y
   las rutas de datos y descarga vuelven a comprobar el permiso.
2. R05/R16 para todos los roles autenticados, coherente con la lectura de
   propiedades y documentos en las specs 003 y 011. R17 solo para
   `ADMINISTRADOR`, porque puede contener datos sensibles y accesos fallidos.
3. Filtros inválidos o desconocidos devuelven 400 `VALIDACION`. Fechas ISO,
   rangos inclusivos y mínimo menor o igual a máximo. Para fechas de auditoría,
   convertir días de Guatemala a límites conscientes de zona horaria en UTC.
4. JSON pagina 25 filas con orden estable terminado en identificador único.
   Los totales abarcan todo el resultado filtrado, no solo la página visible.
   En R05 cada fila usa la pareja `(origen, id)` para distinguir una propiedad
   de una unidad con el mismo identificador. Se pagina antes de materializar
   filas: no se carga todo el inventario para mostrar 25 registros.
5. Excel y PDF usan los mismos filtros, columnas, filas y totales. No usan la
   página visible como fuente. Límite síncrono: 5,000 filas; si se
   supera, ambas descargas devuelven 400 `REPORTE_DEMASIADO_GRANDE` y piden
   acotar filtros. Nunca se trunca silenciosamente.
6. Dinero con `Decimal`, dos decimales y código de moneda. R05 conserva moneda
   original y separa totales por moneda; no suma GTQ y USD. Conversión a moneda
   de presentación queda para un incremento que defina fecha y tasa con core.
7. R05 incluye propiedades activas sin unidades según su tipo, y unidades
   activas de propiedades activas cuyo tipo requiere unidades. Solo filas con
   estado `DISPONIBLE`; no suma el precio del edificio además del de sus unidades.
   Para una unidad se usa su propio precio, moneda y área; país, ciudad y tipo
   provienen de su propiedad. El rango de precio se interpreta en la moneda
   filtrada: exige `moneda` cuando se indique precio mínimo o máximo.
8. R16 incluye documentos activos de propiedades activas con vencimiento no
   nulo y menor o igual a hoy + N días. N entero entre 0 y 365, por defecto 30.
   Vencido: fecha anterior a hoy; por vencer: desde hoy hasta el límite inclusive.
9. R17 usa los registros existentes sin modificarlos. Vista y archivos incluyen
   fecha, usuario_id, entidad, entidad_id y acción; no exportan los JSON de
   valores, IP ni user-agent en este incremento.
10. XLSX conserva números y fechas como celdas tipadas; cualquier texto externo
    se escribe como texto literal, aunque empiece por `=`, `+`, `-` o `@`.
    La plantilla PDF escapa HTML y no carga recursos externos aportados por datos.

## 4. Modelo de datos

Sin tablas ni migraciones nuevas. `Reporte`, `Columna` y `Grupo` son dataclasses
en memoria con la estructura de `docs/reportes.md` §1. Los filtros también son
tipados; cada selector devuelve datos de solo lectura para construir el reporte.

`Reporte.filas` es la lista de filas **ya seleccionadas**: una página para
JSON o todo el resultado dentro del límite para exportar. No ejecuta consultas
ni exige cargar todo el conjunto. `ReportePaginado` contiene `reporte: Reporte`,
`count: int`, `pagina: int` y `tamano_pagina: int` (25). La capa HTTP transforma
estos datos en `filas: {count, next, previous, results}`. `totales` y
`agrupamientos` siempre describen todo el conjunto filtrado.

## 5. API

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/api/v1/reportes/` | Catálogo paginado, con filtros, columnas y permisos aplicados |
| GET | `/api/v1/reportes/{slug}/` | Metadatos, filas paginadas, totales y agrupamientos completos |
| GET | `/api/v1/reportes/{slug}/excel/` | Archivo `.xlsx` |
| GET | `/api/v1/reportes/{slug}/pdf/` | Archivo `.pdf` |

Slugs: `inventario-disponible`, `documentos-por-vencer`, `bitacora-auditoria`.
Ejemplo: `GET /api/v1/reportes/documentos-por-vencer/?dias_anticipacion=30&page=1`.

La respuesta JSON contiene `titulo`, `subtitulo`, `generado_en`, `generado_por`,
`columnas`, `totales`, `agrupamientos` y `filas`; `filas` usa el sobre habitual
`count`, `next`, `previous`, `results`. Los filtros describen nombre, etiqueta,
tipo, obligatoriedad y origen de opciones para construir el formulario genérico.

Errores: 401 sin autenticación, 403 sin rol, 404 slug desconocido; 400 para
validación o exportación demasiado grande. Descargas con `Content-Disposition`
y nombre `R05_inventario_disponible_AAAA-MM-DD.xlsx` (análogo para PDF).

## 6. Servicios y selectores

Firmas previstas para la implementación, con anotaciones y docstrings:

- `listar_reportes(*, usuario: AbstractBaseUser) -> list[dict]`: catálogo autorizado.
- `seleccionar_inventario(*, filtros: FiltrosInventario) -> QuerySet[dict]`:
  lecturas R05 con proyecciones compatibles de propiedades y unidades.
- `seleccionar_vencimientos(*, filtros: FiltrosVencimientos) -> QuerySet`: lecturas R16.
- `seleccionar_bitacora(*, filtros: FiltrosBitacora) -> QuerySet`: lecturas R17.
- `resumir_reporte(*, slug: str, filtros: FiltrosReporte) -> ResumenReporte`:
  selector que calcula `count`, `totales` y `agrupamientos` en PostgreSQL,
  antes de paginar y sin materializar filas de detalle. En R05 agrega
  propiedades y unidades por separado y combina resúmenes sin doble conteo.
- `seleccionar_filas_reporte(*, slug: str, filtros: FiltrosReporte, offset: int,
  limite: int) -> list[dict]`: selector que aplica orden estable y
  `LIMIT/OFFSET` en PostgreSQL antes de convertir el resultado en lista.
- `construir_reporte(*, slug: str, filas: list[dict], resumen: ResumenReporte,
  filtros: FiltrosReporte, usuario: AbstractBaseUser) -> Reporte`:
  presentación compartida, sin consultas; recibe las filas ya elegidas.
- `obtener_reporte_paginado(*, slug: str, filtros: FiltrosReporte,
  usuario: AbstractBaseUser, pagina: int = 1) -> ReportePaginado`:
  comprueba permisos, obtiene el resumen y solicita solo 25 filas con
  `offset=(pagina-1)*25`. Usa `construir_reporte` con esas filas. Una página
  inválida devuelve 404 según la paginación habitual; sin resultados, página 1 vacía.
- `obtener_reporte_exportacion(*, slug: str, filtros: FiltrosReporte,
  usuario: AbstractBaseUser) -> Reporte`: comprueba permisos, obtiene el resumen,
  rechaza `count > 5000` antes de cargar detalles y selecciona las filas con
  `offset=0, limite=5000`; construye el reporte completo. Las descargas no
  admiten `page`: responde 400 `VALIDACION` si se envía, para evitar ambigüedad.
- `exportar_excel(reporte: Reporte) -> bytes` y `exportar_pdf(reporte: Reporte) -> bytes`:
  solo presentación, sin consultar modelos.

`FiltrosReporte` es la unión de las tres dataclasses de filtros.
`ResumenReporte` contiene `count: int`, `totales: dict` y
`agrupamientos: list[Grupo]`. Ningún endpoint pagina una lista completa en
memoria. Las consultas, agregaciones y límites viven en selectores; el servicio
elige el flujo paginado o el de exportación y los exportadores solo renderizan.

Frontend: una ruta `/reportes`, formulario generado por metadatos, tabla paginada
y descargas autenticadas; tipos regenerados desde OpenAPI. Añadir un reporte
al catálogo no requiere agregar una página ni modificar los exportadores.

## 7. Auditoría

Solo lecturas. No modifica entidades de negocio ni inserta registros por
consultar R17. No crea copias de las bitácoras en una tabla nueva.

## 8. Criterios de aceptación

- [x] Los tres reportes filtran y totalizan correctamente, también sin resultados.
- [x] R05 evita doble conteo de edificios/unidades y separa monedas.
- [x] R16 respeta los límites hoy/hoy+N y omite vencimientos nulos.
- [x] R17 no expone campos excluidos ni permite acceso con roles no autorizados.
- [x] Todos los roles autenticados acceden a R05/R16 en catálogo, JSON y archivos;
      R17 responde 403 para cualquier rol distinto de administrador.
- [x] JSON pagina de forma estable; sus totales no cambian al pasar de página.
- [x] Con 60 filas, página 2 materializa solo 25 detalles, conserva count=60 y
      totales completos; Excel/PDF incluyen las 60. Con 5,001 filas no se
      materializan detalles para la descarga y se devuelve el error del límite.
- [x] Excel y PDF incluyen todas las filas filtradas dentro del límite, título,
      filtros, fecha, autor y totales; Excel congela encabezados y formatea celdas.
- [x] PDF repite encabezados/pie y numera páginas; horizontal con más de 6 columnas.
- [x] Un texto con fórmula se exporta literalmente; HTML del usuario queda escapado.
- [ ] La pantalla construye filtros y columnas desde el catálogo y maneja errores.
- [x] Pasan ruff, pytest con PostgreSQL, lint, typecheck y build del frontend.
- [ ] Revisión visual de PDF multipágina y apertura del XLSX de muestra.

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Selector | Filtros combinados, inactivos, dos monedas, edificio con unidades |
| Servicio | 60 filas: página de 25 con totales de 60 y exportación de 60; vacío; 5,001 rechazadas antes de cargar detalle |
| Exportador | Celdas numéricas, texto con fórmula, fechas y PDF multipágina |
| API | Permisos iguales en catálogo, JSON y ambos archivos; parámetros inválidos |
| Frontend/manual | Cambiar filtros reinicia página; descargar con sesión vigente |

## 10. Decisiones y alternativas descartadas

- Tres reportes existentes validan la infraestructura sin esperar compras o IA.
- Se conserva el contrato genérico para evitar un exportador y pantalla por reporte.
- Los límites y la separación por moneda acotan el primer incremento de
  `docs/reportes.md`; se incluyeron en la revisión y aprobación del PR #61.
- Elegir R16/R17 usa el margen del catálogo de 18 reportes. La selección final
  de al menos 15 se acuerda con el equipo, sin descartar reportes unilateralmente.

## 11. Trabajo con agentes de IA

Se utilizó Codex para contrastar el catálogo de reportes, los modelos y las
convenciones con el issue #24 y redactar el borrador. Nathaly explicó que esta
etapa define lo que se hará antes de implementar y trasladó los comentarios
del equipo para corregir la propuesta.

Las correcciones precisan el doble conteo de propiedades/unidades, los totales
por moneda y los permisos. También separan el resumen SQL y la selección de
25 filas para JSON del resultado completo para Excel/PDF, con límite de 5,000.
La entrega contiene especificación, sin implementación ni pruebas de aplicación.
AngelOvalle29 aprobó el PR #61 sobre `dc258e5`; la implementación sigue pendiente.

### Implementación local del 2026-10-31

Se implementaron los tres reportes, los exportadores compartidos, las rutas
autenticadas y la pantalla `/reportes`, en `feature/016-capa-generica-reportes`.
Se conserva el registro anterior como evidencia de la etapa de especificación.
La explicación para revisión y defensa está en
[`docs/016-implementacion-reportes.md`](../docs/016-implementacion-reportes.md).

Se utilizaron consultas SQL separadas para el resumen y el detalle paginado,
sin migraciones ni dependencias distintas de openpyxl/WeasyPrint ya aprobadas.
Los tipos del frontend se regeneraron desde OpenAPI. Los importes JSON se
conservan como cadenas decimales exactas. Se ajustó el ancho de las columnas
del PDF y el ajuste de texto de Excel tras revisar muestras ficticias.

La revisión manual del flujo en navegador queda pendiente porque los servicios
de control del navegador y aplicaciones de esta sesión no están disponibles.
La implementación no se considera aprobada ni fusionada; requiere revisión
del estudiante, commit propio y revisión de otro integrante mediante PR.

Verificación final: 587 pruebas pasaron con PostgreSQL (30 nuevas de reportes),
ruff y formato correctos, sin migraciones nuevas, esquema OpenAPI sin avisos,
y lint/typecheck/build del frontend correctos. Las muestras XLSX se abrieron
mediante bibliotecas y se renderizaron; su apertura en Microsoft Excel queda
pendiente junto con la revisión manual del navegador.

### Integración autorizada del 2026-11-01

Nathaly autorizó expresamente que Codex ejecute commit, push y apertura del PR
con su configuración Git. Se integró `develop` sobre `769df79`, conservando las
rutas y el menú del equipo y regenerando tipos desde OpenAPI. Se corrigieron
dos colisiones de nombres en el esquema de proveedores, sin cambiar su JSON;
ese ajuste requiere revisión del integrante C.

La versión integrada pasó **652 pruebas** con PostgreSQL, ruff, formato,
comprobación de migraciones, OpenAPI sin avisos y lint/typecheck/build.
Se presenta como PR en borrador: falta navegador, comprensión del estudiante
y aprobación real de otro integrante antes de fusionar.

### Ajustes tras la revisión de Marco

Se atienden los cuatro comentarios no bloqueantes del PR #77: fechas de R16
con el formateador común (sin desplazar fechas ISO por UTC), etiquetas de
opciones desde los metadatos, separadores decimales y etiquetas de totales,
y un solo bloque para los errores de filtros. `ReporteDemasiadoGrande` pasa
a `exceptions.py` y se documentan los dos servicios de obtención del reporte.
La guía manual registra las pruebas parciales de Marco y el requisito de
bibliotecas nativas para ejecutar las pruebas PDF en Windows. No se marca
como completa la validación de navegador pendiente ni la revisión de C.
