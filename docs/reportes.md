# Reportería y Business Intelligence

El enunciado pide **15 reportes** con filtros y agregaciones, **cada uno
exportable a Excel y a PDF**, más integración con Power BI.

---

## 1. Diseño de la capa de reportes

```
Filtros tipados  →  selector  →  servicio del reporte  →  exportador
   (dataclass)      (consulta)    (estructura de datos)   (Excel | PDF)
```

Cada reporte devuelve una estructura uniforme:

```python
@dataclass
class Reporte:
    titulo: str
    subtitulo: str              # filtros aplicados, en texto legible
    generado_en: datetime
    generado_por: str
    columnas: list[Columna]     # nombre, tipo, formato, alineación
    filas: list[dict]
    totales: dict               # agregaciones de pie de tabla
    agrupamientos: list[Grupo]  # subtotales, opcional
```

Los exportadores son **genéricos**: reciben un `Reporte` y producen el archivo.
Agregar un reporte nuevo no debe requerir tocar los exportadores.

**Endpoints:**

```
GET /api/v1/reportes/                       lista de reportes disponibles
GET /api/v1/reportes/{slug}/                datos en JSON, para el frontend
GET /api/v1/reportes/{slug}/excel/          descarga .xlsx
GET /api/v1/reportes/{slug}/pdf/            descarga .pdf
```

Los filtros viajan como parámetros de consulta. Los reportes pesados se generan
en Celery y se notifica al usuario cuando el archivo está listo.

**Filtros comunes a casi todos:** rango de fechas, país, ciudad, moneda de
presentación (con conversión por tipo de cambio) y agente.

---

## 2. Catálogo de reportes

### Comerciales

**R01 · Ventas por período**
Contratos de venta en un rango. Filtros: fecha, país, ciudad, agente, tipo de
propiedad, modalidad. Agrupa por mes y país. Totales: cantidad, monto bruto,
descuentos, monto neto, comisiones.

**R02 · Desempeño por agente**
Por agente: cotizaciones emitidas, aprobadas, contratos cerrados, tasa de
conversión, monto vendido y comisión generada. Filtros: fecha, país.

**R03 · Embudo de cotizaciones**
Cotizaciones por estado, con tiempo promedio en cada etapa y tasa de conversión
entre etapas. Filtros: fecha, agente, país, rango de monto.

**R04 · Ranking de clientes**
Clientes ordenados por monto total transado. Columnas: contratos de venta,
arrendamientos vigentes, monto acumulado, saldo pendiente. Filtros: fecha, país,
tipo de cliente.

### Inventario de propiedades

**R05 · Inventario disponible**
Propiedades y unidades en estado `DISPONIBLE`. Filtros: país, ciudad, tipo,
rango de precio, rango de área. Agrupa por ciudad y tipo. Totales: cantidad,
valor de lista, área total.

**R06 · Propiedades por estado**
Distribución del portafolio completo por estado y tipo. Filtros: país, fecha de
corte. Incluye antigüedad promedio en cada estado.

**R07 · Rotación de inventario**
Días transcurridos entre la adquisición y la venta de cada propiedad vendida.
Filtros: fecha, país, tipo. Totales: promedio, mediana, mínimo y máximo.

**R08 · Evolución de avalúos**
Historial de avalúos por propiedad con variación porcentual entre valuaciones.
Filtros: propiedad, país, rango de fechas.

### Financieros

**R09 · Rentabilidad por propiedad**
Costo total de adquisición más construcción, frente al precio de venta.
Columnas: costo de compra, gastos legales, impuestos, inversión en
construcción, precio de venta, utilidad y margen porcentual. Filtros: fecha de
venta, país, tipo.

**R10 · Estado de cuenta de clientes**
Cuotas por cliente: pagadas, pendientes, vencidas, saldo. Filtros: cliente,
rango de fechas, estado, agente.

**R11 · Morosidad**
Cuotas vencidas y pagos de renta vencidos, clasificados por antigüedad de la
mora (1–30, 31–60, 61–90, más de 90 días). Filtros: país, agente, rango de
monto. Totales por tramo.

**R12 · Flujo de ingresos**
Ingresos cobrados por mes, separando ventas de arrendamientos. Filtros: rango de
fechas, país, moneda de presentación. Agrupa por mes y origen.

**R13 · Compras a proveedores**
Adquisiciones por proveedor y período. Columnas: cantidad de propiedades, monto,
gastos legales, impuestos, costo total. Filtros: fecha, proveedor, país.

### Arrendamientos

**R14 · Ocupación de arrendamientos**
Tasa de ocupación por propiedad y por ciudad: unidades totales, arrendadas,
disponibles, porcentaje de ocupación e ingreso mensual recurrente. Filtros:
fecha de corte, país, ciudad, tipo de propiedad.

### Construcción

**R15 · Avance y presupuesto de obra**
Por proyecto: presupuesto, pagado a la fecha, saldo, porcentaje de avance físico
frente a porcentaje pagado, y desviación de fechas. Filtros: constructora,
estado, país, rango de fechas.

### Operativos

**R16 · Documentos por vencer**
Documentos oficiales con vencimiento en los próximos N días, o ya vencidos.
Filtros: tipo de documento, país, días de anticipación.

**R17 · Bitácora de auditoría**
Operaciones registradas por usuario, entidad y acción. Filtros: usuario,
entidad, acción, rango de fechas.

**R18 · Uso del agente de IA**
Consultas por día, modo público frente a interno, tasa de éxito, tiempo
promedio de respuesta, tokens consumidos y preguntas más frecuentes. Filtros:
rango de fechas, modo, usuario.

> Son 18 reportes para un requisito de 15. El margen cubre que alguno se
> descarte durante la implementación.

---

## 3. Exportadores

### Excel (openpyxl)

- Encabezado con logotipo, título, filtros aplicados y fecha de generación.
- Fila de encabezados con formato fijo y paneles congelados.
- Formato numérico por tipo de columna: moneda con dos decimales, porcentajes,
  fechas en formato local.
- Fila de totales en negrita al pie.
- Subtotales por grupo cuando el reporte los define.
- Ancho de columna ajustado al contenido.
- Nombre del archivo: `R05_inventario_disponible_2026-10-08.xlsx`.

### PDF (WeasyPrint)

- Plantilla HTML compartida por todos los reportes, con hoja de estilo propia.
- Encabezado y pie repetidos en cada página, con numeración.
- Orientación horizontal cuando el reporte tiene más de 6 columnas.
- Los filtros aplicados se imprimen bajo el título, para que el documento sea
  autoexplicativo.

---

## 4. Integración con Power BI

### Esquema `bi`

Se crea un esquema aparte en la misma base PostgreSQL, con **vistas** en modelo
estrella. Power BI se conecta a estas vistas, nunca a las tablas operativas.
Esto aísla el modelo analítico de los cambios en el esquema transaccional.

**Tablas de hechos:**

| Vista | Grano |
|---|---|
| `bi.hechos_ventas` | Un contrato de venta |
| `bi.hechos_cobros` | Un pago recibido, de cuota o de renta |
| `bi.hechos_arrendamientos` | Un mes de contrato de arrendamiento vigente |
| `bi.hechos_compras` | Un contrato de compra |
| `bi.hechos_construccion` | Un pago a constructora |

**Tablas de dimensión:**

| Vista | Contenido |
|---|---|
| `bi.dim_tiempo` | Fecha, día, mes, trimestre, año, nombre del mes |
| `bi.dim_geografia` | País, región, ciudad |
| `bi.dim_propiedad` | Propiedad, tipo, área, estado actual |
| `bi.dim_cliente` | Cliente, tipo, país, antigüedad |
| `bi.dim_agente` | Agente, país, fecha de ingreso |
| `bi.dim_constructora` | Constructora, país, calificación |

**Reglas de las vistas:**
- Todos los montos se exponen además en USD (`monto_usd`), convertidos con el
  tipo de cambio vigente a la fecha del hecho. Así Power BI consolida sin
  lógica adicional.
- Toda vista de hechos incluye `fecha_id` para unir con `bi.dim_tiempo`.
- Se crea un usuario de base de datos `powerbi_reader` con permiso de solo
  lectura **únicamente** sobre el esquema `bi`.

### Conexión

- Conector nativo de PostgreSQL en Power BI Desktop.
- Modo **DirectQuery** para los tableros operativos, **Import** con
  actualización programada para los históricos.
- Credenciales del usuario de solo lectura, nunca las del sistema.

### Tableros propuestos

1. **Comercial.** Ventas por mes y país, embudo de cotizaciones, ranking de
   agentes, ticket promedio.
2. **Portafolio.** Mapa de propiedades, distribución por estado y tipo,
   inventario disponible, rotación.
3. **Financiero.** Flujo de ingresos, morosidad por tramo, rentabilidad por
   propiedad, ingreso recurrente de arrendamientos.
4. **Construcción.** Avance frente a presupuesto por proyecto, desviación de
   fechas, pagos por constructora.

### Evidencia para la entrega

- Archivo `.pbix` versionado en `docs/powerbi/`.
- Capturas de los tableros en el manual técnico.
- Script SQL de creación del esquema `bi` versionado como migración.
