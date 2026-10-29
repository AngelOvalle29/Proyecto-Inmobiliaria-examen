# Modelo de datos

El enunciado pide entre 12 y 15 entidades núcleo. Este modelo define **25
entidades de negocio** más 4 de soporte, para tener margen y para que el dominio
quede completo.

Las entidades marcadas con ★ son las que se presentan como núcleo en la defensa.

---

## 1. Catálogos base — app `core`

### Pais
`id` · `nombre` · `codigo_iso` · `moneda_principal` (FK Moneda) · `activo`

### Ciudad
`id` · `nombre` · `pais` (FK) · `region` · `activo`

### Moneda
`id` · `codigo` (GTQ, USD, MXN, COP…) · `nombre` · `simbolo` · `activo`

### TipoCambio
`id` · `moneda_origen` (FK) · `moneda_destino` (FK) · `tasa` · `fecha`
*Regla:* único por combinación de monedas y fecha. Todo monto se guarda en su
moneda original; la conversión a USD se hace al momento de reportar, usando la
tasa vigente a la fecha de la transacción.

---

## 2. Propiedades — app `catalogo`

### TipoPropiedad ★
`id` · `nombre` (Apartamento, Terreno, Casa, Hotel, Bodega, Restaurante,
Gasolinera) · `descripcion` · `requiere_unidades` (bool) · `activo`

### Propiedad ★
`id` · `codigo` (único, generado) · `nombre` · `tipo` (FK) · `ciudad` (FK) ·
`direccion` · `latitud` · `longitud` · `area_m2` · `area_construida_m2` ·
`estado` (enum) · `precio_lista` · `moneda` (FK) · `es_publica` (bool) ·
`descripcion` · `activo` (sin `fecha_registro`: lo cubre `creado_en`, spec 003)

**Estados:** `EN_NEGOCIACION`, `ADQUIRIDA`, `EN_CONSTRUCCION`, `DISPONIBLE`,
`RESERVADA`, `VENDIDA`, `ARRENDADA`, `BAJA`.

*Reglas:*
- `es_publica` controla qué ve el agente de IA en modo público.
- Una propiedad en `VENDIDA` no admite nuevos contratos de venta.
- El cambio de estado siempre genera un `EventoPropiedad`.

### Unidad ★
Apartamentos o locales dentro de una propiedad tipo edificio.
`id` · `propiedad` (FK) · `codigo` · `nivel` · `area_m2` · `habitaciones` ·
`banos` · `estado` (mismo enum) · `precio_lista` · `moneda` (FK) · `activo`

### Amenidad
`id` · `nombre` · `icono` — relación muchos a muchos con Propiedad.

### Avaluo ★
`id` · `propiedad` (FK) · `fecha` · `valor` · `moneda` (FK) · `perito` ·
`metodologia` · `documento` (FK DocumentoOficial, opcional) · `observaciones`

*Regla:* el historial de avalúos permite medir plusvalía en el tiempo. No se
borran, se agregan.

### DocumentoOficial ★
`id` · `propiedad` (FK, opcional) · `contrato_venta` (FK, opcional) ·
`contrato_compra` (FK, opcional) · `tipo` (enum: ESCRITURA, LICENCIA, PLANO,
CERTIFICACION, AVALUO, CONTRATO, OTRO) · `nombre` · `archivo_url` ·
`fecha_emision` · `fecha_vencimiento` · `emisor` · `estado_indexacion` (enum:
PENDIENTE, PROCESANDO, INDEXADO, ERROR) · `subido_por` (FK Usuario) ·
`fecha_carga` · `activo`

*Regla:* al crear un documento se encola su procesamiento para el RAG. Los
documentos con `fecha_vencimiento` próxima alimentan un reporte de alertas.

### EventoPropiedad ★
Línea de tiempo de cada propiedad. Es el "historial" que pide el enunciado.
`id` · `propiedad` (FK) · `tipo` (enum: ADQUISICION, INICIO_CONSTRUCCION,
AVANCE_OBRA, FIN_CONSTRUCCION, AVALUO, PUBLICACION, COTIZACION, RESERVA, VENTA,
ARRENDAMIENTO, FIN_ARRENDAMIENTO, REMODELACION, BAJA) · `fecha` ·
`descripcion` · `monto` (opcional) · `moneda` (FK, opcional) ·
`referencia_tipo` / `referencia_id` (apunta al registro que lo originó) ·
`usuario` (FK)

*Regla:* los eventos nunca se editan ni se borran. Son append-only.

---

## 3. CRM — app `crm`

### Cliente ★
`id` · `codigo` · `tipo` (PERSONA, EMPRESA) · `nombre` · `apellidos` ·
`razon_social` · `documento_identidad` · `nit` · `email` · `telefono` ·
`pais` (FK) · `ciudad` (FK, opcional) · `direccion` ·
`agente_asignado` (FK Agente) · `notas` · `activo`

*Reglas:* documento de identidad único por país para personas y NIT único por
país para empresas. La fecha de registro es `creado_en` (detalle en
`specs/004-crm-clientes-agentes.md`).

### Agente ★
`id` · `usuario` (OneToOne Usuario) · `codigo` · `porcentaje_comision` ·
`fecha_ingreso` · `activo`

*Regla:* nombre, teléfono, correo y país se leen del usuario; no se duplican
en el agente. Solo los usuarios con rol `AGENTE` tienen perfil de agente.

### Cotizacion ★
`id` · `codigo` · `cliente` (FK) · `agente` (FK) · `fecha_emision` ·
`fecha_vencimiento` · `estado` (enum: BORRADOR, ENVIADA, EN_NEGOCIACION,
APROBADA, RECHAZADA, VENCIDA) · `subtotal` · `descuento` · `total` ·
`moneda` (FK) · `observaciones` · `activo`

### CotizacionDetalle
`id` · `cotizacion` (FK) · `propiedad` (FK, opcional) · `unidad` (FK, opcional) ·
`descripcion` · `precio_unitario` · `descuento` · `subtotal`

*Regla:* el total de la cotización se recalcula desde sus detalles, nunca se
edita directamente.

---

## 4. Ventas — app `ventas`

### ContratoVenta ★
`id` · `codigo` · `cotizacion` (FK, opcional) · `cliente` (FK) ·
`propiedad` (FK, opcional) · `unidad` (FK, opcional) · `agente` (FK) ·
`fecha_firma` · `monto_total` · `moneda` (FK) · `enganche` ·
`modalidad` (CONTADO, FINANCIADO) · `estado` (VIGENTE, LIQUIDADO, ANULADO) ·
`comision_agente` · `observaciones` · `activo`

*Reglas:*
- Exactamente uno de `propiedad` o `unidad` debe estar presente.
- Al firmarse, la propiedad o unidad pasa a `VENDIDA` y se crea el evento.
- Un contrato anulado conserva el registro; nunca se borra.

### PlanPago ★
`id` · `contrato_venta` (FK) · `numero_cuotas` · `tasa_interes` ·
`fecha_inicio` · `periodicidad` (MENSUAL, TRIMESTRAL, ANUAL)

### CuotaPago ★
`id` · `plan_pago` (FK) · `numero` · `fecha_vencimiento` · `monto_capital` ·
`monto_interes` · `monto_total` · `estado` (PENDIENTE, PAGADA, VENCIDA,
PARCIAL) · `fecha_pago` · `monto_pagado` · `referencia_pago`

*Regla:* una cuota con `fecha_vencimiento` pasada y estado `PENDIENTE` cuenta
como mora. Es la base del reporte de morosidad.

---

## 5. Arrendamientos — app `arrendamientos`

### ContratoArrendamiento ★
`id` · `codigo` · `cliente` (FK) · `propiedad` (FK, opcional) ·
`unidad` (FK, opcional) · `agente` (FK) · `fecha_inicio` · `fecha_fin` ·
`renta_mensual` · `moneda` (FK) · `deposito` · `dia_cobro` ·
`estado` (VIGENTE, VENCIDO, RESCINDIDO, RENOVADO) · `renovacion_automatica` ·
`activo`

### PagoRenta ★
`id` · `contrato` (FK) · `periodo_anio` · `periodo_mes` · `fecha_vencimiento` ·
`monto` · `moneda` (FK) · `estado` (PENDIENTE, PAGADO, VENCIDO) ·
`fecha_pago` · `monto_pagado` · `mora_aplicada` · `referencia_pago`

*Regla:* único por contrato, año y mes.

---

## 6. Compras — app `compras`

### Proveedor ★
`id` · `codigo` · `tipo` (PROPIETARIO_PARTICULAR, INMOBILIARIA, BANCO,
GOBIERNO, OTRO) · `nombre` · `nit` · `email` · `telefono` · `pais` (FK) ·
`ciudad` (FK) · `direccion` · `activo`

### ContratoCompra ★
`id` · `codigo` · `proveedor` (FK) · `propiedad` (FK) · `fecha_compra` ·
`monto` · `moneda` (FK) · `gastos_legales` · `impuestos` ·
`costo_total` (calculado) · `estado` (EN_PROCESO, COMPLETADO, ANULADO) ·
`observaciones` · `activo`

*Regla:* el `costo_total` es la base para calcular la rentabilidad de la
propiedad cuando se venda.

---

## 7. Construcción — app `construccion`

### Constructora ★
`id` · `codigo` · `nombre` · `nit` · `contacto` · `email` · `telefono` ·
`pais` (FK) · `calificacion` (1 a 5) · `activo`

### ProyectoConstruccion ★
`id` · `codigo` · `nombre` · `propiedad` (FK) · `constructora` (FK) ·
`fecha_inicio` · `fecha_fin_estimada` · `fecha_fin_real` ·
`presupuesto_total` · `moneda` (FK) · `estado` (PLANIFICADO, EN_EJECUCION,
SUSPENDIDO, FINALIZADO, CANCELADO) · `porcentaje_avance` · `activo`

### AvanceObra
`id` · `proyecto` (FK) · `fecha` · `porcentaje` · `descripcion` ·
`supervisor` (FK Usuario) · `evidencia_url`

### PagoConstructora ★
`id` · `codigo` · `proyecto` (FK) · `constructora` (FK) · `fecha` ·
`monto` · `moneda` (FK) · `tipo` (ANTICIPO, AVANCE, FINIQUITO, EXTRA) ·
`porcentaje_obra_cubierto` · `documento` (FK DocumentoOficial, opcional) ·
`estado` (PROGRAMADO, PAGADO, ANULADO) · `referencia_pago`

*Regla:* la suma de pagos no puede exceder el presupuesto del proyecto sin una
autorización explícita registrada.

---

## 8. Seguridad — app `usuarios`

### Usuario
Extiende `AbstractUser` de Django, sin `username`, `first_name` ni `last_name`.
`id` · `email` (login) · `nombre_completo` · `rol` (FK) · `pais` (FK, opcional) ·
`telefono` · `last_login` (último acceso) · `is_active` (borrado lógico)

Se reutilizan los campos de Django en lugar de duplicarlos. Detalle en
`specs/001-fundacion.md` §4.

### Rol
`id` · `nombre` (ADMINISTRADOR, GERENTE, AGENTE, CONTABILIDAD, CONSULTA) ·
`descripcion` · permisos asociados

---

## 9. Auditoría e IA — apps `auditoria` e `ia`

### LogAuditoria
Ver `docs/arquitectura.md`, sección 5.

### LogAgenteIA
Ver `docs/arquitectura.md`, sección 5.

### DocumentoRAG
`id` · `titulo` · `tipo` (POLITICA, MANUAL, LEGAL, PLANTILLA, FICHA_PROPIEDAD) ·
`pais` (FK, opcional) · `archivo_url` · `documento_oficial` (FK, opcional) ·
`fecha_indexacion` · `version` · `activo`

### FragmentoRAG
`id` · `documento` (FK) · `orden` · `contenido` · `seccion` ·
`embedding` (vector, dimensión según `IA_DIMENSION_EMBEDDINGS`) · `tokens`

*Índice:* IVFFlat o HNSW sobre `embedding` para búsqueda por similitud de coseno.

---

## 10. Diagrama de relaciones principales

```
Pais ──< Ciudad ──< Propiedad ──< Unidad
                        │
                        ├──< Avaluo
                        ├──< DocumentoOficial ──> FragmentoRAG
                        ├──< EventoPropiedad          (vía cola)
                        │
          Proveedor ──< ContratoCompra ──┘
                        │
     Constructora ──< ProyectoConstruccion ──< AvanceObra
                        └──< PagoConstructora
                        │
        Cliente ──< Cotizacion ──< CotizacionDetalle
            │           │
            │           └──> ContratoVenta ──> PlanPago ──< CuotaPago
            │
            └──< ContratoArrendamiento ──< PagoRenta

        Agente ──< Cliente, Cotizacion, ContratoVenta, ContratoArrendamiento
        Usuario ──< LogAuditoria, LogAgenteIA
        Moneda ──< TipoCambio, y todos los montos del sistema
```

---

## 11. Reglas transversales

1. **Toda cantidad monetaria lleva su moneda.** Sin excepción.
2. **Borrado lógico** (`activo = False`) en todas las entidades de negocio. Los
   contratos, pagos y eventos nunca se borran físicamente.
3. **Códigos legibles** generados por el sistema: `PROP-00001`, `CV-2026-0042`,
   `COT-2026-0137`. Facilitan la defensa oral y los reportes.
4. **Campos de rastro** en toda tabla de negocio: `creado_en`, `creado_por`,
   `actualizado_en`, `actualizado_por`. Van en un modelo base abstracto en
   `apps/core`.
5. **Todo cambio de estado** de una propiedad genera un `EventoPropiedad`.
6. **Índices** obligatorios en: claves foráneas, campos de fecha usados en
   filtros de reportes, `estado`, y los campos `codigo`.
