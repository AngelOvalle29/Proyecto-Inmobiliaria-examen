# Modelo de datos

El enunciado pide entre 12 y 15 entidades núcleo. Este modelo define **25
entidades de negocio** más 4 de soporte, para tener margen y para que el dominio
quede completo.

Las entidades marcadas con ★ son las que se presentan como núcleo en la defensa.

> **Qué se construyó.** Este documento es el diseño inicial. No se
> construyeron `Amenidad`, `EventoPropiedad`, `AvanceObra`, `PlanPago` ni
> `CotizacionDetalle`: sus datos van en otra entidad o en la bitácora de
> auditoría. El detalle y el motivo de cada una están en
> `docs/guia-del-sistema.md` §16.

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
editan ni se borran: si uno tiene un error, se desactiva y se registra el
correcto. La fecha no puede ser futura y el documento adjunto, si lo hay, debe
ser de la misma propiedad.

### DocumentoOficial ★
`id` · `propiedad` (FK) · `tipo` (enum: ESCRITURA, LICENCIA, PLANO,
CERTIFICACION, AVALUO, CONTRATO, OTRO) · `nombre` · `archivo` (FileField) ·
`nombre_original` · `tipo_contenido` · `tamano_bytes` · `fecha_emision` ·
`fecha_vencimiento` (opcional) · `emisor` · `activo`

*Regla:* el archivo se guarda como
`documentos/<código de propiedad>/<uuid>.<extensión>`, en un bucket privado, y
se descarga con una URL firmada de 5 minutos. Se aceptan PDF, JPG y PNG de
hasta 10 MB, comprobados por el contenido. El archivo no se reemplaza: una
versión nueva es otro documento y el anterior se desactiva. Los documentos con
`fecha_vencimiento` próxima alimentan un reporte de alertas.

*Cambios respecto de la versión original:* `archivo_url` pasa a `archivo`
(se guarda la ruta, no la URL); `subido_por` y `fecha_carga` se reemplazan por
`creado_por` y `creado_en` de `ModeloBase`; `estado_indexacion` se pospone con
el RAG; y se quitan `contrato_venta` y `contrato_compra` porque la relación va
al revés, desde el contrato.

### ImagenPropiedad
Galería de fotos de una propiedad (spec 019).
`id` · `propiedad` (FK) · `archivo` (FileField) · `nombre_original` ·
`tipo_contenido` · `tamano_bytes` · `descripcion` (texto alternativo) · `orden` ·
`es_portada` (bool) · `activo`

*Reglas:* JPG o PNG de hasta 5 MB, comprobados por el contenido, en
`imagenes/<código de propiedad>/<uuid>.<extensión>` del mismo bucket privado.
Hasta 10 activas por propiedad. Una propiedad con imágenes tiene exactamente una
portada activa, garantizada por un constraint único condicional; la primera
imagen que se sube es la portada.

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
`id` · `codigo` · `cliente` (FK) · `agente` (FK) · `propiedad` (FK, opcional) ·
`unidad` (FK, opcional) · `fecha_emision` · `fecha_vencimiento` ·
`estado` (enum: BORRADOR, ENVIADA, APROBADA, RECHAZADA) · `precio` ·
`descuento` · `total` · `moneda` (FK) · `observaciones` · `activo`

*Reglas:*
- Exactamente uno de `propiedad` o `unidad` debe estar presente.
- El total es precio menos descuento; lo calcula el servicio.
- Vencida no es un estado guardado: se calcula con la fecha.
- No hay `CotizacionDetalle`: el plan de una semana (#28) dejó el detalle en la
  propia cotización (spec 007).

---

## 4. Ventas — app `ventas`

### ContratoVenta ★
`id` · `codigo` · `cotizacion` (OneToOne, opcional) · `cliente` (FK) ·
`propiedad` (FK, opcional) · `unidad` (FK, opcional) · `agente` (FK) ·
`fecha_firma` · `monto_total` · `moneda` (FK) · `tasa_a_usd` ·
`monto_total_usd` · `enganche` · `modalidad` (CONTADO, FINANCIADO) ·
`numero_cuotas` · `tasa_interes_anual` · `fecha_primera_cuota` ·
`estado` (VIGENTE, LIQUIDADO, ANULADO) · `comision_agente` · `observaciones` ·
`documento` (FK DocumentoOficial, opcional) · `activo`

*Reglas:*
- Exactamente uno de `propiedad` o `unidad` debe estar presente.
- Al firmarse, la propiedad o unidad pasa a `VENDIDA`.
- Un contrato anulado conserva el registro; nunca se borra.
- No hay `PlanPago`: sus datos van en el contrato (#28, spec 007).

### CuotaPago ★
`id` · `contrato` (FK) · `numero` · `fecha_vencimiento` · `monto_capital` ·
`monto_interes` · `monto_total` · `estado` (PENDIENTE, PARCIAL, PAGADA) ·
`monto_pagado` · `fecha_ultimo_pago` · `referencia_ultimo_pago` ·
`tasa_a_usd_ultimo_pago`

*Reglas:*
- La mora no es un estado: `en_mora()` la calcula con la fecha, y solo en
  contratos vigentes. Un filtro en SQL debe repetir esa condición.
- Los pagos parciales se acumulan en `monto_pagado`; la historia de cada pago,
  con su fecha y su tasa, queda en la bitácora de auditoría.

---

## 5. Arrendamientos — app `arrendamientos`

### ContratoArrendamiento ★
`id` · `codigo` · `cliente` (FK) · `propiedad` (FK, opcional) ·
`unidad` (FK, opcional) · `agente` (FK) · `fecha_inicio` · `duracion_meses` ·
`fecha_fin` · `renta_mensual` · `moneda` (FK) · `tasa_a_usd` · `deposito` ·
`dia_cobro` · `dias_gracia` · `porcentaje_mora` ·
`estado` (VIGENTE, VENCIDO, RESCINDIDO, RENOVADO) · `fecha_rescision` ·
`contrato_anterior` (OneToOne, opcional) ·
`documento` (FK DocumentoOficial, opcional) · `activo`

*Regla:* renovar crea un contrato nuevo, que apunta al anterior con
`contrato_anterior`.

### PagoRenta ★
`id` · `contrato` (FK) · `periodo_anio` · `periodo_mes` · `fecha_vencimiento` ·
`monto` · `estado` (PENDIENTE, PAGADO, CANCELADO) · `fecha_pago` ·
`monto_pagado` · `mora_aplicada` · `referencia_pago` · `tasa_a_usd`

*Reglas:*
- Único por contrato, año y mes.
- La moneda es la del contrato.
- La mora no es un estado: `en_mora()` la calcula con la fecha.
- `monto_pagado` ya incluye el recargo de `mora_aplicada`.

---

## 6. Compras — app `compras`

### Proveedor ★
`id` · `codigo` · `tipo` (PROPIETARIO_PARTICULAR, INMOBILIARIA, BANCO,
GOBIERNO, OTRO) · `nombre` · `nit` · `email` · `telefono` · `pais` (FK) ·
`ciudad` (FK) · `direccion` · `activo`

### ContratoCompra ★
`id` · `codigo` · `proveedor` (FK) · `propiedad` (FK) · `fecha_compra` ·
`monto` · `moneda` (FK) · `gastos_legales` · `impuestos` ·
`costo_total` (calculado) · `tasa_a_usd` · `costo_total_usd` ·
`estado` (EN_PROCESO, COMPLETADO, ANULADO) · `observaciones` · `activo`

*Regla:* el `costo_total` es la base para calcular la rentabilidad de la
propiedad cuando se venda. Una propiedad tiene como máximo un contrato no
anulado; completarlo la pasa de EN_NEGOCIACION a ADQUIRIDA (spec 017).

---

## 7. Construcción — app `construccion`

### Constructora ★
`id` · `codigo` · `nombre` · `nit` · `contacto` · `email` · `telefono` ·
`pais` (FK) · `calificacion` (1 a 5) · `activo`

### ProyectoConstruccion ★
`id` · `codigo` · `nombre` · `propiedad` (FK) · `constructora` (FK) ·
`fecha_inicio` · `fecha_fin_estimada` · `fecha_fin_real` ·
`presupuesto_total` · `moneda` (FK) · `estado` (PLANIFICADO, EN_EJECUCION,
SUSPENDIDO, FINALIZADO, CANCELADO) · `porcentaje_avance` · `tasa_a_usd` ·
`presupuesto_total_usd` · `activo`

*Regla:* una propiedad tiene como máximo un proyecto activo (PLANIFICADO,
EN_EJECUCION o SUSPENDIDO). Iniciar pasa la propiedad a EN_CONSTRUCCION y
finalizar, con avance 100, a DISPONIBLE (spec 017).

### AvanceObra
`id` · `proyecto` (FK) · `fecha` · `porcentaje` · `descripcion` ·
`supervisor` (FK Usuario) · `evidencia_url`

*No se implementa por ahora* (spec 017, §10): el avance es el
`porcentaje_avance` del proyecto, y cada avance queda en la bitácora con su
descripción.

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
`id` · `titulo` (único) · `tipo` (POLITICA, MANUAL, LEGAL, PLANTILLA,
FICHA_PROPIEDAD) · `pais` (FK, opcional) · `contenido_fuente` (el Markdown
completo) · `version` · `fecha_indexacion` · `estado_indexacion` (PENDIENTE,
INDEXADO, ERROR) · `error_indexacion` · `activo` y demás campos de `ModeloBase`

*Reglas:* `fecha_indexacion` nula significa que nunca se indexó; se vacía cada
vez que cambia el contenido. `estado_indexacion` lo maneja la cola de
RabbitMQ (`specs/020-ingesta-asincrona.md`): `PENDIENTE` al subir o reemplazar,
`INDEXADO` al guardar los fragmentos y `ERROR`, con su motivo en
`error_indexacion`, si se agotan los reintentos. *Cambios respecto de la versión original:*
`archivo_url` pasa a `contenido_fuente`, para poder reindexar sin depender del
almacenamiento de archivos, y `documento_oficial` se pospone a otra spec
(detalle en `specs/005-agente-ia-rag.md`).

### FragmentoRAG
`id` · `documento` (FK, borrado en cascada) · `orden` · `contenido` · `seccion` ·
`embedding` (vector de 768, igual a `IA_DIMENSION_EMBEDDINGS`) · `tokens`

*Regla:* único por documento y orden. No hereda `ModeloBase`: se regenera desde
el documento al reindexar.

*Índice:* HNSW con `vector_cosine_ops` sobre `embedding`, para búsqueda por
similitud de coseno (se descartó IVFFlat porque necesita datos para crearse).

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
        Cliente ──< Cotizacion
            │           │
            │           └──> ContratoVenta ──< CuotaPago
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