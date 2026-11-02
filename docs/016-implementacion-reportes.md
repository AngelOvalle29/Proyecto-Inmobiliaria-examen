# Uso y explicación de los reportes iniciales

Implementa la spec 016 aprobada en el PR #61. El trabajo está en la rama
`feature/016-capa-generica-reportes`, pendiente de revisión del estudiante y PR.
No crea tablas ni migraciones. Este incremento no cierra el issue #24:
implementa tres reportes de los quince mínimos y no incluye Power BI.

## Cómo usarlo

1. Instalar `backend/requirements/dev.txt` y ejecutar el backend con PostgreSQL.
   En Windows se recomienda el contenedor del backend para las bibliotecas
   nativas de WeasyPrint; el Dockerfile ya instala Pango y Cairo.
2. Iniciar el frontend con `npm run dev` e ingresar con una cuenta del sistema.
3. Abrir **Reportes** (`/reportes`) y elegir un reporte.
4. Elegir filtros y pulsar **Aplicar filtros**. La vista previa pagina de 25
   en 25; los totales describen todo el resultado filtrado.
5. Pulsar **Descargar Excel** o **Descargar PDF**. El archivo incluye todos
   los resultados del filtro aplicado, aunque se esté viendo otra página.
   Con más de 5,000 filas hay que acotar los filtros.

| Reporte | Acceso | Filtros |
|---|---|---|
| R05 Inventario disponible | Todos los roles autenticados | País, ciudad, tipo, moneda ISO, precio mínimo/máximo, área mínima/máxima |
| R16 Documentos por vencer | Todos los roles autenticados | Tipo de documento, país, anticipación de 0 a 365 días (30 por defecto) |
| R17 Bitácora de auditoría | Administrador | Usuario ID, entidad, acción, fechas ISO desde/hasta |

R05 exige moneda al filtrar por precio. Conserva la moneda original y no
suma monedas diferentes. Los edificios aportan sus unidades disponibles;
no se cuenta además el precio del edificio. R16 incluye documentos vencidos
y documentos que vencen entre hoy y hoy más la anticipación, inclusive.
R17 excluye IP, user-agent y los JSON de valores anteriores/nuevos.

Los filtros de una descarga son los aplicados en la última consulta.
**Limpiar** restablece los filtros y la primera página. Cambiar de reporte
también restablece el formulario. Las opciones de relaciones se paginan.

## API

Todas las rutas requieren JWT:

```text
GET /api/v1/reportes/
GET /api/v1/reportes/inventario-disponible/?moneda=GTQ&page=2
GET /api/v1/reportes/documentos-por-vencer/?dias_anticipacion=30
GET /api/v1/reportes/bitacora-auditoria/?fecha_desde=2026-10-01&fecha_hasta=2026-10-31
GET /api/v1/reportes/{slug}/excel/
GET /api/v1/reportes/{slug}/pdf/
```

El catálogo devuelve filtros, opciones, columnas y roles; las descargas
comprueban nuevamente el permiso. Los parámetros desconocidos, repetidos
o inválidos responden `400 VALIDACION`. Las descargas no admiten `page`.
Un reporte demasiado grande responde `400 REPORTE_DEMASIADO_GRANDE`.
Una página inexistente o un slug desconocido responde 404.

## Qué explicar en la defensa

- `estructuras.py` define dataclasses en memoria. `Reporte.filas` recibe una
  página para JSON o todo el resultado permitido para exportar.
- `catalogo.py` declara el contrato de cada reporte. La pantalla lee sus
  metadatos para construir filtros y columnas; los exportadores no conocen
  los nombres de los tres reportes.
- `selectors.py` consulta y agrega en PostgreSQL. R05 hace `UNION ALL` de
  propiedades y unidades con orden `(origen, id)`. El origen evita confundir
  una propiedad con una unidad que tenga el mismo ID.
- El resumen se calcula antes de obtener detalles. Por eso cambiar de página
  no modifica los totales, y se rechaza una descarga grande sin cargarla.
- `services.py` comprueba permisos y elige 25 filas o el resultado completo.
  `construir_reporte` recibe datos listos y no consulta modelos.
- `serializers.py` valida parámetros; `views.py` transforma el resultado al
  contrato HTTP. Los decimales se conservan como texto exacto en JSON.
- `exportadores.py` usa openpyxl para Excel y WeasyPrint para PDF. Las celdas
  numéricas y fechas conservan su tipo; el texto que comienza con `=` se
  escribe literalmente. La plantilla escapa HTML y bloquea recursos externos.
- El último día de un rango de auditoría se incluye usando como límite
  exclusivo la medianoche del día siguiente en Guatemala. Esto incluye sus
  horas completas, aunque PostgreSQL almacene la fecha en UTC.
- TanStack Query administra las consultas y las descargas autenticadas.
  Los tipos se generan desde OpenAPI; no se editan manualmente.

## Validación y revisión pendiente

Se verificaron PostgreSQL, permisos de los cinco roles en catálogo/JSON/Excel/PDF,
límites de vencimientos, rangos, paginación SQL y rechazo de descargas grandes.
Resultado definitivo: **587 pruebas pasaron**, incluidas 30 pruebas nuevas de
reportes. También pasaron `ruff check .`, `ruff format --check .`,
`makemigrations --check --dry-run`, la generación OpenAPI con `--fail-on-warn`,
`npm run lint`, `npm run typecheck` y `npm run build`. No hay migraciones nuevas.
La compilación avisa del tamaño del paquete JavaScript principal (671 kB antes
de gzip); no impide generar el frontend.

Se generaron muestras ficticias en `reportes_generados/` (carpeta ignorada por
Git). Se revisaron páginas de PDF horizontal y vertical, encabezados repetidos,
numeración y totales; los XLSX se abrieron con openpyxl y Artifact Tool y se
renderizaron sus hojas. No se pudo abrir Microsoft Excel ni un navegador:
el servicio de control de aplicaciones de esta sesión no está disponible.
La comprobación manual de la pantalla y de descargas desde una sesión del
navegador queda pendiente; la compilación y los controles estáticos sí pasan.

Antes del commit, el estudiante debe revisar y comprender el código; después
se abre el PR hacia `develop` y otro integrante lo aprueba, según las convenciones.

### Revalidación del 2026-11-01

Se repitió la suite completa con PostgreSQL: **587 pruebas pasaron en 57.41 s**.
Pasaron `ruff check .`, `ruff format --check .`, la comprobación de migraciones,
OpenAPI con `--fail-on-warn`, `npm.cmd run lint`, `npm.cmd run typecheck` y
`npm.cmd run build`. Se mantiene el aviso de tamaño del paquete principal.

La imagen local de pruebas estaba desactualizada: faltaban paquetes Python y
bibliotecas nativas de PDF. Se instalaron dentro de un contenedor de validación;
el Dockerfile del proyecto ya declara Pango/Cairo. Un error de lectura del
montaje de OneDrive se evitó copiando el backend al contenedor antes de probar.
No se cambió el código de aplicación para resolver esos problemas del entorno.

Se intentó recuperar el control de aplicaciones y navegador: el servicio nativo
devolvió `native pipe is unavailable` y el servicio de navegador
`browser access host is unavailable`. La prueba del flujo visual continúa
pendiente. La guía [`016-revision-y-pr.md`](016-revision-y-pr.md) contiene el
recorrido manual, la explicación por capas y el borrador de descripción del PR.

A petición de la estudiante se preparó la spec 021 para revisión del equipo,
sin implementarla. Debe presentarse en un PR de documentación separado de la
implementación de la 016. Nathaly autorizó posteriormente que Codex ejecute
commit, push y apertura del PR con su configuración de Git. Sigue pendiente
la revisión del estudiante y la aprobación de otro integrante para fusionar.

### Integración con develop y preparación del PR

Tras la autorización se creó el commit de implementación con la identidad Git
de Nathaly y se integró `origin/develop` (`769df79`). Se conservaron las rutas
de reportes, compras y construcción, y las opciones actuales del menú.
Los tipos del frontend se regeneraron desde OpenAPI, sin resolverlos a mano.

La integración detectó dos avisos del esquema de proveedores: nombres de
serializer de ciudad duplicados con CRM y enum de tipo sin nombre explícito.
Se dio un nombre propio al resumen de ciudad de proveedor y se declaró
`TipoProveedorEnum`. No cambia la respuesta JSON; C debe revisar el ajuste.

Validación de la versión integrada: **652 pruebas pasaron en 97.03 s**,
ruff y formato correctos, sin cambios de migraciones y OpenAPI sin avisos.
Pasaron lint, typecheck y build del frontend. El paquete principal integrado
es de 695.09 kB antes de gzip y conserva el aviso de tamaño.
El PR se prepara como borrador por la validación de navegador pendiente.

### Revisión de presentación y organización

Se corrigieron los comentarios de Marco sobre formato de fechas, etiquetas
de opciones/totales y error de filtros duplicado. La excepción de límite se
movió a `exceptions.py` y se añadieron docstrings a los servicios de consulta
y exportación. La versión corregida pasó **652 pruebas en 145.78 s**, ruff,
formato, migraciones, OpenAPI sin avisos y lint/typecheck/build del frontend.
El paquete principal quedó en 695.55 kB antes de gzip (209.59 kB gzip).
El servicio de navegador sigue sin conexión; las pruebas parciales de Marco
y las comprobaciones todavía pendientes se registran en la guía de revisión.
