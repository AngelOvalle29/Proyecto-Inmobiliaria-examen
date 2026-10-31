# 012 · Pantallas de CRM, ventas y arrendamientos

| Campo | Valor |
|---|---|
| **Número** | 012 |
| **Estado** | En revisión |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-30 |
| **Apps afectadas** | `frontend/` (`paginas/crm`, `paginas/ventas`, `paginas/arrendamientos` y sus hooks en `api/`). Sin cambios en el backend |
| **Rama** | `feature/012-pantallas-bloque-b` |
| **Pull request** | — |

---

## 1. Problema

El backend del bloque B ya existe (specs 004, 007 y 008), pero solo se usa por
la API. Un agente, un gerente o contabilidad necesitan pantallas para registrar
clientes, cotizar, firmar contratos y cobrar cuotas y rentas, que es lo que se
muestra en la demostración y en la defensa.

## 2. Alcance

**Incluye** (decidido por B: todo el bloque):
- **CRM:** clientes, agentes y cotizaciones.
- **Ventas:** contratos de venta, su detalle con las cuotas y el pago de cuotas.
- **Arrendamientos:** contratos, su detalle con el calendario de pagos, el pago
  de rentas, y renovar, rescindir y finalizar.

Todo con los componentes de la spec 010 (`TablaDatos`, `FormularioDatos`,
`CampoRelacion`, `RutaProtegida`) y siguiendo `ListaPropiedades` y
`NuevaPropiedad` como ejemplo.

**No incluye:**
- Cambios en el backend: las pantallas usan los endpoints que ya existen.
- Gráficas, tableros y reportes (rol D).
- Reactivar clientes o agentes desactivados (spec 004, §2).
- Pruebas automáticas del frontend (spec 010, §10): la verificación es manual,
  con los criterios de §8.

## 3. Reglas

1. **Una pantalla por lista, formulario y detalle**, y nada más (`CLAUDE.md`
   §11): las listas son `TablaDatos`, los formularios son `FormularioDatos`, y
   las acciones que piden datos son un diálogo de la página, como
   `DialogoCambiarEstado` del catálogo.
2. **El menú y las rutas siguen los permisos del backend** (reglas de las specs
   004, 007 y 008). Ocultar no es seguridad: el backend responde 403 de todos
   modos. Las acciones de una fila se ocultan si el rol no puede hacerlas o si
   el estado no lo permite (por ejemplo, Aprobar en una cotización que no está
   enviada).
3. **La cartera la decide el backend.** Un agente ve en las listas solo lo
   suyo, porque la API ya lo filtra; el frontend no filtra nada por su cuenta.
4. **Los formularios validan el formato con Zod y las reglas las valida la
   API.** Los campos obligatorios solo para un caso (los de persona o empresa
   en un cliente, el plan de cuotas en una venta financiada) se declaran
   opcionales en el esquema y se exigen con `superRefine` según el campo que
   los activa, porque `visibleSi` oculta el campo pero Zod lo sigue validando
   (observación de B en la revisión de #46).
5. **Los errores de negocio se muestran con el mensaje de la API**: un 409
   (`PROPIEDAD_NO_DISPONIBLE`, `CONTRATO_CON_PAGOS`…) arriba de la tabla o del
   formulario, y un 400 de validación junto a su campo (spec 010, regla 8).
6. **Lo que está en mora se marca.** Las cuotas con `en_mora` y los pagos de
   renta con `en_mora` se resaltan en su tabla, y las cotizaciones con `vencida`
   también.
7. **Todo monto con su moneda** (`formatearMoneda`) y las fechas como
   `dd/mm/aaaa` (`formatearFecha`).
8. **Una cotización aprobada se firma desde su fila** (decidido por B): la
   acción Firmar contrato abre el formulario de firma con la cotización ya
   elegida, y solo faltan la fecha, la modalidad y el plan. Nuevo contrato, en
   la lista de contratos, firma sin cotización.

## 4. Modelo de datos

Sin cambios. Los tipos salen de `npm run gen:api`.

## 5. Pantallas y rutas

| Ruta | Pantalla | Roles que la ven |
|---|---|---|
| `/crm/clientes` | Lista: código, nombre, tipo, país, agente. Filtros: tipo, país, `?buscar=`. Acciones: Editar, Reasignar (diálogo), Desactivar | Todos (escriben admin, gerente y agente) |
| `/crm/clientes/nuevo` · `/crm/clientes/{id}/editar` | Formulario: tipo; nombre, apellidos y documento si es persona; razón social y NIT si es empresa; país y ciudad (la ciudad depende del país) | Admin, gerente, agente |
| `/crm/agentes` | Lista: código, nombre, país, comisión, clientes activos. Acciones: Editar comisión (diálogo), Desactivar | Todos (escriben admin y gerente) |
| `/crm/agentes/nuevo` | Formulario: usuario, comisión, fecha de ingreso | Admin, gerente |
| `/crm/cotizaciones` | Lista: código, cliente, bien, total, estado, vencida. Filtro: estado. Acciones: Enviar, Aprobar, Rechazar, Firmar contrato (según el estado) | Todos (escriben admin, gerente y agente) |
| `/crm/cotizaciones/nueva` | Formulario: cliente, propiedad o unidad, fecha de vencimiento, descuento | Admin, gerente, agente |
| `/ventas/contratos` | Lista: código, cliente, bien, monto, modalidad, estado | Todos |
| `/ventas/contratos/nuevo` | Formulario de firma, con o sin cotización (`?cotizacion=<id>`); el plan de cuotas aparece solo si es financiado | Admin, gerente, agente |
| `/ventas/contratos/{id}` | **Detalle** (decidido por B): datos del contrato y tabla de cuotas con su mora. Acciones: Pagar cuota (diálogo: monto, fecha, referencia), Anular | Todos (pagan admin, gerente y contabilidad; anulan admin y gerente) |
| `/arrendamientos/contratos` | Lista: código, cliente, bien, renta, fin, estado. Filtro: estado | Todos |
| `/arrendamientos/contratos/nuevo` | Formulario de firma | Admin, gerente, agente |
| `/arrendamientos/contratos/{id}` | **Detalle**: datos y calendario de pagos con su mora. Acciones: Pagar renta (diálogo: fecha, monto, referencia), Renovar (diálogo), Rescindir (diálogo con la fecha), Finalizar | Todos (permisos de la spec 008, reglas 13 a 15) |

En el diálogo de Pagar renta, el monto se propone con la renta y el recargo
que corresponderían a la fecha elegida, y quien registra lo confirma. La API
sigue siendo la que valida (`MONTO_INCORRECTO`).

**Menú**, agrupado: *CRM* (Clientes, Cotizaciones, Agentes), *Ventas*
(Contratos de venta) y *Arrendamientos* (Contratos de arrendamiento). Las
entradas de "Nuevo…" están en el botón de cada lista, no en el menú.

## 6. Componentes y módulos

```
src/api/crm/          consultas.ts (useClientes, useAgentes, useCotizaciones, búsquedas)
                      mutaciones.ts (crear, editar, desactivar, reasignar, enviar, aprobar…)
src/api/ventas/       consultas.ts (useContratosVenta, useContratoVenta)
                      mutaciones.ts (useFirmarContrato, usePagarCuota, useAnularContrato)
src/api/arrendamientos/  consultas.ts y mutaciones.ts, con el mismo patrón
src/paginas/crm/         ListaClientes, FormularioCliente, ListaAgentes, NuevoAgente,
                         ListaCotizaciones, NuevaCotizacion, DialogoReasignar…
src/paginas/ventas/      ListaContratosVenta, FirmarContratoVenta, DetalleContratoVenta,
                         DialogoPagarCuota
src/paginas/arrendamientos/  ListaArrendamientos, FirmarArrendamiento,
                             DetalleArrendamiento, DialogoPagarRenta,
                             DialogoRenovar, DialogoRescindir
```

Cada mutación invalida la consulta de su lista y de su detalle, para que la
tabla se actualice sola, como en el catálogo.

**Depende de A (#46):** que `CampoRelacion` acepte una etiqueta inicial, para
que el formulario de edición de clientes muestre el país y la ciudad actuales
(observación de B en la revisión de #46). Si no llega, la edición de un
cliente no cambia su país ni su ciudad, y se registra aquí.

**Estado al 2026-10-30:** la etiqueta inicial aún no existe, así que la edición
de un cliente no cambia su país ni su ciudad. Tampoco cambia su tipo, y el
agente se cambia con Reasignar.

**Agregado al implementar cotizaciones:** `FormularioDatos` tiene el tipo de
campo `fecha`, que también usarán los formularios de firma, y solo pone junto
a un campo los `detalles` de un 400 de validación: los de un 409 son datos del
caso, y su mensaje va arriba (regla 5). El buscador de unidad filtra la primera
página de `/propiedades/{id}/unidades/`, porque ese endpoint no tiene búsqueda.

## 7. Auditoría

No aplica: el frontend no escribe en la bitácora. Cada acción llama a un
endpoint que ya audita (specs 004, 007 y 008).

## 8. Criterios de aceptación

- [ ] Un agente ve solo sus clientes, cotizaciones y contratos; un gerente ve
      todos
- [ ] `CONSULTA` y `CONTABILIDAD` no ven los botones de crear, editar ni las
      acciones que no les corresponden; y `CONTABILIDAD` sí ve Pagar
- [ ] El formulario de cliente cambia entre persona y empresa, y no envía los
      campos ocultos; un documento repetido muestra el 409 de la API
- [ ] La ciudad se busca dentro del país elegido y se vacía al cambiarlo
- [ ] Una cotización pasa de borrador a enviada y a aprobada desde su fila, y
      su propiedad aparece como reservada en el catálogo
- [ ] Firmar contrato desde una cotización aprobada llega al formulario con la
      cotización elegida y crea el contrato
- [ ] Un contrato financiado muestra sus cuotas; las vencidas se marcan en mora
- [ ] Pagar una cuota a medias la deja parcial, y pagar de más muestra el error
      de la API
- [ ] Un arrendamiento muestra su calendario; pagar tarde propone el recargo y
      un monto equivocado muestra el esperado
- [ ] Renovar, rescindir y finalizar funcionan desde el detalle y muestran los
      errores de la API (renovar uno vencido, rescindir con fecha futura…)
- [ ] Montos con su moneda y fechas `dd/mm/aaaa`
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Manual, local | Cada criterio de §8 con `seed_demo` y un usuario por rol |
| Manual, producción | Un recorrido completo en Vercel: cotizar, aprobar, firmar y pagar |
| Estático | `typecheck` con los tipos generados |

## 10. Decisiones y alternativas descartadas

**Decididas por B:** todo el bloque en esta spec (se descartó dejar agentes y
la edición para después: son pantallas cortas sobre los mismos componentes);
página de detalle para contratos (se descartó un diálogo, porque un contrato de
60 cuotas no cabe cómodo); firmar desde la fila de la cotización aprobada (se
descartó buscar la cotización dentro del formulario de contrato).

**Propuestas del agente, a validar en la revisión:**
- *Las acciones que piden datos son diálogos de la página*, como
  `DialogoCambiarEstado`, y no un componente genérico nuevo: cada una pide
  campos distintos, y `FormularioDatos` dentro del diálogo ya cubre la
  validación y los errores.
- *El monto del pago de renta se propone, no se calcula en el frontend como
  verdad*: la regla del recargo vive en el backend (`calcular_recargo`); la
  pantalla solo ayuda a no escribirlo mal.
- *Los "Nuevo…" van en el botón de cada lista*, no en el menú: el menú quedaría
  con 15 entradas.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-30 (Claude Code, rol B).** El agente leyó las specs 004, 007,
008 y 010, `docs/frontend.md` y el código de la base del frontend en #46, y
propuso el borrador. Las tres decisiones de §10 las tomó B entre opciones
planteadas por el agente.

**Plan de implementación:** (1) CRM: clientes y agentes; (2) cotizaciones;
(3) ventas: lista, firma y detalle con pagos; (4) arrendamientos: lista, firma,
detalle y sus acciones; (5) verificación de §8.
