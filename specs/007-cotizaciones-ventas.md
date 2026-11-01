# 007 · Cotizaciones y ventas

| Campo | Valor |
|---|---|
| **Número** | 007 |
| **Estado** | En revisión |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `crm` (cotizaciones), `ventas`; pide a `catalogo` un servicio para el estado de las unidades (§6) |
| **Rama** | `feature/007-cotizaciones-ventas` |
| **Pull request** | DouGMV/Proyecto-Inmobiliaria#44 |
| **Issues** | #17, #18 |

---

## 1. Problema

El agente ofrece una propiedad a un cliente con un precio y un descuento, y el
cliente acepta o no. Si acepta, la agencia firma un contrato de venta, de
contado o financiado en cuotas, y después registra cada pago. Hoy nada de eso
queda registrado, y sin ventas no hay estado de cuenta, morosidad, comisiones
ni flujo de ingresos (reportes R02, R03, R10, R11 y R12).

## 2. Alcance

**Incluye:** `Cotizacion` (en `crm`), `ContratoVenta` y `CuotaPago` (en
`ventas`); el flujo de la cotización (enviar, aprobar, rechazar); la firma del
contrato con su plan de cuotas; el registro de pagos de cuotas; la anulación;
permisos con cartera; auditoría; datos de demostración.

**No incluye** (plan de una semana, #28): `CotizacionDetalle` como tabla
aparte; `PlanPago` como tabla aparte (sus datos van en el contrato); recargos
por mora en ventas (la mora solo se reporta); notificaciones por correo al
aprobar o pagar (spec de mensajería, rol D); pantallas (spec aparte, sobre la
base del frontend #15); vencimiento automático de cotizaciones con una tarea
programada.

## 3. Reglas de negocio

**Cotizaciones**

1. Una cotización es por **exactamente una** propiedad o unidad (decidido por
   B). Precio, descuento y total están en la propia cotización. Como en la
   regla 9, una propiedad de un tipo con unidades no se cotiza completa: se
   cotizan sus unidades.
2. El precio inicial es el precio de lista de la propiedad o unidad, y la
   moneda es la suya. El total es precio menos descuento, lo calcula el
   servicio y nunca se edita directamente. El descuento está entre 0 y el
   precio.
3. El agente de la cotización es el agente asignado al cliente.
4. Estados: `BORRADOR` → `ENVIADA` → `APROBADA` o `RECHAZADA`. Solo una
   cotización en `BORRADOR` se edita. **Vencida no es un estado guardado**
   (decidido por B): una cotización en `BORRADOR` o `ENVIADA` está vencida si
   su fecha de vencimiento ya pasó, igual que la mora de la regla 17. La API la
   muestra con `vencida: true`, y una cotización vencida no se envía ni se
   aprueba (409 `COTIZACION_VENCIDA`).
5. Solo se cotiza y se aprueba sobre una propiedad o unidad `DISPONIBLE`.
6. **Aprobar reserva** (decidido por B): la propiedad o unidad pasa a
   `RESERVADA`. Rechazar una cotización aprobada (el cliente desistió) la
   devuelve a `DISPONIBLE`. **Una cotización que ya tiene contrato no se
   rechaza** (409 `COTIZACION_YA_CONTRATADA`): su propiedad está `VENDIDA`, y
   rechazarla la volvería a ofrecer.

**Contratos de venta**

7. Un contrato se firma **desde una cotización aprobada o sin ella**
   (decidido por B). Desde una cotización toma su cliente, propiedad o unidad,
   moneda y total; cada cotización da lugar a un contrato como máximo.
8. Sin cotización, la propiedad o unidad debe estar `DISPONIBLE`. Desde una
   cotización, la cotización debe estar `APROBADA` y la propiedad o unidad
   `RESERVADA`. La propiedad no guarda quién la reservó; no hace falta, porque
   la regla 5 impide dos cotizaciones aprobadas sobre la misma propiedad.
9. Una propiedad de un tipo con unidades no se vende completa: se venden sus
   unidades.
10. Al firmar, la propiedad o unidad pasa a `VENDIDA`.
11. **Contado:** el contrato nace `LIQUIDADO` y no genera cuotas.
    **Financiado:** enganche entre 0 y el monto total (sin incluirlo),
    número de cuotas entre 1 y 360, tasa de interés anual entre 0 y 100, y
    cuotas mensuales desde la fecha de la primera cuota.
12. **Cuota fija** (sistema francés, decidido por B): con saldo `P` = monto
    total − enganche, tasa mensual `i` = tasa anual / 12 / 100 y `n` cuotas,
    cada cuota vale `P · i / (1 − (1 + i)^−n)`; con tasa 0, `P / n`. Cada cuota
    separa interés (saldo pendiente · `i`) y capital (el resto). Los montos se
    redondean a centavos con `ROUND_HALF_UP` y la **última cuota ajusta** la
    diferencia, para que el capital sume exactamente el saldo.
13. La comisión del agente se calcula al firmar (monto total · porcentaje del
    agente) y se guarda: si después cambia su porcentaje, la comisión de ese
    contrato no cambia. **Con cotización, la comisión es del agente que
    cotizó**, aunque el cliente se haya reasignado después; sin cotización, del
    agente asignado al cliente al firmar (decidido por B en la revisión de
    #44).
14. **Tasa de cambio aplicada** (observación de B en #1): el contrato guarda la
    tasa de su moneda al dólar en la fecha de firma y el monto total en
    dólares; cada pago de cuota guarda la tasa de la fecha de pago. Si no hay
    tasa registrada, la operación se rechaza (regla 7 de la spec 001: no se
    calculan inversas). Con esto los reportes suman en dólares sin recalcular.
15. Un contrato **vigente sin ningún pago registrado** se puede anular: pasa a
    `ANULADO`, conserva sus registros y la propiedad o unidad vuelve a
    `DISPONIBLE`. Con pagos no se anula (habría que devolver dinero, fuera de
    alcance).

**Pagos de cuotas**

16. Un pago se registra sobre una cuota de un contrato `VIGENTE`, con fecha
    entre la firma del contrato y hoy (400 `FECHA_PAGO_INVALIDA`), en la moneda
    del contrato; en un contrato `ANULADO` o `LIQUIDADO` no se registran pagos
    (409 `CONTRATO_NO_VIGENTE`). Puede ser parcial: la cuota queda `PARCIAL`
    hasta completar su total, y entonces `PAGADA`. Un pago no puede exceder lo
    que falta de la cuota.
17. Una cuota `PENDIENTE` o `PARCIAL` con fecha de vencimiento pasada está **en
    mora**. No se guarda como estado: se calcula al consultar, así nunca queda
    desactualizada (base del reporte R11).
18. Cuando todas las cuotas están `PAGADA`, el contrato pasa a `LIQUIDADO`.

**Permisos** (esquema de la spec 004)

19. Cotizaciones: crean, editan, envían, aprueban y rechazan `ADMINISTRADOR`,
    `GERENTE` y `AGENTE` (este, solo en su cartera).
20. Contratos: firman los mismos tres; anulan solo `ADMINISTRADOR` y `GERENTE`.
21. Pagos: registran `ADMINISTRADOR`, `GERENTE` y `CONTABILIDAD`.
22. Todos los roles autenticados leen; un agente solo ve las cotizaciones y
    contratos de sus clientes, y lo ajeno responde 404 (regla 14 de la spec
    004).

**Documento del contrato** (agregado el 2026-11-01, pendiente desde #42)

23. Un contrato puede apuntar a un documento oficial: el contrato firmado y
    escaneado. Es opcional y debe ser un documento activo de la misma propiedad;
    si se vende una unidad, de su edificio (409 `DOCUMENTO_DE_OTRA_PROPIEDAD`).
24. **Se vincula al firmar o después** (decidido por B), porque el escaneado
    suele existir después de firmar. **Se puede cambiar, pero no quitar**
    (decidido por B): corrige un archivo equivocado sin dejar sin respaldo un
    contrato que ya lo tenía. El cambio queda en la bitácora. Un contrato
    `ANULADO` ya no cambia (409 `CONTRATO_NO_VIGENTE`); uno `LIQUIDADO` sí,
    porque el de contado nace así. Vinculan los que firman (regla 20).

## 4. Modelo de datos

```
crm      → core, usuarios, auditoria, catalogo
ventas   → core, usuarios, auditoria, catalogo, crm
```

Todos heredan `core.ModeloBase`. Montos: `DecimalField(18, 2)`; tasas de
cambio: `DecimalField(18, 6)`, como `TipoCambio`.

### `crm.Cotizacion`

`codigo` (`COT-00001`, nulo solo al crear) · `cliente` (FK) · `agente` (FK) ·
`propiedad` (FK `catalogo.Propiedad`, opcional) · `unidad` (FK
`catalogo.Unidad`, opcional) · `fecha_emision` · `fecha_vencimiento` ·
`estado` (enum `EstadoCotizacion`) · `precio` · `descuento` · `total` ·
`moneda` (FK) · `observaciones`

Constraints: exactamente uno de `propiedad` o `unidad`; `precio > 0`;
`0 <= descuento <= precio`; `total = precio - descuento`;
`fecha_vencimiento >= fecha_emision`.

Del modelo original se quita `subtotal` (es el precio) y los estados
`EN_NEGOCIACION`, que no tiene una acción que lo produzca, y `VENCIDA`, que se
calcula (regla 4).

### `ventas.ContratoVenta`

`codigo` (`CV-00001`) · `cotizacion` (OneToOne, opcional) · `cliente` ·
`agente` · `propiedad` / `unidad` (exactamente uno) · `fecha_firma` ·
`monto_total` · `moneda` · `tasa_a_usd` · `monto_total_usd` · `modalidad`
(`CONTADO`, `FINANCIADO`) · `enganche` · `numero_cuotas` ·
`tasa_interes_anual` (5, 2) · `fecha_primera_cuota` · `comision_agente` ·
`estado` (`VIGENTE`, `LIQUIDADO`, `ANULADO`) · `observaciones`

`numero_cuotas`, `tasa_interes_anual` y `fecha_primera_cuota` son los datos que
tenía `PlanPago`; quedan nulos en un contrato de contado. Constraints: los
rangos de la regla 11 y que un contrato financiado los tenga.

### `ventas.CuotaPago`

`contrato` (FK) · `numero` · `fecha_vencimiento` · `monto_capital` ·
`monto_interes` · `monto_total` · `estado` (`PENDIENTE`, `PARCIAL`, `PAGADA`) ·
`monto_pagado` · `fecha_ultimo_pago` · `referencia_ultimo_pago` ·
`tasa_a_usd_ultimo_pago`

Constraints: único por (`contrato`, `numero`);
`0 <= monto_pagado <= monto_total`. Del modelo original se quita el estado
`VENCIDA` (regla 17).

Cada pago parcial actualiza el acumulado y los datos del último pago; la
historia completa de pagos queda en la bitácora de auditoría.

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| POST | `/api/v1/contratos-venta/{id}/documento/` · `{ "documento": 3 }` | Firman: regla 20. Reglas 23 y 24 |
| GET, POST | `/api/v1/cotizaciones/` · filtros `?estado`, `?cliente`, `?agente` | Leer: todos · Crear: regla 19 |
| GET, PATCH | `/api/v1/cotizaciones/{id}/` | Editar: regla 19, solo en `BORRADOR` |
| POST | `/api/v1/cotizaciones/{id}/enviar/` · `/aprobar/` · `/rechazar/` | Regla 19 |
| GET, POST | `/api/v1/contratos-venta/` · filtros `?estado`, `?cliente`, `?agente`, `?modalidad` | Leer: todos · Firmar: regla 20 |
| GET | `/api/v1/contratos-venta/{id}/` (incluye sus cuotas, con `en_mora`) | Todos, con cartera |
| POST | `/api/v1/contratos-venta/{id}/anular/` | `ADMINISTRADOR`, `GERENTE` |
| POST | `/api/v1/cuotas/{id}/pagos/` · `{ "monto", "fecha", "referencia" }` | Regla 21 |

**Firmar desde una cotización:** `{ "cotizacion": 7, "fecha_firma": "2026-10-30", "modalidad": "FINANCIADO", "enganche": "50000.00", "numero_cuotas": 120, "tasa_interes_anual": "9.50", "fecha_primera_cuota": "2026-12-01" }`.
**Sin cotización:** en lugar de `cotizacion`, `cliente`, `propiedad` o
`unidad`, `monto_total` y `moneda`.

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `PROPIEDAD_NO_DISPONIBLE` | La propiedad o unidad no está en el estado que exige la regla 5 u 8 | 409 |
| `COTIZACION_NO_EDITABLE` | Se edita una cotización fuera de `BORRADOR` | 409 |
| `TRANSICION_INVALIDA` | Se envía, aprueba o rechaza desde un estado que no lo permite | 409 |
| `COTIZACION_VENCIDA` | Se envía o aprueba una cotización vencida (regla 4) | 409 |
| `COTIZACION_YA_CONTRATADA` | La cotización ya tiene contrato: no da otro (regla 7) ni se rechaza (regla 6) | 409 |
| `PROPIEDAD_CON_UNIDADES` | Se cotiza o vende completa una propiedad de un tipo con unidades (reglas 1 y 9) | 409 |
| `CONTRATO_NO_VIGENTE` | Se paga o se anula un contrato que no está `VIGENTE` (reglas 15 y 16) | 409 |
| `FECHA_PAGO_INVALIDA` | La fecha del pago es anterior a la firma o futura (regla 16). *Agregado en la revisión de #44* | 400 |
| `COTIZACION_NO_APROBADA` | Se firma desde una cotización que no está `APROBADA` (regla 8). *Agregado al implementar* | 409 |
| `CONTRATO_CON_PAGOS` | Se anula un contrato que ya tiene pagos (regla 15) | 409 |
| `PAGO_EXCEDE_SALDO` | El pago supera lo que falta de la cuota (regla 16) | 400 |
| `TIPO_CAMBIO_NO_DISPONIBLE` | Ya existe (spec 001): no hay tasa al dólar en la fecha (regla 14) | 422 |

## 6. Servicios y selectores

```python
# crm/services.py
def crear_cotizacion(*, datos: dict, autor, ip) -> Cotizacion
def actualizar_cotizacion(*, cotizacion, datos: dict, autor, ip) -> Cotizacion
def enviar_cotizacion(*, cotizacion, autor, ip) -> Cotizacion
def aprobar_cotizacion(*, cotizacion, autor, ip) -> Cotizacion     # reserva (regla 6)
def rechazar_cotizacion(*, cotizacion, autor, ip) -> Cotizacion    # libera si estaba aprobada

# ventas/services.py
def firmar_contrato(*, datos: dict, autor, ip) -> ContratoVenta    # reglas 7 a 14
def calcular_cuotas(*, saldo, tasa_anual, numero_cuotas, primera) -> list[dict]
    """Función pura, sin base de datos (regla 12). Se prueba sola."""
def anular_contrato(*, contrato, autor, ip) -> ContratoVenta
def registrar_pago_cuota(*, cuota, monto, fecha, referencia, autor, ip) -> CuotaPago

# selectores con cartera, sobre listar_clientes_visibles de la spec 004
def listar_cotizaciones_visibles(*, usuario) -> QuerySet[Cotizacion]
def listar_contratos_visibles(*, usuario) -> QuerySet[ContratoVenta]
```

Los cambios de estado pasan por `cambiar_estado_propiedad` y
`cambiar_estado_unidad` de `catalogo` (spec 003). El de unidades lo pidió esta
spec y A lo agregó en #34. Las tasas usan `obtener_tipo_cambio` de `core`;
para un contrato en dólares devuelve 1 (regla 7 de la spec 001), así que no
hace falta un tipo de cambio USD→USD.

El cálculo de fechas mensuales va en `core/fechas.py` (acordado con A en #35),
compartido con arrendamientos: función pura, con sus pruebas. Las fechas
mensuales que caen en un día que el mes no tiene (31 de febrero) se
mueven al último día de ese mes.

## 7. Auditoría

Cada escritura registra en la misma transacción: `CREAR` al crear una
cotización y al firmar un contrato (con su número de cuotas), `ACTUALIZAR` al
editar y al cambiar de estado (con el anterior y el nuevo), `APROBAR` al
aprobar una cotización, `ANULAR` al anular un contrato, y `ACTUALIZAR` en cada
pago de cuota, con monto, fecha, referencia, tasa y el acumulado antes y
después. Las cuotas generadas al firmar no se auditan una por una: el registro
del contrato dice cuántas se generaron, y se pueden recalcular.

## 8. Criterios de aceptación

*Verificados el 2026-10-30 con las pruebas de `apps/crm/tests/test_cotizaciones.py` y `apps/ventas/tests/`, y con la demostración de `seed_demo` (§11).*

- [x] Una cotización aprobada deja la propiedad `RESERVADA`; rechazarla la
      devuelve a `DISPONIBLE`
- [x] No se cotiza ni se aprueba sobre una propiedad no disponible (409)
- [x] Una cotización vencida aparece con `vencida: true` y no se envía ni se
      aprueba (409)
- [x] Una cotización con contrato no se rechaza (409), y su propiedad sigue
      `VENDIDA`
- [x] Un edificio con unidades no se cotiza ni se vende completo (409)
- [x] No se registran pagos en un contrato anulado (409)
- [x] Un contrato firmado desde una cotización toma sus datos y deja la
      propiedad `VENDIDA`; la misma cotización no da un segundo contrato
- [x] Un contrato de contado nace `LIQUIDADO` sin cuotas
- [x] Un contrato financiado genera sus cuotas fijas, y su capital suma
      exactamente el saldo
- [x] El contrato guarda comisión, tasa al dólar y monto en dólares; sin tasa,
      422
- [x] Un pago parcial deja la cuota `PARCIAL`; completarla la deja `PAGADA`;
      pagar de más es 400
- [x] Al pagar la última cuota el contrato queda `LIQUIDADO`
- [x] Una cuota pendiente vencida aparece con `en_mora: true`
- [x] Anular sin pagos libera la propiedad; con pagos, 409
- [x] Matriz de permisos de las reglas 19 a 22, con 404 para lo ajeno
- [x] Toda escritura queda en la bitácora
- [x] `ruff`, `pytest`, `makemigrations --check` y el esquema OpenAPI pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Unidad | `calcular_cuotas`: cuota fija conocida (caso de libro), tasa 0, ajuste de la última cuota, 31 de enero → 28 o 29 de febrero |
| Modelo | Exactamente una de propiedad o unidad; total = precio − descuento; montos y rangos |
| Servicio | Flujo de la cotización y sus transiciones inválidas; aprobar reserva y rechazar libera; vencida |
| Servicio | Firmar con y sin cotización, de contado y financiado; comisión y tasa guardadas; propiedad con unidades |
| Servicio | Pago parcial, completo, excedido; contrato liquidado; anular con y sin pagos |
| Selector | Cartera del agente; `en_mora` calculado |
| API | Matriz de permisos; 404 ajeno; filtros; un error por endpoint |

## 10. Decisiones y alternativas descartadas

**Decididas por B:** una propiedad o unidad por cotización (se descartó una
lista en JSON, que no se valida con constraints ni se cruza en reportes);
aprobar reserva (se descartó no cambiar el estado, que permitía dos
cotizaciones aprobadas sobre la misma propiedad); contrato con cotización
opcional (una venta de contado inmediata no necesita cotización); cuota fija
(se descartaron capital fijo y sin interés; la cuota fija es la que usan los
bancos y la que un cliente espera).

**Propuestas del agente, a validar en la revisión:**

- *La cotización vive en `crm` y no en `ventas`.* Es la propuesta comercial al
  cliente, como lo ubica `docs/arquitectura.md` §3; `ventas` depende de `crm`
  y no al revés.
- *La mora se calcula, no se guarda.* Un estado `VENCIDA` guardado necesita una
  tarea diaria que lo actualice y queda mal si la tarea falla. Calcularla con
  la fecha de hoy siempre es correcto.
- *La cotización vencida también se calcula (decidido por B, en la revisión).*
  La primera versión guardaba `VENCIDA` y rechazaba en el mismo paso, pero
  dentro de `transaction.atomic` el error deshace la marca: nunca quedaría
  guardada (observación de A). Se descartó guardarla en una transacción aparte,
  como el `LOGIN_FALLIDO` de la spec 001, porque calcularla es coherente con la
  mora y no necesita una escritura especial.
- *La última cuota ajusta el redondeo.* Redondear cada cuota a centavos deja
  unos centavos de diferencia con el saldo; si se reparte en la última, el
  capital cuadra exacto.
- *Pagos acumulados en la cuota, historia en la bitácora.* Una tabla de pagos
  aparte sería más completa, pero es otra entidad que el plan de una semana
  deja fuera; la bitácora ya guarda cada pago con su monto y tasa.
- *Tasa al dólar y no a la moneda de presentación.* Los reportes consolidan en
  dólares, y `seed_demo` carga las tasas contra el dólar. Guardarla al firmar
  y al pagar responde la observación de B en #1 sin recalcular el pasado.
- *Anular solo sin pagos.* Con pagos, anular exige devolver dinero, una regla
  de negocio que nadie pidió.
- *Una propiedad con unidades no se vende completa.* Evita decidir qué pasa con
  unidades vendidas o arrendadas dentro de un edificio vendido.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-28 (Claude Code, rol B).** El agente leyó `docs/modelo-datos.md`,
`docs/reportes.md`, las specs 001, 003 y 004, el código de `catalogo` del PR
#34 y las issues #17 y #18, y propuso el borrador. Las cuatro decisiones de
negocio de §10 las tomó B entre opciones planteadas por el agente. El agente
detectó que la spec 003 no tiene un servicio para cambiar el estado de las
unidades y lo dejó como pedido a A (§6).

**Plan de implementación:** (1) `Cotizacion` con su flujo y API; (2)
`calcular_cuotas` y modelos de `ventas`; (3) firma y anulación; (4) pagos y
mora; (5) API de ventas y datos de demostración.

**Renumeración, 2026-10-29.** Esta spec se propuso como 005, pero ese número
lo tomó la spec del agente de IA (#36), fusionada antes. Pasa a 007, y la de
arrendamientos a 008, para dejar el 006 a proveedores y constructoras (#39).

**Revisión de A (Douglas), 2026-10-29.** Pidió cambios por dos huecos: rechazar
una cotización ya contratada liberaba una propiedad vendida (regla 6), y la
regla 4 no podía guardar `VENCIDA` y rechazar en el mismo paso. Se cerraron los
dos; para el segundo, B eligió calcular la vencida. También se aplicaron sus
sugerencias: la regla 9 vale para las cotizaciones, no se paga en un contrato
anulado, la regla 8 redactada sin "reservada por", `cambiar_estado_unidad` ya
existe, la tasa USD→USD es 1, y las fechas mensuales van en `core/fechas.py`.

**Implementación, 2026-10-29 y 30 (Claude Code, rol B).** El agente escribió el
código de cada paso con sus pruebas, en cinco commits en #44.

- **Paso 0, en `catalogo` (área de A).** Aprobar una cotización comprueba que el
  bien esté `DISPONIBLE` y lo pasa a `RESERVADA`. Comprobarlo antes del bloqueo
  de la fila dejaba una carrera: dos aprobaciones simultáneas pasaban las dos.
  `cambiar_estado_propiedad` y `cambiar_estado_unidad` aceptan ahora
  `estado_requerido`, que se comprueba bajo el mismo bloqueo, y la regla 5 se
  cumple aunque lleguen dos peticiones a la vez. Lo usan también la firma y la
  anulación.
- **Paso 2, constraints.** Las pruebas encontraron que "un financiado tiene
  entre 1 y 360 cuotas" aceptaba un número de cuotas nulo: en SQL, `NULL >= 1`
  no es falso sino desconocido, y un `CHECK` deja pasar lo desconocido. Se
  exige además `isnull=False`.
- **Paso 2, cuota fija.** `calcular_cuotas` se comprobó con un caso de libro
  (10 000 al 12 % en 12 cuotas: 888.49, calculado aparte) y con el capital
  sumando exactamente el saldo.
- **Paso 3, decisiones al implementar** (a validar en la revisión del PR):
  - Firmar desde una cotización que no está `APROBADA` responde 409
    `COTIZACION_NO_APROBADA`, un código que la spec no tenía.
  - Un contrato de contado nace `LIQUIDADO` (ya está pagado), así que no se
    anula: la regla 15 pide un contrato `VIGENTE`.
  - Los pagos bloquean primero el contrato y después la cuota, para que dos
    pagos simultáneos del mismo contrato se ordenen.
- **Paso 5, esquema.** Cuatro campos `estado` con valores distintos (propiedad,
  cotización, contrato y cuota) chocaban en el esquema OpenAPI. Se les dio
  nombre en `SPECTACULAR_SETTINGS` (área de A).
- **Paso 5, demostración.** A diferencia de las demos de core, catálogo y CRM,
  la de ventas usa los mismos servicios que la API, para que cada contrato
  quede coherente (cuotas, estado del bien, tasa y comisión). Por eso sus
  escrituras sí quedan en la bitácora, con usuario nulo.
- **Resuelto el 2026-11-01:** el campo `documento` de `ContratoVenta`, acordado
  en la revisión de la spec 011 (#42), se agregó cuando `DocumentoOficial` llegó
  a `develop` (reglas 23 y 24).

Resultado: 387 pruebas del proyecto, cobertura de `ventas/services.py` del 96 %
y de `crm/services.py` del 99 %, esquema OpenAPI sin advertencias.

**Revisión de A del PR (#44), 2026-10-29.** Aprobó y dejó tres detalles para
un PR siguiente: la spec 003 debe mencionar `estado_requerido` (lo agrega A);
la fecha de un pago se debe limitar a entre la firma y hoy, porque una fecha
futura aplicaría una tasa que todavía no es la vigente (regla 16); y la spec
debía decir qué agente cobra la comisión si el cliente se reasignó después de
cotizar. B decidió que la cobra el agente que cotizó (regla 13).
