# Power BI

Power BI lee cuatro vistas del esquema `bi` de PostgreSQL, en modelo estrella
(spec 021, §4). Las crea la migración `reportes/0001_vistas_bi`, así que existen
en toda base migrada: local y Neon.

| Vista | Grano | Clave |
|---|---|---|
| `bi.dim_tiempo` | Un día | `fecha_id` (entero AAAAMMDD) |
| `bi.dim_geografia` | Una ciudad, con su país | `ciudad_id` |
| `bi.dim_propiedad` | Un bien: propiedad sin unidades o unidad de un edificio | `bien_clave` (`PROPIEDAD-12`, `UNIDAD-5`) |
| `bi.hechos_ventas` | Un contrato de venta no anulado | `contrato_id` |

Relaciones, todas de muchos a uno desde `hechos_ventas`:
- `hechos_ventas.fecha_id` → `dim_tiempo.fecha_id`
- `hechos_ventas.bien_clave` → `dim_propiedad.bien_clave`
- `hechos_ventas.ciudad_id` → `dim_geografia.ciudad_id`

Los montos van en su moneda (`neto`, con `moneda`) y en dólares (`neto_usd`),
con la tasa guardada al firmar. Para sumar entre monedas use `neto_usd`. Estado
y ciudad de la propiedad son los actuales, no los de la fecha de la venta.

## Conectar Power BI Desktop a Neon

1. **Rol de solo lectura:** el administrador de la base corre
   `crear_lector.sql` en el SQL Editor de Neon, con una contraseña propia, y
   la pasa por privado. Una sola vez.
2. En Power BI Desktop: *Obtener datos → Base de datos PostgreSQL*.
   - **Servidor:** el host de Neon (`ep-…neon.tech`), sin `postgres://` ni puerto.
   - **Base de datos:** la de `DATABASE_URL` en Render (Neon la llama `neondb` por defecto).
   - **Modo:** Importar.
   - **Credenciales:** *Base de datos*, usuario `powerbi_reader`.
   - **Cifrado:** deje la conexión cifrada (SSL). Neon la exige; no se desactiva
     la validación del certificado para que funcione.
3. Marque las cuatro vistas de `bi` y cárguelas.
4. Revise las tres relaciones de arriba en la vista de modelo.

Neon suspende la base cuando no se usa: la primera actualización puede tardar
unos segundos mientras despierta.

El tablero se guarda en `docs/powerbi/inmobiliaria.pbix`, con una página
comercial: ventas por mes, país, ciudad y tipo de propiedad, en USD y por
cantidad de contratos.

## Construir y comprobar la página comercial

1. Confirmar las tres relaciones anteriores, activas, muchos-a-uno y con
   filtro desde dimensión hacia hechos. No relacionar también las dimensiones
   entre sí: una segunda ruta puede introducir ambigüedad.
2. Crear las tres medidas de `medidas.dax`; formatear Ventas USD y Ticket
   promedio USD con dos decimales, y Contratos como entero.
3. Crear una página **Comercial** con título, tarjetas de ventas/contratos/ticket,
   columnas de ventas por `dim_tiempo.anio_mes`, barras por país y por tipo,
   y segmentadores de año, país y ciudad. `anio_mes` en formato AAAA-MM ordena
   cronológicamente; no ordenar meses solo por nombre.
4. Ejecutar `conciliacion.sql` y comparar las tarjetas y los cortes por mes,
   país y tipo con los mismos filtros. Las ventas sin dimensión deben ser cero.
5. Actualizar desde Desktop, guardar y volver a abrir el `.pbix`. No incluir
   contraseñas en consultas M ni capturas. El archivo contiene datos importados:
   usar únicamente los datos ficticios de demostración para versionarlo.
6. Capturar página y modelo sin credenciales visibles. Registrar origen,
   fecha de actualización, cifras conciliadas y el resultado de acceso
   denegado a tablas operativas. No dar por comprobada Neon con una fuente CSV.

El conector nativo ya incluye Npgsql en Desktop reciente; no se instala un
driver de terceros. Referencia: [conector PostgreSQL de Microsoft](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

## Estado de la evidencia del bloque D (registro inicial)

El 2026-11-02 las cuatro vistas ya estaban integradas por A. Se prepararon
medidas y conciliación y se inició la instalación oficial de Desktop con
autorización de Nathaly. El `.pbix`, las capturas y la prueba de conexión a
Neon no se consideran terminados hasta abrirlos, actualizarlos y comprobarlos
realmente. El acceso de `powerbi_reader` se coordina por privado con Douglas.

### Conexión y archivo guardado por Nathaly

Nathaly recibió por privado el acceso de Douglas, conectó Desktop a Neon con
Importar y cargó las cuatro vistas. Guardó `docs/powerbi/inmobiliaria.pbix`.
Douglas informó que ya comprobó en producción los permisos del lector;
esa comprobación se atribuye a él, no a una prueba SQL ejecutada por Codex.

Se inspeccionó el archivo guardado: contiene cuatro tablas (`bi dim_tiempo`,
`bi dim_geografia`, `bi dim_propiedad`, `bi hechos_ventas`) y una página sin
visuales. Falta corregir/comprobar las relaciones, crear medidas y gráficos,
actualizar y conciliar el tablero. Las medidas de `medidas.dax` usan el nombre
real de la tabla importada, con su prefijo y espacio entre comillas simples.

Para editar de forma programática sin modificar directamente el binario PBIX,
guardar una copia como Proyecto de Power BI (`.pbip`) en esta misma carpeta,
cerrar esa copia en Desktop y editar sus definiciones. El proyecto conserva
el modelo y las consultas en archivos de texto; luego se abre, valida y guarda
el `.pbix` final desde Desktop. Los archivos locales de caché y configuración
de `.pbi` se excluyen de Git.
Referencia: [proyectos editables de Power BI](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview).

### Página comercial preparada en PBIP

Se guardó una copia de respaldo local antes de editar el proyecto. Se
corrigieron las relaciones automáticas entre las vistas: las tres salen de
`bi hechos_ventas` (muchos) hacia tiempo, geografía y propiedad (uno), activas
y con filtro unidireccional desde las dimensiones. Se conservan las tablas
locales de fecha que Desktop creó para su función de fecha automática; no
intervienen en los campos usados por este tablero.

El modelo incorpora Ventas USD, Contratos y Ticket promedio USD, con formato
monetario e identidades sin suma automática. La página **Comercial** contiene
las tres tarjetas, ventas por mes, país y tipo, y filtros de año, país y ciudad.
No se suman `neto` de monedas distintas: los gráficos usan la medida USD.

Validación de los archivos preparados: el modelo se deserializa correctamente
con Microsoft.AnalysisServices 19.118.3, con cuatro tablas BI, tres medidas y
tres relaciones de estrella. Los 16 documentos de definición PBIR (incluidos
los doce visuales) cumplen sus esquemas oficiales de Microsoft. Estas son
comprobaciones de estructura, no una prueba de ejecución de DAX, de cifras
en producción ni de presentación final en Desktop.

Abrir **inmobiliaria.pbip** para cargar estos cambios. El `.pbix` original
todavía contiene la página vacía: solo reemplazarlo desde Desktop después de
verificar que los gráficos muestran datos, que los filtros cambian las cifras,
que la actualización desde Neon funciona y que los totales concilian.
Luego guardar como `inmobiliaria.pbix` y aportar capturas del tablero/modelo.

### Guardado final y prueba visual

Nathaly abrió el PBIP preparado, actualizó desde Desktop, verificó selecciones
de meses y guardó el PBIX final. El archivo contiene los doce visuales de la
página Comercial. Se incorporan las capturas originales a `capturas/` y el
detalle de resultados a [evidencia.md](evidencia.md). La conciliación SQL de
cifras exactas en producción queda explícitamente para revisión; no se
sustituye por comprobar tarjetas con importes abreviados.
