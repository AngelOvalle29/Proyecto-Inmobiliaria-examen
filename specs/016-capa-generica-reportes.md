# 016 · Capa genérica de reportes y primeras exportaciones

| Campo | Valor |
|---|---|
| **Número** | 016 |
| **Estado** | Borrador |
| **Autor** | Nathaly Saraí Reyes Cifuentes (rol D), con apoyo de Codex |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `reportes`; lecturas de `catalogo`, `core` y `auditoria`; frontend |
| **Rama** | Documentación: `docs/015-016-bloque-d`; implementación propuesta: `feature/016-capa-generica-reportes` |
| **Pull request** | Pendiente; avance del issue [#24](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/24) |

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

Todas las reglas nuevas son propuestas para revisión, no acuerdos ya aprobados.

1. Cada reporte declara slug, título, columnas, filtros y roles. Un slug
   desconocido devuelve 404. El catálogo solo muestra reportes autorizados y
   las rutas de datos y descarga vuelven a comprobar el permiso.
2. Permisos propuestos: R05/R16 para `ADMINISTRADOR` y `GERENTE`; R17 solo
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
   página visible como fuente. Límite síncrono propuesto: 5,000 filas; si se
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

Firmas propuestas, implementadas con anotaciones y docstrings:

- `listar_reportes(*, usuario: AbstractBaseUser) -> list[dict]`: catálogo autorizado.
- `seleccionar_inventario(*, filtros: FiltrosInventario) -> QuerySet[dict]`:
  lecturas R05 con proyecciones compatibles de propiedades y unidades.
- `seleccionar_vencimientos(*, filtros: FiltrosVencimientos) -> QuerySet`: lecturas R16.
- `seleccionar_bitacora(*, filtros: FiltrosBitacora) -> QuerySet`: lecturas R17.
- `construir_reporte(*, slug: str, filtros: dict, usuario: AbstractBaseUser) -> Reporte`:
  adapta datos y agregaciones; no hace consultas fuera de los selectores.
- `exportar_excel(reporte: Reporte) -> bytes` y `exportar_pdf(reporte: Reporte) -> bytes`:
  solo presentación, sin consultar modelos.

Frontend: una ruta `/reportes`, formulario generado por metadatos, tabla paginada
y descargas autenticadas; tipos regenerados desde OpenAPI. Añadir un reporte
al catálogo no requiere agregar una página ni modificar los exportadores.

## 7. Auditoría

Solo lecturas. No modifica entidades de negocio ni inserta registros por
consultar R17. No crea copias de las bitácoras en una tabla nueva.

## 8. Criterios de aceptación

- [ ] Los tres reportes filtran y totalizan correctamente, también sin resultados.
- [ ] R05 evita doble conteo de edificios/unidades y separa monedas.
- [ ] R16 respeta los límites hoy/hoy+N y omite vencimientos nulos.
- [ ] R17 no expone campos excluidos ni permite acceso con roles no autorizados.
- [ ] JSON pagina de forma estable; sus totales no cambian al pasar de página.
- [ ] Excel y PDF incluyen todas las filas filtradas dentro del límite, título,
      filtros, fecha, autor y totales; Excel congela encabezados y formatea celdas.
- [ ] PDF repite encabezados/pie y numera páginas; horizontal con más de 6 columnas.
- [ ] Un texto con fórmula se exporta literalmente; HTML del usuario queda escapado.
- [ ] La pantalla construye filtros y columnas desde el catálogo y maneja errores.
- [ ] Pasan ruff, pytest con PostgreSQL, lint, typecheck y build del frontend.
- [ ] Revisión visual de PDF multipágina y apertura del XLSX de muestra.

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Selector | Filtros combinados, inactivos, dos monedas, edificio con unidades |
| Servicio | Totales de todas las páginas, vacío y límite de exportación |
| Exportador | Celdas numéricas, texto con fórmula, fechas y PDF multipágina |
| API | Permisos iguales en catálogo, JSON y ambos archivos; parámetros inválidos |
| Frontend/manual | Cambiar filtros reinicia página; descargar con sesión vigente |

## 10. Decisiones y alternativas descartadas

- Tres reportes existentes validan la infraestructura sin esperar compras o IA.
- Se conserva el contrato genérico para evitar un exportador y pantalla por reporte.
- Los límites y la separación por moneda hacen explícitas las limitaciones;
  deben aprobarse antes de implementar porque acotan el diseño de `docs/reportes.md`.
- Elegir R16/R17 usa el margen del catálogo de 18 reportes. La selección final
  de al menos 15 se acuerda con el equipo, sin descartar reportes unilateralmente.

## 11. Trabajo con agentes de IA

Sesión 2026-10-31: Codex comparó el catálogo, modelos y convenciones con el
issue #24 y redactó este borrador. No se implementó ni probó código. Nathaly
completa su revisión y los ajustes acordados antes de hacer su propio commit.

Revisión técnica posterior de Codex, solicitada por Nathaly: se precisaron la
identidad de filas mixtas, la paginación antes de cargar filas, el origen de
montos/áreas y la moneda exigida para comparar precios. Nathaly autorizó al
agente a ejecutar el commit de documentación; la aprobación del equipo sigue
pendiente.
