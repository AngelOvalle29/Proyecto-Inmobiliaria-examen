# 018 · Pantallas de compras, construcción y el asistente

| Campo | Valor |
|---|---|
| **Número** | 018 |
| **Estado** | En revisión |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `frontend/` (`paginas/compras`, `paginas/construccion`, `paginas/asistente` y sus hooks en `api/`). En el backend, solo el campo `total_comprometido` del proyecto (§4) |
| **Rama** | `feature/018-pantallas-bloque-c` |
| **Pull request** | — |

---

## 1. Problema

El backend del bloque C ya existe o está por implementarse (specs 005, 006 y
017), pero solo se usa por la API. Administración, gerencia y contabilidad
necesitan pantallas para registrar proveedores y constructoras, comprar
propiedades, seguir las obras y pagarlas; y un visitante necesita dónde
preguntarle al asistente. Es lo que se muestra en la demostración y en la
defensa.

## 2. Alcance

**Incluye:**
- **Compras:** proveedores (spec 006) y contratos de compra (spec 017).
- **Construcción:** constructoras (spec 006), proyectos con su detalle, su
  avance y sus pagos (spec 017).
- **Asistente:** la pantalla de consulta al agente de IA, con las citas de cada
  respuesta (spec 005).

Todo con los componentes de la spec 010 (`TablaDatos`, `FormularioDatos`,
`CampoRelacion`, `RutaProtegida`) y siguiendo las pantallas de la spec 012 como
ejemplo.

**No incluye:**
- Cambios en el backend, salvo `total_comprometido` (§4): las pantallas usan los
  endpoints que ya existen.
- Reactivar proveedores o constructoras desactivados (spec 006, §2).
- Cargar o editar los documentos del asistente: se cargan con `cargar_demo_ia`
  (spec 005).
- Gráficas, tableros y reportes (rol D).
- Pruebas automáticas del frontend (spec 010, §10): la verificación es manual,
  con los criterios de §8.

**Orden:** las pantallas de proveedores, constructoras y el asistente se
implementan primero, porque su API ya está en revisión (#62 y #63). Las de
contratos, proyectos y pagos, cuando la spec 017 esté implementada.

## 3. Reglas

1. **Una pantalla por lista, formulario y detalle** (`CLAUDE.md` §11): las listas
   son `TablaDatos`, los formularios son `FormularioDatos` y las acciones que
   piden datos son un diálogo de la página, como en la spec 012.
2. **El menú y las rutas siguen los permisos del backend:** proveedores,
   constructoras, contratos y proyectos los escriben administración y gerencia;
   los pagos, administración, gerencia y contabilidad (spec 006, regla 10;
   spec 017, regla 24). Ocultar no es seguridad: el backend responde 403 de
   todos modos.
3. **Las acciones dependen del estado.** Completar o Anular solo en un contrato
   `EN_PROCESO`; Iniciar solo en un proyecto `PLANIFICADO`; Registrar avance,
   Suspender y Finalizar solo en `EN_EJECUCION`; Reanudar solo en `SUSPENDIDO`;
   Pagar y Anular solo en un pago `PROGRAMADO`. Finalizar se ofrece solo con
   avance 100.
4. **Los formularios validan el formato con Zod y las reglas las valida la
   API.** El NIT del proveedor es opcional en el esquema, porque solo el
   propietario particular puede omitirlo; si falta en otro tipo, la API
   responde `NIT_OBLIGATORIO` y se muestra junto al campo.
5. **Los errores de negocio se muestran con el mensaje de la API**: un 409
   (`PROVEEDOR_DUPLICADO`, `PROPIEDAD_NO_DISPONIBLE`, `PRESUPUESTO_EXCEDIDO`…)
   arriba de la tabla o del formulario, y un 400 de validación junto a su campo
   (spec 010, regla 8).
6. **Todo monto con su moneda** (`formatearMoneda`) y las fechas como
   `dd/mm/aaaa` (`formatearFecha`). El costo total de un contrato y el
   disponible de un proyecto se muestran como los calcula la API; el formulario
   solo adelanta la suma como ayuda.
7. **Los formularios de compra y de proyecto ofrecen solo las propiedades que
   la operación acepta:** en `EN_NEGOCIACION` para comprar y `ADQUIRIDA` para
   construir, con el filtro `?estado=` de `/propiedades/`. La API sigue siendo la
   que valida.
8. **El asistente es público** (decisión a validar, §10): se abre sin iniciar
   sesión, en `/asistente`, y también aparece en el menú de quien sí inició
   sesión.
9. **En el asistente, cada `[n]` de la respuesta apunta a su cita**, que se
   muestra debajo con documento, sección y extracto. Una respuesta
   `sin_informacion` se muestra como tal, sin citas. Un 503 dice que el
   asistente no está disponible y un 429 cuántos segundos esperar
   (`espera_segundos`).

## 4. Modelo de datos

Sin cambios de modelo. Los tipos salen de `npm run gen:api`.

**Un campo nuevo en la API:** el detalle de `/proyectos-construccion/{id}/`
incluye `total_comprometido` (la suma de pagos programados y pagados que ya
calcula el selector de la spec 017). Así la pantalla muestra presupuesto,
comprometido y disponible sin sumar los pagos por su cuenta. Se agrega en la
implementación de la spec 017.

## 5. Pantallas y rutas

| Ruta | Pantalla | Roles que la ven |
|---|---|---|
| `/compras/proveedores` | Lista: código, nombre, tipo, NIT, país. Filtros: tipo, país, `?buscar=`. Acciones: Editar, Desactivar | Todos (escriben admin y gerente) |
| `/compras/proveedores/nuevo` · `/compras/proveedores/{id}/editar` | Formulario: tipo, nombre, NIT, correo, teléfono, país, ciudad (depende del país), dirección | Admin, gerente |
| `/compras/contratos` | Lista: código, proveedor, propiedad, fecha, costo total, estado. Filtro: estado. Acciones: Completar (con confirmación), Anular (diálogo con motivo) | Todos (escriben admin y gerente) |
| `/compras/contratos/nuevo` | Formulario: proveedor, propiedad en negociación, fecha, monto, gastos legales, impuestos, moneda, observaciones | Admin, gerente |
| `/construccion/constructoras` | Lista: código, nombre, NIT, país, calificación. Filtros: país, calificación mínima, `?buscar=`. Acciones: Editar, Desactivar | Todos (escriben admin y gerente) |
| `/construccion/constructoras/nueva` · `/construccion/constructoras/{id}/editar` | Formulario: nombre, NIT, contacto, correo, teléfono, país, calificación (opcional, 1 a 5) | Admin, gerente |
| `/construccion/proyectos` | Lista: código, nombre, propiedad, constructora, estado, avance. Filtro: estado | Todos |
| `/construccion/proyectos/nuevo` | Formulario: nombre, propiedad adquirida, constructora, fechas de inicio y fin estimada, presupuesto, moneda | Admin, gerente |
| `/construccion/proyectos/{id}` | **Detalle** (decisión a validar, §10): datos, barra de avance, presupuesto / comprometido / disponible y tabla de pagos. Acciones del proyecto: Iniciar, Registrar avance, Suspender, Reanudar, Finalizar, Cancelar y Editar (diálogos según el estado). Programar pago (diálogo: tipo, monto, fecha, documento). Por pago: Pagar (diálogo: fecha y referencia) y Anular (diálogo con motivo) | Todos (proyecto: admin y gerente; pagos: admin, gerente y contabilidad) |
| `/asistente` | Pregunta, respuesta con sus marcas `[n]` y la lista de citas. Mantiene las preguntas de la sesión en pantalla; no se guardan | Público |

**Menú**, agrupado: *Compras* (Proveedores, Contratos de compra),
*Construcción* (Constructoras, Proyectos) y *Asistente*. Las entradas de
"Nuevo…" están en el botón de cada lista, como en la spec 012.

## 6. Componentes y módulos

```
src/api/compras/        consultas.ts (useProveedores, useContratosCompra, búsquedas)
                        mutaciones.ts (crear, editar y desactivar proveedor;
                                       crear, completar y anular contrato)
src/api/construccion/   consultas.ts (useConstructoras, useProyectos, useProyecto)
                        mutaciones.ts (constructoras; las acciones del proyecto;
                                       programar, pagar y anular pago)
src/api/ia/             mutaciones.ts (useConsultarAgente)
src/paginas/compras/       ListaProveedores, FormularioProveedor,
                           ListaContratosCompra, NuevoContratoCompra,
                           DialogoMotivo
src/paginas/construccion/  ListaConstructoras, FormularioConstructora,
                           ListaProyectos, NuevoProyecto, DetalleProyecto,
                           DialogoAvance, DialogoEditarProyecto,
                           DialogoProgramarPago, DialogoPagar
src/paginas/asistente/     Asistente, RespuestaConCitas
```

Cada mutación invalida la consulta de su lista y de su detalle, para que la
tabla se actualice sola, como en el catálogo y en la spec 012. Una acción del
proyecto invalida también la lista de propiedades, porque cambia su estado.

`DialogoMotivo` sirve a todas las acciones que solo piden un motivo (anular un
contrato o un pago, suspender o cancelar un proyecto), con el título y la
mutación que le pase cada página.

`RespuestaConCitas` convierte cada `[n]` del texto en un enlace a la cita `n` de
la lista. Si el modelo menciona un número que no está en las citas, se deja como
texto.

**Si `CampoRelacion` aún no acepta una etiqueta inicial** (spec 012, §6), la
edición de un proveedor no cambia su país ni su ciudad, ni la de una
constructora su país, y se registra aquí.

## 7. Auditoría

No aplica: el frontend no escribe en la bitácora. Cada acción llama a un
endpoint que ya audita (specs 005, 006 y 017).

## 8. Criterios de aceptación

- [ ] `CONSULTA` y `AGENTE` ven las listas de compras y construcción sin botones
      de crear ni acciones; `CONTABILIDAD` ve Pagar y Programar pago, pero no
      las acciones del proyecto.
- [ ] Un proveedor particular se registra sin NIT; un banco sin NIT muestra el
      error junto al campo; un NIT repetido muestra el 409 de la API.
- [ ] La ciudad del proveedor se busca dentro del país elegido y se vacía al
      cambiarlo.
- [ ] Una constructora con calificación 6 muestra el error de validación.
- [ ] El formulario de compra solo ofrece propiedades en negociación; al
      completar el contrato, la propiedad aparece como adquirida en el catálogo.
- [ ] Un proyecto se inicia, avanza, se suspende, se reanuda y se finaliza desde
      su detalle, y la propiedad pasa a en construcción y luego a disponible.
- [ ] El detalle muestra presupuesto, comprometido y disponible; un pago que
      supera el presupuesto muestra el 409, y tras subir el presupuesto se acepta.
- [ ] Pagar un pago programado guarda su fecha y referencia, y deja de ofrecer
      Pagar y Anular.
- [ ] El asistente responde sin iniciar sesión, con sus marcas `[n]` enlazadas a
      las citas; una pregunta ajena muestra que no hay información, sin citas.
- [ ] Con el asistente sin llave o con Gemini caído, la pantalla muestra que no
      está disponible y no se rompe.
- [ ] Montos con su moneda y fechas `dd/mm/aaaa`.
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan.

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Manual, local | Cada criterio de §8 con `seed_demo`, `cargar_demo_ia` y un usuario por rol |
| Manual, producción | Un recorrido en Vercel: comprar, construir, pagar y preguntar al asistente. **Pendiente** hasta desplegar |
| Estático | `typecheck` con los tipos generados |

## 10. Decisiones y alternativas descartadas

**Propuestas del agente, a validar por el integrante C y en la revisión:**

- *El asistente es público.* La spec 005 lo definió para visitantes sin cuenta;
  pedir sesión dejaría fuera justo a quien debería usarlo. Se descartó ponerlo
  solo dentro del sistema.
- *Página de detalle para el proyecto*, con los pagos dentro, como el detalle de
  contratos de la spec 012. Un proyecto tiene seis acciones, su avance y sus
  pagos: en un diálogo no caben cómodos. Se descartó una pantalla de pagos
  aparte, porque un pago siempre se mira junto al presupuesto de su proyecto.
- *Los contratos de compra no tienen detalle.* La lista ya muestra lo
  importante y sus dos acciones van en la fila; un contrato de compra no tiene
  cuotas ni pagos que listar.
- *Un solo `DialogoMotivo`* para las cuatro acciones que solo piden un motivo,
  en lugar de cuatro diálogos iguales.
- *`total_comprometido` lo calcula la API.* Sumar los pagos en el navegador
  daría otro número si la API cambia qué cuenta como comprometido.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-31, borrador (Claude, rol C).** El agente revisó la spec 012 de
B, `menu.ts`, `App.tsx` y los componentes `TablaDatos` y `FormularioDatos` de la
base del frontend (spec 010), y propuso el borrador siguiendo esos patrones.
Las decisiones de §10 son propuestas del agente que valida el integrante C en
la revisión.

**Plan de implementación:** (1) proveedores y constructoras; (2) asistente;
(3) contratos de compra; (4) proyectos, su detalle y sus pagos; (5) verificación
de §8.
