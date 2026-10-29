# 008 · Arrendamientos

| Campo | Valor |
|---|---|
| **Número** | 008 |
| **Estado** | En revisión |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `arrendamientos`; usa `catalogo`, `crm` y `core` |
| **Rama** | `feature/008-arrendamientos` |
| **Pull request** | — |
| **Issue** | #19 |

---

## 1. Problema

La agencia renta apartamentos, casas, bodegas y locales. Necesita registrar
cada contrato de renta, saber qué se cobra cada mes, registrar los pagos con su
recargo cuando llegan tarde, y renovar o terminar los contratos. Sin esto no
hay ocupación (R14), ni la parte de rentas de la morosidad (R11) y del flujo
de ingresos (R12).

## 2. Alcance

**Incluye:** `ContratoArrendamiento` y `PagoRenta`; firma con el calendario de
cobros completo; registro de pagos con recargo por mora; renovación como
contrato nuevo; rescisión y finalización; permisos con cartera; auditoría;
datos de demostración.

**No incluye:** devolución del depósito ni su uso como penalización (solo se
registra); pagos parciales de renta; renovación automática con una tarea
programada; notificaciones (rol D); pantallas (spec aparte, sobre #15).

Sigue el patrón de la spec 007 (ventas): mismo esquema de permisos, tasa al
dólar aplicada, mora calculada y cambios de estado por `catalogo`.

## 3. Reglas de negocio

**Contrato**

1. Un contrato es sobre exactamente una propiedad o unidad, que debe estar
   `DISPONIBLE`. Al firmarlo pasa a `ARRENDADA`. Una propiedad de un tipo con
   unidades no se arrienda completa: se arriendan sus unidades (como en la
   regla 9 de la spec 007).
2. El agente es el agente asignado al cliente.
3. Se firma con fecha de inicio, **duración en meses** (1 a 120), renta
   mensual, moneda, depósito (0 o más, en la misma moneda), día de cobro (1 a
   28), días de gracia (0 a 31) y porcentaje de mora (0 a 100). La fecha de
   fin la calcula el sistema: inicio + duración − 1 día.
4. **Al firmar se generan todos los pagos de renta** (decidido por B): uno por
   mes de la duración. El primero vence en la primera fecha con el día de
   cobro igual o posterior al inicio; los demás, ese día de cada mes siguiente.
   Cada pago guarda su período (año y mes) y es único por contrato y período.
   No hay prorrateo: cada mes se cobra completo.
5. El contrato guarda la tasa de su moneda al dólar en la fecha de firma
   (observación de B en #1). Sin tasa registrada, se rechaza (regla 7 de la
   spec 001).

**Pagos**

6. Un pago de renta se registra **completo** y una sola vez. Si la fecha de
   pago es posterior al vencimiento más los días de gracia, se cobra un
   **recargo fijo**: renta · porcentaje de mora (decidido por B), redondeado a
   centavos con `ROUND_HALF_UP`.
7. Quien registra el pago envía el monto recibido, y debe coincidir con renta
   más recargo: así un error de digitación no queda como pago válido. El pago
   guarda fecha, monto, recargo, referencia y la tasa al dólar de su fecha.
8. Un pago `PENDIENTE` con fecha de vencimiento pasada está **en mora**. Como
   en ventas, no se guarda: se calcula al consultar.

**Fin del contrato**

9. **Renovar** (decidido por B) crea un contrato nuevo para el mismo cliente y
   la misma propiedad o unidad, que empieza el día siguiente al fin del
   anterior, con su propia renta y duración. El anterior queda `RENOVADO` y la
   propiedad sigue `ARRENDADA`. Se renueva un contrato `VIGENTE` o `VENCIDO`, y
   cada contrato se renueva una sola vez.
10. **Rescindir** (decidido por B): el contrato `VIGENTE` pasa a `RESCINDIDO`
    con su fecha de rescisión; los pagos `PENDIENTE` de períodos posteriores a
    esa fecha pasan a `CANCELADO`; los anteriores se siguen debiendo; la
    propiedad vuelve a `DISPONIBLE`.
11. **Finalizar**: un contrato `VIGENTE` cuya fecha de fin ya pasó pasa a
    `VENCIDO` y la propiedad vuelve a `DISPONIBLE`. Los pagos pendientes se
    siguen debiendo.
12. Ningún contrato ni pago se borra.

**Permisos** (esquema de la spec 004)

13. Firman y renuevan `ADMINISTRADOR`, `GERENTE` y `AGENTE` (en su cartera).
14. Rescinden y finalizan `ADMINISTRADOR` y `GERENTE`.
15. Registran pagos `ADMINISTRADOR`, `GERENTE` y `CONTABILIDAD`.
16. Todos leen; un agente solo ve los contratos de sus clientes, y lo ajeno
    responde 404.

## 4. Modelo de datos

```
arrendamientos → core, usuarios, auditoria, catalogo, crm
```

Ambos heredan `core.ModeloBase`. Montos `DecimalField(18, 2)`, tasas
`DecimalField(18, 6)`.

### `arrendamientos.ContratoArrendamiento`

`codigo` (`ARR-00001`, nulo solo al crear) · `cliente` · `agente` ·
`propiedad` / `unidad` (exactamente uno) · `fecha_inicio` · `duracion_meses` ·
`fecha_fin` · `renta_mensual` · `moneda` · `tasa_a_usd` · `deposito` ·
`dia_cobro` · `dias_gracia` · `porcentaje_mora` (5, 2) · `estado` (`VIGENTE`,
`VENCIDO`, `RESCINDIDO`, `RENOVADO`) · `fecha_rescision` (opcional) ·
`contrato_anterior` (OneToOne a sí mismo, opcional: el contrato que renueva)

Constraints: exactamente uno de propiedad o unidad; los rangos de la regla 3;
`fecha_fin > fecha_inicio`.

Del modelo original se quita `renovacion_automatica` (la renovación es una
acción, regla 9) y se agregan `duracion_meses`, `dias_gracia`,
`porcentaje_mora`, `tasa_a_usd`, `fecha_rescision` y `contrato_anterior`.

### `arrendamientos.PagoRenta`

`contrato` (FK) · `periodo_anio` · `periodo_mes` · `fecha_vencimiento` ·
`monto` (la renta) · `estado` (`PENDIENTE`, `PAGADO`, `CANCELADO`) ·
`fecha_pago` · `monto_pagado` · `mora_aplicada` · `referencia_pago` ·
`tasa_a_usd`

Constraints: único por (`contrato`, `periodo_anio`, `periodo_mes`)
(`docs/modelo-datos.md`); `periodo_mes` entre 1 y 12. `moneda` se quita: es la
del contrato. El estado `VENCIDO` se quita (regla 8) y se agrega `CANCELADO`
(regla 10).

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| GET, POST | `/api/v1/contratos-arrendamiento/` · filtros `?estado`, `?cliente`, `?agente`, `?propiedad` | Leer: todos · Firmar: regla 13 |
| GET | `/api/v1/contratos-arrendamiento/{id}/` (con sus pagos y `en_mora`) | Todos, con cartera |
| POST | `/{id}/renovar/` · `{ "renta_mensual", "duracion_meses" }` | Regla 13 |
| POST | `/{id}/rescindir/` · `{ "fecha_rescision" }` | Regla 14 |
| POST | `/{id}/finalizar/` | Regla 14 |
| POST | `/api/v1/pagos-renta/{id}/pagar/` · `{ "fecha", "monto", "referencia" }` | Regla 15 |

**Errores nuevos** (además de `PROPIEDAD_NO_DISPONIBLE`,
`PROPIEDAD_CON_UNIDADES` y `TIPO_CAMBIO_NO_DISPONIBLE` de las specs 001 y 007):

| Código | Situación | HTTP |
|---|---|---|
| `CONTRATO_NO_VIGENTE` | Se rescinde o finaliza un contrato que no está `VIGENTE` | 409 |
| `CONTRATO_NO_TERMINADO` | Se finaliza antes de la fecha de fin (regla 11) | 409 |
| `CONTRATO_YA_RENOVADO` | Se renueva un contrato renovado o rescindido (regla 9) | 409 |
| `PAGO_NO_PENDIENTE` | Se paga un pago ya pagado o cancelado | 409 |
| `MONTO_INCORRECTO` | El monto no es renta más recargo; `detalles` dice el esperado (regla 7) | 400 |

## 6. Servicios y selectores

```python
# arrendamientos/services.py (transaction.atomic y registrar_auditoria)
def firmar_arrendamiento(*, datos: dict, autor, ip) -> ContratoArrendamiento
def calcular_calendario(*, inicio, duracion_meses, dia_cobro) -> list[date]
    """Función pura (regla 4): fechas de vencimiento de cada mes."""
def calcular_recargo(*, renta, porcentaje, vencimiento, dias_gracia, fecha_pago) -> Decimal
    """Función pura (regla 6)."""
def registrar_pago_renta(*, pago, fecha, monto, referencia, autor, ip) -> PagoRenta
def renovar_arrendamiento(*, contrato, renta_mensual, duracion_meses, autor, ip) -> ContratoArrendamiento
def rescindir_arrendamiento(*, contrato, fecha_rescision, autor, ip) -> ContratoArrendamiento
def finalizar_arrendamiento(*, contrato, autor, ip) -> ContratoArrendamiento

# arrendamientos/selectors.py
def listar_arrendamientos_visibles(*, usuario) -> QuerySet[ContratoArrendamiento]
```

Los estados de la propiedad o unidad cambian con `cambiar_estado_propiedad` y
`cambiar_estado_unidad` (pedido en la spec 007 e implementado por A en #34). El cálculo de fechas
mensuales (un 31 que el mes no tiene pasa al último día) es el mismo que el de
las cuotas de ventas; se escribe una sola vez, en `core`, si A está de
acuerdo.

## 7. Auditoría

`CREAR` al firmar y al renovar (con el número de pagos generados);
`ACTUALIZAR` en cada pago (monto, recargo, fecha, referencia, tasa) y al
renovar el contrato anterior; `ANULAR` al rescindir (con los pagos cancelados)
y `ACTUALIZAR` al finalizar, ambos con el estado anterior y el nuevo. Los
pagos generados al firmar no se auditan uno por uno.

## 8. Criterios de aceptación

- [ ] Firmar sobre una propiedad disponible la deja `ARRENDADA` y genera un
      pago por mes, con el día de cobro correcto y sin repetir período
- [ ] No se arrienda una propiedad no disponible ni una propiedad con unidades
      completa (409)
- [ ] Un pago dentro de la gracia no lleva recargo; uno después, sí
- [ ] Un monto distinto de renta más recargo es 400 con el esperado; pagar dos
      veces es 409
- [ ] Renovar crea un contrato que empieza al día siguiente, deja el anterior
      `RENOVADO` y la propiedad sigue `ARRENDADA`
- [ ] Rescindir cancela los pagos futuros, conserva los vencidos y libera la
      propiedad
- [ ] Finalizar antes del fin es 409; después, deja el contrato `VENCIDO` y
      libera la propiedad
- [ ] Un pago pendiente vencido aparece con `en_mora: true`
- [ ] Matriz de permisos de las reglas 13 a 16, con 404 para lo ajeno
- [ ] Toda escritura queda en la bitácora
- [ ] `ruff`, `pytest`, `makemigrations --check` y el esquema OpenAPI pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Unidad | `calcular_calendario`: inicio antes y después del día de cobro, fin de mes, cambio de año |
| Unidad | `calcular_recargo`: último día de gracia (sin recargo), día siguiente (con recargo), redondeo |
| Modelo | Exactamente una de propiedad o unidad; período único; rangos |
| Servicio | Firmar, pagar, renovar, rescindir y finalizar, con sus errores |
| Selector | Cartera del agente; `en_mora` |
| API | Matriz de permisos; 404 ajeno; filtros; un error por endpoint |

## 10. Decisiones y alternativas descartadas

**Decididas por B:** pagos generados al firmar (se descartó generarlos mes a
mes con Celery beat, que no existe y depende de un worker que se duerme);
recargo fijo tras días de gracia (se descartó un porcentaje por día, que cambia
cada día y es difícil de explicar, y no cobrar recargo); renovar como contrato
nuevo (se descartó extender la fecha de fin, que no permite cambiar la renta ni
separa los períodos); rescindir cancelando los pagos futuros, con el depósito
solo registrado (se descartó usarlo como penalización, que agrega una regla
contable).

**Propuestas del agente, a validar en la revisión:**

- *Duración en meses en lugar de fecha de fin.* Con una fecha de fin libre
  habría que decidir qué pasa con un mes incompleto; con la duración, el
  número de pagos es exacto.
- *Sin prorrateo y sin pagos parciales.* Cada mes se cobra completo y en un
  solo pago. Ventas sí acepta parciales porque una cuota puede ser grande; una
  renta mensual se paga entera.
- *El monto lo confirma quien registra.* El sistema calcula renta más recargo,
  pero exige que el monto recibido coincida, para que un error de digitación no
  pase como pago.
- *Finalizar es una acción y no una tarea diaria.* Igual que la mora: sin
  Celery beat, el gerente finaliza el contrato vencido, y mientras tanto la
  consulta muestra que su fecha de fin ya pasó.
- *Un día de cobro del 1 al 28.* Todos los meses tienen esos días, así el
  calendario nunca necesita ajustar el día de cobro.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-28 (Claude Code, rol B).** El agente leyó
`docs/modelo-datos.md` §5, `docs/reportes.md` (R11, R12, R14), las specs 003, 004 y 007
y la issue #19, y propuso el borrador siguiendo el patrón de la spec 007.
Las cuatro decisiones de negocio de §10 las tomó B entre opciones planteadas
por el agente.

**Plan de implementación:** (1) modelos y funciones puras de calendario y
recargo; (2) firma y pagos; (3) renovar, rescindir y finalizar; (4) API y
datos de demostración.

**Renumeración, 2026-10-29.** Se propuso como 006, número que también usó la
spec de proveedores y constructoras (#39). Pasa a 008, después de la de ventas
(007, antes 005), que es el patrón que copia.
