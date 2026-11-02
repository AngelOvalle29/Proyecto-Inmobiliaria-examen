# 017 · Compras y construcción: contratos de compra, proyectos y pagos

| Campo | Valor |
|---|---|
| **Número** | 017 |
| **Estado** | Implementada |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce), PR #64 |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `compras`, `construccion` (incluidos sus comandos de demostración), `config/settings/base.py` (nombres de enums del esquema), `docs/modelo-datos.md` |
| **Rama** | `feature/017-contratos-compra-proyectos` y `feature/017-pagos-constructora` |
| **Pull request** | #75 (contratos y proyectos) y el PR de pagos, demostración y cierre |

---

## 1. Problema

La agencia ya registra a sus proveedores y constructoras (spec 006), pero no lo
que hace con ellos: comprarles propiedades, construir sobre ellas y pagar la
obra. Sin eso, una propiedad no tiene cómo pasar de `EN_NEGOCIACION` a
`DISPONIBLE`, no se sabe cuánto costó adquirirla (la base de la rentabilidad) y
no hay control de lo que se le paga a cada constructora.

Esta spec crea `ContratoCompra`, `ProyectoConstruccion` y `PagoConstructora`,
3 de las 17 entidades con CRUD del plan de una semana (`docs/roadmap.md`), y
completa el ciclo de vida de una propiedad del lado de la agencia:

```
EN_NEGOCIACION ──completar compra──► ADQUIRIDA ──iniciar obra──► EN_CONSTRUCCION ──finalizar obra──► DISPONIBLE
```

Desde `DISPONIBLE`, las specs 007 y 008 ya la venden o la arriendan. Una
propiedad que se compra para revender tal como está, sin obra, pasa de
`ADQUIRIDA` a `DISPONIBLE` con `/cambiar-estado/` del catálogo (regla 25).

## 2. Alcance

**Incluye:**
- `compras.ContratoCompra`: crear, completar y anular, con su auditoría
- `construccion.ProyectoConstruccion`: crear, editar, iniciar, registrar avance,
  suspender, reanudar, finalizar y cancelar
- `construccion.PagoConstructora`: programar, pagar y anular
- Los cambios de estado de la propiedad, siempre con `cambiar_estado_propiedad`
  de `catalogo` (spec 003)
- Las reglas de desactivación que la spec 006 dejó para aquí (reglas 22 y 23)
- Datos de demostración en `cargar_demo_compras` y `cargar_demo_construccion`

**No incluye:**
- **`AvanceObra` como entidad:** el avance es un porcentaje del proyecto, con su
  historial en la bitácora (§10). El plan de una semana dejó `AvanceObra` para
  "si sobra tiempo".
- **Remodelar una propiedad ya `DISPONIBLE`:** solo se construye sobre una
  propiedad `ADQUIRIDA` (regla 9, §10).
- **Compra de unidades sueltas:** la agencia compra la propiedad completa; las
  unidades se crean después en `catalogo`.
- **Editar o reabrir un contrato de compra:** un error se corrige anulando el
  contrato en proceso y registrando otro (§10).
- Pantallas: van en una spec aparte, sobre la base del frontend.
- Los reportes de rentabilidad y de pagos a constructoras: son de D; esta spec
  deja `costo_total_usd` y `monto_usd` listos para ellos.

## 3. Reglas de negocio

**Contratos de compra**

1. Un contrato se registra con un proveedor activo y una propiedad en estado
   `EN_NEGOCIACION`. Nace `EN_PROCESO` y no cambia el estado de la propiedad.
2. Una propiedad tiene como máximo un contrato que no esté anulado.
3. El monto es mayor que cero; los gastos legales y los impuestos son cero o
   más. El costo total es la suma de los tres y lo calcula el sistema.
4. La fecha de compra no puede ser futura.
5. Al registrarse se guardan la tasa de la moneda al dólar en la fecha de
   compra y el costo total convertido, como en ventas (spec 007, regla 14). Sin
   tasa registrada, no se registra.
6. **Completar** pasa el contrato de `EN_PROCESO` a `COMPLETADO` y la propiedad
   de `EN_NEGOCIACION` a `ADQUIRIDA`. Si la propiedad ya no está en negociación,
   no se completa y no cambia nada.
7. **Anular** solo es posible en `EN_PROCESO` y exige un motivo. La propiedad
   no cambia de estado. Un contrato completado no se anula.
8. El código lo genera el sistema y no cambia: `CC-00001`.

**Proyectos de construcción**

9. Un proyecto se registra con una constructora activa y una propiedad en
   estado `ADQUIRIDA`. Nace `PLANIFICADO`, con avance 0.
10. Una propiedad tiene como máximo un proyecto activo (`PLANIFICADO`,
    `EN_EJECUCION` o `SUSPENDIDO`).
11. El presupuesto es mayor que cero; la fecha de fin estimada no es anterior a
    la de inicio. Se guarda la tasa al dólar de la fecha de inicio y el
    presupuesto convertido; si el presupuesto cambia, se convierte con la misma
    tasa.
12. **Iniciar** pasa el proyecto de `PLANIFICADO` a `EN_EJECUCION` y la propiedad
    de `ADQUIRIDA` a `EN_CONSTRUCCION`.
13. **Registrar avance** solo en `EN_EJECUCION`. El porcentaje va de 0 a 100 y
    nunca baja. Cada avance queda en la bitácora con su descripción.
14. **Suspender** (de `EN_EJECUCION`, con motivo) y **reanudar** (de
    `SUSPENDIDO`). No cambian el estado de la propiedad.
15. **Finalizar** solo en `EN_EJECUCION` y con avance 100. La fecha de fin real
    es la de hoy. Pasa la propiedad de `EN_CONSTRUCCION` a `DISPONIBLE` y, si la
    propiedad tiene unidades, también sus unidades activas que todavía no
    estaban a la venta, en `EN_NEGOCIACION` o `EN_CONSTRUCCION` (con
    `cambiar_estado_unidad`), porque en un edificio lo que se cotiza y se vende
    son las unidades. Las que ya tienen otro estado (reservada, vendida) no se
    tocan. Si la propiedad ya no está `EN_CONSTRUCCION`, no se finaliza
    (regla 26).
16. **Cancelar** desde `PLANIFICADO`, `EN_EJECUCION` o `SUSPENDIDO`, con motivo.
    Si la propiedad está `EN_CONSTRUCCION`, vuelve a `ADQUIRIDA`; si alguien ya
    la movió a mano a otro estado, se cancela el proyecto sin tocar la propiedad
    y la bitácora lo anota (regla 26). Los pagos programados del proyecto se
    anulan con él.
17. Se puede editar el nombre, la fecha de fin estimada y el presupuesto de un
    proyecto activo; de un proyecto `FINALIZADO`, solo el presupuesto, para poder
    pagar un finiquito que no cabía. El presupuesto nunca queda por debajo de lo
    ya programado y pagado (regla 19). Subirlo es la autorización explícita para
    pagar más (§10).
18. El código lo genera el sistema y no cambia: `PC-00001`.

**Pagos a constructoras**

19. La suma de los pagos programados y pagados de un proyecto nunca supera su
    presupuesto.
20. Un pago se programa en la moneda del proyecto, para un proyecto que no esté
    cancelado. Un pago de tipo `FINIQUITO` solo para un proyecto `FINALIZADO`.
    Si lleva documento, debe ser un documento oficial activo de la misma
    propiedad.
21. **Pagar** pasa el pago de `PROGRAMADO` a `PAGADO` con fecha de pago (no futura
    ni anterior al inicio del proyecto, salvo un `ANTICIPO`, que se paga antes de
    empezar la obra) y referencia, y guarda la tasa al dólar de esa fecha. **Anular** solo es posible en `PROGRAMADO` y exige motivo. Un
    pago pagado no se anula. El código: `PG-00001`.

**Desactivación (reglas que la spec 006 dejó para aquí)**

22. Un proveedor con un contrato `EN_PROCESO` no se puede desactivar.
23. Una constructora con un proyecto activo no se puede desactivar.

**Propiedades sin obra y cambios manuales de estado**

25. Una propiedad `ADQUIRIDA` que no necesita obra se publica con
    `/cambiar-estado/` del catálogo (spec 003), que ya audita el cambio con su
    motivo. Sus unidades, si tiene, se publican igual, una por una. No hace falta
    una acción nueva.
26. `/cambiar-estado/` no conoce los proyectos: alguien podría mover a mano una
    propiedad en obra. Para que un proyecto nunca quede atascado, **cancelar
    siempre es posible** (regla 16) y **finalizar** responde 409 con el estado
    actual de la propiedad y la salida: devolverla a `EN_CONSTRUCCION` con
    `/cambiar-estado/` y volver a finalizar. Se acordará con A si
    `/cambiar-estado/` debe rechazar las propiedades con un proyecto activo
    (§10).

**Permisos**

24. Contratos y proyectos: escriben `ADMINISTRADOR` y `GERENTE`. Pagos: escriben
    `ADMINISTRADOR`, `GERENTE` y `CONTABILIDAD`, como los pagos de ventas
    (spec 007). Todos los roles autenticados leen.

## 4. Modelo de datos

```
compras      → core, usuarios, auditoria, catalogo
construccion → core, usuarios, auditoria, catalogo
```

Las dos apps siguen sin depender entre sí. Usan los selectores y
`cambiar_estado_propiedad` de `catalogo`, nunca sus modelos directamente.

### `compras.ContratoCompra` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`CC-00001`). Nulo solo durante la creación |
| `proveedor` | FK `Proveedor` | `PROTECT`, `related_name="contratos"` |
| `propiedad` | FK `catalogo.Propiedad` | `PROTECT`, `related_name="contratos_compra"` |
| `fecha_compra` | DateField | No futura (regla 4) |
| `monto` | DecimalField(18, 2) | Mayor que cero |
| `gastos_legales` | DecimalField(18, 2) | Cero o más, por defecto 0 |
| `impuestos` | DecimalField(18, 2) | Cero o más, por defecto 0 |
| `costo_total` | DecimalField(18, 2) | Calculado: monto + gastos + impuestos |
| `moneda` | FK `core.Moneda` | `PROTECT` |
| `tasa_a_usd` | DecimalField(18, 6) | De la fecha de compra (regla 5) |
| `costo_total_usd` | DecimalField(18, 2) | Costo total convertido |
| `estado` | CharField, enum `EstadoContratoCompra` | `EN_PROCESO`, `COMPLETADO`, `ANULADO` |
| `observaciones` | TextField | Opcional |

**Constraints:** monto > 0; gastos e impuestos ≥ 0; `costo_total` = monto +
gastos + impuestos; tasa > 0; y un único contrato no anulado por propiedad
(`UniqueConstraint` con condición, regla 2).
**Índices:** `estado`, `fecha_compra`.

### `construccion.ProyectoConstruccion` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`PC-00001`) |
| `nombre` | CharField(200) | |
| `propiedad` | FK `catalogo.Propiedad` | `PROTECT`, `related_name="proyectos_construccion"` |
| `constructora` | FK `Constructora` | `PROTECT`, `related_name="proyectos"` |
| `fecha_inicio` | DateField | Planificada |
| `fecha_fin_estimada` | DateField | No anterior a `fecha_inicio` |
| `fecha_fin_real` | DateField | Nula hasta finalizar |
| `presupuesto_total` | DecimalField(18, 2) | Mayor que cero |
| `moneda` | FK `core.Moneda` | `PROTECT` |
| `tasa_a_usd` | DecimalField(18, 6) | De la fecha de inicio (regla 11) |
| `presupuesto_total_usd` | DecimalField(18, 2) | |
| `estado` | CharField, enum `EstadoProyecto` | `PLANIFICADO`, `EN_EJECUCION`, `SUSPENDIDO`, `FINALIZADO`, `CANCELADO` |
| `porcentaje_avance` | PositiveSmallIntegerField | De 0 a 100, por defecto 0 |

**Constraints:** presupuesto > 0; fin estimada ≥ inicio; avance entre 0 y 100;
un único proyecto activo por propiedad (regla 10).
**Índices:** `estado`, `fecha_inicio`.

### `construccion.PagoConstructora` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`PG-00001`) |
| `proyecto` | FK `ProyectoConstruccion` | `PROTECT`, `related_name="pagos"` |
| `tipo` | CharField, enum `TipoPagoConstructora` | `ANTICIPO`, `AVANCE`, `FINIQUITO`, `EXTRA` |
| `monto` | DecimalField(18, 2) | Mayor que cero |
| `moneda` | FK `core.Moneda` | La del proyecto; la asigna el servicio |
| `fecha_programada` | DateField | |
| `estado` | CharField, enum `EstadoPago` | `PROGRAMADO`, `PAGADO`, `ANULADO` |
| `fecha_pago` | DateField | Nula hasta pagar |
| `referencia_pago` | CharField(100) | Vacía hasta pagar |
| `tasa_a_usd` | DecimalField(18, 6) | Nula hasta pagar; la de la fecha de pago |
| `monto_usd` | DecimalField(18, 2) | Nulo hasta pagar |
| `documento` | FK `catalogo.DocumentoOficial` | Opcional, `PROTECT` |
| `observaciones` | TextField | Opcional |

**Constraints:** monto > 0; un pago `PAGADO` tiene fecha, referencia y tasa.
**Índices:** `estado`, `fecha_programada`.

Respecto de `docs/modelo-datos.md`: `PagoConstructora` no repite `constructora`
(sale del proyecto, y dos campos con el mismo dato terminarían
desincronizados) ni `porcentaje_obra_cubierto` (el avance vive en el proyecto).
Se actualiza ese documento en el PR de implementación.

## 5. API

Configuración común de la spec 001. Permisos con `TieneRol` (regla 24). Las
acciones que no son CRUD van como subrecurso, como en ventas
(`docs/arquitectura.md` §4).

| Método | Ruta | Escriben |
|---|---|---|
| GET · POST | `/api/v1/contratos-compra/` | Admin., gerencia |
| GET | `/api/v1/contratos-compra/{id}/` | — |
| POST | `/api/v1/contratos-compra/{id}/completar/` | Admin., gerencia |
| POST | `/api/v1/contratos-compra/{id}/anular/` | Admin., gerencia |
| GET · POST | `/api/v1/proyectos-construccion/` | Admin., gerencia |
| GET · PATCH | `/api/v1/proyectos-construccion/{id}/` | Admin., gerencia |
| POST | `/api/v1/proyectos-construccion/{id}/iniciar/` · `/avance/` · `/suspender/` · `/reanudar/` · `/finalizar/` · `/cancelar/` | Admin., gerencia |
| GET · POST | `/api/v1/proyectos-construccion/{id}/pagos/` | Admin., gerencia, contabilidad |
| GET | `/api/v1/pagos-constructora/` | — |
| POST | `/api/v1/pagos-constructora/{id}/pagar/` · `/anular/` | Admin., gerencia, contabilidad |

**Filtros:**
- `/contratos-compra/`: `?estado=`, `?proveedor=`, `?propiedad=`, `?fecha_desde=`, `?fecha_hasta=`
- `/proyectos-construccion/`: `?estado=`, `?constructora=`, `?propiedad=`
- `/pagos-constructora/`: `?estado=`, `?proyecto=`, `?tipo=`

**Ejemplo** (`POST /api/v1/contratos-compra/`):

```json
{
  "proveedor": 1,
  "propiedad": 7,
  "fecha_compra": "2026-10-30",
  "monto": "850000.00",
  "gastos_legales": "12000.00",
  "impuestos": "25500.00",
  "moneda": 1,
  "observaciones": "Compra a banco por adjudicación."
}
```

Responde 201 con `codigo` (`CC-00001`), `estado` (`EN_PROCESO`), `costo_total`
(`887500.00`), `tasa_a_usd` y `costo_total_usd`, y los resúmenes de proveedor,
propiedad y moneda.

Las acciones con motivo (`/anular/`, `/suspender/`, `/cancelar/`) reciben
`{"motivo": "..."}`. `/avance/` recibe `{"porcentaje": 40, "descripcion": "..."}`.
`/pagar/` recibe `{"fecha_pago": "2026-10-31", "referencia_pago": "TRF-123"}`.

**El detalle del proyecto** (`GET /proyectos-construccion/{id}/`) incluye
`total_comprometido`, que calcula el selector del mismo nombre (§6), y
`disponible` (presupuesto menos comprometido), los dos en la moneda del
proyecto. Así la pantalla de la spec 018 no suma los pagos por su cuenta.

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `PROPIEDAD_NO_DISPONIBLE` | La propiedad no está en el estado que la operación exige (reglas 1, 6, 9, 12, 15, 16). Se reutiliza la excepción de `catalogo` | 409 |
| `PROPIEDAD_CON_CONTRATO` | Ya tiene un contrato no anulado (regla 2) | 409 |
| `PROPIEDAD_CON_PROYECTO` | Ya tiene un proyecto activo (regla 10) | 409 |
| `TRANSICION_INVALIDA` | La acción no es posible en el estado actual del contrato, proyecto o pago | 409 |
| `AVANCE_INVALIDO` | El porcentaje baja o pasa de 100, o se finaliza sin llegar a 100 (reglas 13 y 15) | 400 |
| `PRESUPUESTO_EXCEDIDO` | Los pagos superarían el presupuesto, o el presupuesto quedaría por debajo de lo pagado (reglas 17 y 19) | 409 |
| `FECHA_INVALIDA` | Fecha futura, o fecha de pago anterior al inicio (reglas 4 y 21) | 400 |
| `PROVEEDOR_CON_CONTRATOS` · `CONSTRUCTORA_CON_PROYECTOS` | Desactivación bloqueada (reglas 22 y 23) | 409 |

`TipoCambioNoDisponible` (422) y `DocumentoDeOtraPropiedad` (409) se reutilizan
de `core` y `catalogo`.

## 6. Servicios y selectores

```python
# compras/services.py  (transaction.atomic y registrar_auditoria)
def crear_contrato_compra(*, datos: dict, autor, ip) -> ContratoCompra
def completar_contrato_compra(*, contrato: ContratoCompra, autor, ip) -> ContratoCompra
def anular_contrato_compra(*, contrato: ContratoCompra, motivo: str, autor, ip) -> ContratoCompra

# construccion/services.py
def crear_proyecto(*, datos: dict, autor, ip) -> ProyectoConstruccion
def actualizar_proyecto(*, proyecto, datos: dict, autor, ip) -> ProyectoConstruccion
def iniciar_proyecto(*, proyecto, autor, ip) -> ProyectoConstruccion
def registrar_avance(*, proyecto, porcentaje: int, descripcion: str, autor, ip) -> ProyectoConstruccion
def suspender_proyecto(*, proyecto, motivo: str, autor, ip) -> ProyectoConstruccion
def reanudar_proyecto(*, proyecto, autor, ip) -> ProyectoConstruccion
def finalizar_proyecto(*, proyecto, autor, ip) -> ProyectoConstruccion
def cancelar_proyecto(*, proyecto, motivo: str, autor, ip) -> ProyectoConstruccion
def programar_pago(*, proyecto, datos: dict, autor, ip) -> PagoConstructora
def pagar(*, pago, fecha_pago: date, referencia: str, autor, ip) -> PagoConstructora
def anular_pago(*, pago, motivo: str, autor, ip) -> PagoConstructora
```

**Concurrencia:** cada acción bloquea la fila del contrato o del proyecto con
`select_for_update()` antes de revisar su estado, como la spec 004 hace con los
agentes. Así, dos peticiones que completan o pagan al mismo tiempo no pasan las
dos la validación. `programar_pago` bloquea el proyecto antes de sumar sus
pagos, para que dos pagos simultáneos no superen juntos el presupuesto.

**Estado de la propiedad:** siempre con `cambiar_estado_propiedad(...,
estado_requerido=...)`, dentro de la misma transacción. Si la propiedad no está
en el estado requerido, se revierte todo (reglas 6, 12, 15 y 16).

**Tasa al dólar:** con el selector de tipo de cambio de `core`, igual que
`_tasa_a_dolar` de ventas: el dólar tiene tasa 1 y sin tasa se rechaza.

**Selectores:** `listar_contratos_compra()`, `listar_proyectos()`,
`listar_pagos()`, `total_comprometido(*, proyecto)` (suma de programados y
pagados; la usan `programar_pago`, `actualizar_proyecto` y el detalle del
proyecto), `existe_contrato_no_anulado(*, propiedad)`,
`existe_proyecto_activo(*, propiedad)`, `proveedor_tiene_contratos_en_proceso`
y `constructora_tiene_proyectos_activos`.

## 7. Auditoría

| Acción | Cuándo |
|---|---|
| `CREAR` | Registrar un contrato, un proyecto o un pago |
| `ACTUALIZAR` | Completar, iniciar, avanzar, suspender, reanudar, finalizar, editar un proyecto, pagar |
| `ANULAR` | Anular un contrato o un pago; cancelar un proyecto |

Los valores guardan el estado anterior y el nuevo, y lo propio de cada acción:
el motivo, el porcentaje y la descripción del avance, o la fecha y la
referencia del pago. El cambio de estado de la propiedad lo audita
`cambiar_estado_propiedad`. Entidades: `compras_contratocompra`,
`construccion_proyectoconstruccion` y `construccion_pagoconstructora`.

## 8. Criterios de aceptación

- [x] Registrar un contrato sobre una propiedad `EN_NEGOCIACION` crea `CC-00001`
      con su costo total, su tasa y su costo en dólares, sin cambiar la propiedad.
- [x] Completarlo deja la propiedad `ADQUIRIDA`; completarlo otra vez responde 409.
- [x] Un segundo contrato no anulado sobre la misma propiedad responde 409; tras
      anular el primero, se acepta.
- [x] Anular un contrato completado responde 409; anular uno en proceso sin
      motivo responde 400.
- [x] Un proyecto sobre una propiedad que no está `ADQUIRIDA` responde 409.
- [x] Iniciar deja la propiedad `EN_CONSTRUCCION`; finalizar con avance 100 la
      deja `DISPONIBLE`, junto con sus unidades en negociación o en
      construcción, y guarda la fecha de hoy; finalizar con avance menor
      responde 400.
- [x] Un `ANTICIPO` se paga con fecha anterior al inicio de la obra; otro tipo de
      pago con esa fecha responde 400.
- [x] En un proyecto finalizado se puede subir el presupuesto y pagar el
      finiquito.
- [x] Si la propiedad se movió a mano durante la obra, cancelar el proyecto
      funciona y finalizar responde 409 con el estado actual.
- [x] Un avance menor que el anterior, o mayor que 100, responde 400.
- [x] Cancelar una obra iniciada devuelve la propiedad a `ADQUIRIDA` y anula sus
      pagos programados.
- [x] Un pago que supere el presupuesto responde 409; tras subir el presupuesto,
      se acepta. Bajar el presupuesto por debajo de lo comprometido responde 409.
- [x] Un `FINIQUITO` para un proyecto no finalizado responde 409.
- [x] El detalle de un proyecto devuelve `total_comprometido` y `disponible`;
      al programar un pago, el comprometido sube y el disponible baja en su
      monto, y al anularlo vuelven a su valor.
- [x] Pagar guarda fecha, referencia, tasa y monto en dólares; anular un pago
      pagado responde 409.
- [x] `CONTABILIDAD` paga pero no crea contratos ni proyectos (403); `AGENTE` y
      `CONSULTA` solo leen.
- [x] Desactivar un proveedor con un contrato en proceso, o una constructora con
      un proyecto activo, responde 409.
- [x] Cada operación queda en la bitácora del sistema.
- [x] Los comandos de demostración no duplican nada al correrlos dos veces.
- [x] `ruff`, `makemigrations --check` y `pytest` pasan (`docs/convenciones.md` §1.1).

## 9. Pruebas

- **Servicios:** cada transición válida y cada una inválida, los cambios de
  estado de la propiedad y su reversión cuando la propiedad no está en el
  estado requerido, el presupuesto, la tasa y la auditoría de cada acción.
- **Modelos:** los constraints (costo total, avance, unicidad de contrato y
  proyecto activos).
- **API:** la matriz de permisos, un caso feliz por acción y el formato de los
  errores.

## 10. Decisiones y alternativas descartadas

**Solo se construye sobre una propiedad `ADQUIRIDA` (decidido por el
integrante C).** Permitir remodelar una propiedad `DISPONIBLE` obligaría a
decidir qué pasa con sus cotizaciones y arrendamientos mientras está en obra.
Se deja para una spec posterior.

**Pagos: administración, gerencia y contabilidad (decidido por el integrante
C).** Mismo criterio que los pagos de cuotas de ventas (spec 007): contabilidad
registra pagos, pero no decide compras ni obras.

**El presupuesto no se supera; se sube (decidido por el integrante C).**
`modelo-datos.md` pide una "autorización explícita" para pagar más que el
presupuesto. Se descartó una entidad de autorizaciones: subir el presupuesto ya
es una decisión explícita de administración o gerencia, y queda en la bitácora
con el valor anterior y el nuevo.

**Avance como porcentaje del proyecto, sin `AvanceObra` (decidido por el
integrante C).** El historial de cada avance queda en la bitácora con su
descripción. Se puede agregar la entidad después sin cambiar la API de avance.

**Contratos sin edición.** Un contrato en proceso con un error se anula y se
registra otro. Así cada versión queda en la bitácora con su motivo, y no hace
falta recalcular costo, tasa y conversión al editar.

**Tasa al dólar guardada, como en ventas.** Los reportes en dólares no deben
cambiar el pasado cuando se corrige o se agrega una tasa (spec 007, regla 14).

**Revisión de Marco (PR #64), cinco decisiones.** (1) La reventa sin obra usa
`/cambiar-estado/` y no una acción nueva: ya audita con motivo y evita duplicar
una herramienta de A (regla 25). (2) Finalizar publica también las unidades en
negociación: sin eso, un edificio terminado quedaría sin nada que cotizar
(regla 15). (3) El anticipo se puede pagar antes del inicio, porque es justo su
razón de ser (regla 21). (4) El presupuesto de un proyecto finalizado se puede
subir, para no dejar un finiquito sin forma de pagarse (regla 17). (5) Ante un
cambio manual de estado, cancelar siempre funciona y finalizar explica cómo
salir; si `/cambiar-estado/` debe bloquear las propiedades en obra se decide
con A, porque es su servicio (regla 26).

**Bloqueo de filas en cada acción.** Sin `select_for_update()`, dos pagos
simultáneos podrían pasar juntos el presupuesto, o dos peticiones completar el
mismo contrato. Mismo criterio que la spec 004 con los agentes.

**Unicidad de contrato y proyecto activos en la base.** Constraints con
condición, como las cotizaciones aprobadas de la spec 007: la regla se cumple
aunque dos peticiones lleguen al mismo tiempo.

**`PagoConstructora` sin `constructora`.** Se obtiene del proyecto; guardarla
dos veces permitiría un pago a una constructora distinta de la de su obra.

**`total_comprometido` y `disponible` en el detalle del proyecto (revisión de
Douglas, PR #66).** Los pide la pantalla de la spec 018. Van aquí y no en la
018 porque son un cambio de backend: la 018 queda sin cambios en el backend y
solo los cita. Los calcula la API con el mismo selector que valida el
presupuesto (regla 19), para que la pantalla y la validación nunca den números
distintos.

**Decisiones de la implementación (2026-11-01):**

- **Finalizar publica también las unidades `EN_CONSTRUCCION` (decidido por el
  integrante C).** La demo del catálogo marca así las unidades del hotel en
  obra. Si finalizar solo publicara las `EN_NEGOCIACION`, en la demostración el
  hotel quedaría disponible con sus suites todavía "en construcción". Las dos
  significan lo mismo para una obra: la unidad aún no está a la venta
  (regla 15).
- **Dos PR en lugar de uno.** Con los cuatro incrementos juntos, el PR pasaba de
  5,000 líneas (`CLAUDE.md` §2 pide incrementos revisables). El #75 lleva
  contratos y proyectos; el segundo, pagos, demostración y este cierre.
- **La demostración es una foto, sin auditoría.** Contratos, proyectos y pagos
  se guardan con el estado que ya tienen sus propiedades en la demo del
  catálogo (el terreno en negociación, la gasolinera adquirida, el hotel en
  obra), sin pasar por los servicios que cambian estados. Es el mismo criterio
  de las specs 004 y 006, y deja la obra del hotel lista para finalizarla en la
  defensa por la API.
- **`obtener_dolar` repetido en cada app.** Ventas ya lo tenía; compras y
  construcción tienen su propia copia de una línea, porque las apps no dependen
  entre sí (§4).
- **Cancelar bloquea los pagos programados antes de anularlos.** Si alguien
  paga uno de ellos al mismo tiempo, la cancelación espera, y PostgreSQL vuelve
  a revisar el filtro sobre la fila ya pagada: un pago `PAGADO` nunca se anula.
- **El mismo porcentaje de avance se puede registrar otra vez.** "Nunca baja"
  (regla 13) permite repetirlo con otra descripción, que queda en la bitácora.
- **Editar un campo que el estado no permite responde `TRANSICION_INVALIDA`**
  (regla 17): por ejemplo, el nombre de un proyecto finalizado.
- **Nombres del esquema OpenAPI.** Para que el frontend reciba tipos con nombres
  claros, los enums de compras y construcción se agregaron a
  `ENUM_NAME_OVERRIDES` (como los de ventas y arrendamientos) y se renombraron
  tres serializadores que chocaban con los de otras apps. El esquema queda sin
  advertencias.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-31, borrador (Claude, rol C).** El agente revisó el código real
de `catalogo` (`EstadoPropiedad`, `cambiar_estado_propiedad` con
`estado_requerido`, los selectores y `DocumentoOficial`) y de `ventas`
(`ContratoVenta`, el código `CV-{id:05d}`, la tasa al dólar de la regla 14 y las
acciones como subrecurso), para seguir los mismos patrones. Las cuatro
decisiones de negocio de §10 las tomó el integrante C entre opciones planteadas
por el agente; las demás son propuestas del agente que se validan en la
revisión.

**Sesión 2026-11-01, revisión de la spec 018 (Claude, rol C).** La revisión de
Douglas en el PR #66 pidió mover `total_comprometido` a esta spec. El agente lo
agregó en §5, §6, §8 y §10, junto con `disponible`, que la regla 6 de la 018 ya
pedía calculado por la API.

**Plan de implementación (un commit por incremento):**

1. `ContratoCompra`: modelo, servicios, API y reglas de desactivación de proveedor
2. `ProyectoConstruccion`: modelo, servicios de su ciclo, API y desactivación de constructora
3. `PagoConstructora`: modelo, servicios, API
4. Datos de demostración y cierre de la spec

**Implementación, 2026-11-01 (Claude, rol C).** Los cuatro incrementos del plan
se hicieron en orden, uno por commit:

| Commit | Incremento | PR |
|---|---|---|
| `feat(compras): agregar contratos de compra con API, auditoría y regla de desactivación` | 1 | #75 |
| `feat(construccion): agregar proyectos de construcción con su ciclo, API y auditoría` | 2 | #75 |
| `feat(construccion): agregar pagos a constructoras con el control del presupuesto` | 3 | 2.º PR |
| `feat(compras, construccion): datos de demostración y cierre de la spec 017` | 4 | 2.º PR |

**Qué generó el agente.** El código de los tres modelos, sus servicios,
selectores, API, pruebas y datos de demostración. Antes de escribirlo revisó el
código real de `ventas` (`ContratoVenta`, la tasa al dólar, las acciones como
subrecurso), `catalogo` (`cambiar_estado_propiedad`, `cambiar_estado_unidad`,
sus selectores y excepciones) y las apps `compras` y `construccion` de la spec
006, para seguir los mismos patrones. Cada incremento lo corrió en una réplica
con PostgreSQL 16 y pgvector: `ruff`, `makemigrations --check`, la suite
completa y el esquema de `drf-spectacular`. Además, en cada uno quitó a
propósito las reglas nuevas (presupuesto, unicidad, desactivación, unidades,
anticipo) para comprobar que alguna prueba fallaba sin ellas.

**Qué verificó el integrante C en su máquina:** cada incremento por separado,
con las migraciones aplicadas y la suite completa (665, 744, 776 y 783
pruebas; 161 nuevas sobre las 622 de `develop`), `ruff` y
`makemigrations --check` limpios. Tomó la
decisión de la regla 15 al preparar la demostración.

**Pendiente para A (Douglas):** agregar `cargar_demo_compras` y
`cargar_demo_construccion` a `COMANDOS_DE_DEMO` de `seed_demo`, después de
`cargar_demo_catalogo`; y decidir si `/cambiar-estado/` debe rechazar las
propiedades con un proyecto activo (regla 26).
