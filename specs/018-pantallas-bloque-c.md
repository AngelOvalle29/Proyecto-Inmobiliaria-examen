# 018 · Pantallas de compras, construcción y el asistente

| Campo | Valor |
|---|---|
| **Número** | 018 |
| **Estado** | Implementada y verificada en producción (2026-11-03) |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Douglas Gerardo Morales Velásquez (DouGMV) |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `frontend/` (`paginas/compras`, `paginas/construccion`, `paginas/asistente` y sus hooks en `api/`; `DialogoMotivo` en `componentes/comunes/`; el filtro de estado de `useOpcionesPropiedad`). Sin cambios en el backend |
| **Rama** | `feature/018-asistente-publico` (A), `feature/018-proveedores-constructoras` y `feature/018-contratos-proyectos-pagos` (C) |
| **Pull request** | [#86](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/86) (asistente) y los dos de C (proveedores y constructoras; contratos, proyectos y pagos) |

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
- Cambios en el backend: las pantallas usan los endpoints de las specs 005,
  006 y 017. `total_comprometido` y `disponible` los agrega la spec 017 (§4).
- Reactivar proveedores o constructoras desactivados (spec 006, §2).
- Cargar o editar los documentos del asistente: se cargan con `cargar_demo_ia`
  (spec 005).
- Gráficas, tableros y reportes (rol D).
- Pruebas automáticas del frontend (spec 010, §10): la verificación es manual,
  con los criterios de §8.

**Orden:** las pantallas de proveedores, constructoras y el asistente se
implementan primero, porque su API ya existe (#63 fusionado, #62 en revisión). Las de
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
   API.** El NIT del proveedor es opcional en el objeto, porque solo el
   propietario particular puede omitirlo, y el `superRefine` lo exige para los
   demás tipos, como `FormularioCliente` con la empresa (spec 012, regla 4):
   ese aviso sale junto al campo antes de enviar. La regla de verdad sigue
   siendo la de la API: su `NIT_OBLIGATORIO` es un error de dominio, y desde
   #56 `FormularioDatos` los muestra arriba del formulario (spec 014,
   regla 5).
5. **Los errores de negocio se muestran con el mensaje de la API**: un 409
   (`PROVEEDOR_DUPLICADO`, `PROPIEDAD_NO_DISPONIBLE`, `PRESUPUESTO_EXCEDIDO`…)
   arriba de la tabla o del formulario, y un 400 de validación junto a su campo
   (spec 010, regla 8).
6. **Todo monto con su moneda** (`formatearMoneda`) y las fechas como
   `dd/mm/aaaa` (`formatearFecha`). El costo total de un contrato y el
   disponible de un proyecto se muestran como los calcula la API. El
   formulario de compra no adelanta la suma: `FormularioDatos` no expone sus
   valores a la página, y cambiarlo solo para una ayuda no lo justificaba
   (§11). El costo total aparece en la lista apenas se registra.
7. **Los formularios de compra y de proyecto ofrecen solo las propiedades que
   la operación acepta:** en `EN_NEGOCIACION` para comprar y `ADQUIRIDA` para
   construir. No se crea un hook nuevo: `useOpcionesPropiedad`
   (`api/catalogo/consultas.ts`) acepta un `estado` opcional y lo pasa a
   `?estado=` de `/propiedades/`, como se amplió `useUnidadesDePropiedad` en la
   spec 014 (§6). Sin `estado`, los formularios de B siguen igual. La API sigue
   siendo la que valida.
8. **El asistente es público** (decisión a validar, §10): se abre sin iniciar
   sesión, en `/asistente`, y también aparece en el menú de quien sí inició
   sesión.
9. **En el asistente, cada `[n]` de la respuesta apunta a su cita**, que se
   muestra debajo con documento, sección y extracto. Una respuesta
   `sin_informacion` se muestra como tal, sin citas. Un 503 dice que el
   asistente no está disponible y un 429 cuántos segundos esperar
   (`espera_segundos`).
10. **El asistente pide no escribir datos personales.** Es una pantalla pública
    y la capa gratuita de Gemini usa lo que recibe (`CLAUDE.md` §11). Un aviso
    fijo, visible antes de la primera pregunta y mientras se conversa, pide no
    escribir nombres, teléfonos ni números de documento.

## 4. Modelo de datos

Sin cambios de modelo. Los tipos salen de `npm run gen:api`.

El detalle de `/proyectos-construccion/{id}/` trae `total_comprometido` y
`disponible`, que agrega la spec 017 (§5). La pantalla los muestra tal cual,
sin sumar los pagos por su cuenta.

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
| `/asistente` | Aviso de no escribir datos personales (regla 10), pregunta, respuesta con sus marcas `[n]` y la lista de citas. Mantiene las preguntas de la sesión en pantalla; no se guardan | Público |

**Menú**, agrupado: *Compras* (Proveedores, Contratos de compra),
*Construcción* (Constructoras, Proyectos) y *Asistente*. Las entradas de
"Nuevo…" están en el botón de cada lista, como en la spec 012. La pantalla de
inicio de sesión lleva un enlace al asistente, para que un visitante lo
encuentre sin cuenta.

## 6. Componentes y módulos

```
src/api/compras/        consultas.ts (useProveedores, useContratosCompra, búsquedas)
                        mutaciones.ts (crear, editar y desactivar proveedor;
                                       crear, completar y anular contrato)
src/api/construccion/   consultas.ts (useConstructoras, useProyectos, useProyecto)
                        mutaciones.ts (constructoras; las acciones del proyecto;
                                       programar, pagar y anular pago)
src/api/ia/             mutaciones.ts (useConsultarAgente)
src/api/catalogo/       consultas.ts (useOpcionesPropiedad acepta `estado`)
src/componentes/comunes/   DialogoMotivo
src/paginas/compras/       ListaProveedores, FormularioProveedor,
                           ListaContratosCompra, NuevoContratoCompra
src/paginas/construccion/  ListaConstructoras, FormularioConstructora,
                           ListaProyectos, NuevoProyecto, DetalleProyecto,
                           DialogoAvance, DialogoEditarProyecto,
                           DialogoProgramarPago, DialogoPagar
src/paginas/asistente/     Asistente, RespuestaConCitas
```

Cada mutación invalida la consulta de su lista y de su detalle, para que la
tabla se actualice sola, como en el catálogo y en la spec 012. Las que cambian
el estado de una propiedad invalidan además `['catalogo']` completo, como
`useInvalidarVenta` en ventas: completar o anular un contrato de compra, y
todas las acciones del proyecto. Invalidar solo la lista no basta, porque la
ficha usa `['catalogo', 'propiedades', 'detalle', id]` y
`['catalogo', 'unidades', …]`, y finalizar cambia también las unidades
(spec 017, regla 15). Los pagos invalidan `['construccion']`, porque cambian
el comprometido del detalle.

`DialogoMotivo` vive en `componentes/comunes/`, porque no es de un dominio:
sirve a todas las acciones que solo piden un motivo (anular un contrato o un
pago, suspender o cancelar un proyecto) y también a B para anular contratos de
venta. Recibe el título y la función que llama a la mutación.

`RespuestaConCitas` convierte cada `[n]` del texto en un enlace a la cita `n` de
la lista. Si el modelo menciona un número que no está en las citas, se deja como
texto.

La edición de un proveedor muestra su país y su ciudad actuales con
`etiquetaInicial` de `CampoRelacion` (existe desde #52), y los dos se pueden
cambiar; la de una constructora, su país.

## 7. Auditoría

No aplica: el frontend no escribe en la bitácora. Cada acción llama a un
endpoint que ya audita (specs 005, 006 y 017).

## 8. Criterios de aceptación

- [x] `CONSULTA` y `AGENTE` ven las listas de compras y construcción sin botones
      de crear ni acciones; `CONTABILIDAD` ve Pagar y Programar pago, pero no
      las acciones del proyecto.
- [x] Un proveedor particular se registra sin NIT; un banco sin NIT muestra el
      error junto al campo; un NIT repetido muestra el 409 de la API.
- [x] La ciudad del proveedor se busca dentro del país elegido y se vacía al
      cambiarlo.
- [x] Al editar un proveedor se ven su país y su ciudad actuales, y cambiarlos
      se guarda.
- [x] Una constructora con calificación 6 muestra el error de validación.
- [x] El formulario de compra solo ofrece propiedades en negociación; al
      completar el contrato, la propiedad aparece como adquirida en el catálogo.
- [x] Un proyecto se inicia, avanza, se suspende, se reanuda y se finaliza desde
      su detalle, y la propiedad pasa a en construcción y luego a disponible.
- [x] Tras finalizar un proyecto, la ficha de la propiedad muestra la propiedad
      y sus unidades como disponibles sin recargar la página.
- [x] El detalle muestra presupuesto, comprometido y disponible; un pago que
      supera el presupuesto muestra el 409, y tras subir el presupuesto se acepta.
- [x] Pagar un pago programado guarda su fecha y referencia, y deja de ofrecer
      Pagar y Anular.
- [x] El asistente responde sin iniciar sesión, con sus marcas `[n]` enlazadas a
      las citas; una pregunta ajena muestra que no hay información, sin citas.
- [x] El asistente muestra el aviso de no escribir datos personales antes de la
      primera pregunta y lo mantiene visible; la pantalla de inicio de sesión
      enlaza al asistente.
- [x] Con el asistente sin llave o con Gemini caído, la pantalla muestra que no
      está disponible y no se rompe.
- [x] Montos con su moneda y fechas `dd/mm/aaaa`.
- [x] `npm run lint`, `npm run typecheck` y `npm run build` pasan.

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Manual, local | Cada criterio de §8 con `seed_demo`, `cargar_demo_ia` y un usuario por rol |
| Manual, producción | Un recorrido en Vercel: comprar, construir, pagar y preguntar al asistente. **Hecho el 2026-11-03** (§11), en modo lectura para compras y construcción |
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
- *`total_comprometido` y `disponible` los calcula la API* (spec 017). Sumar los
  pagos en el navegador daría otro número si la API cambia qué cuenta como
  comprometido.

**Revisión de Douglas (PR #66), seis cambios aceptados:**

1. *Aviso de datos personales en el asistente* (regla 10), con su criterio en
   §8: la pantalla es pública y Gemini, en su capa gratuita, usa lo que recibe.
2. *Sin el condicional de `CampoRelacion`:* `etiquetaInicial` existe desde #52,
   así que la edición sí cambia país y ciudad.
3. *`useOpcionesPropiedad` con `estado` opcional* en vez de un hook nuevo
   (regla 7), como `useUnidadesDePropiedad` en la spec 014.
4. *Las acciones que cambian una propiedad invalidan `['catalogo']` completo*
   (§6), porque la ficha y las unidades tienen sus propias claves.
5. *`total_comprometido` pasa a la spec 017*, porque es backend; esta spec queda
   sin cambios en el backend.
6. *`DialogoMotivo` en `componentes/comunes/`*, porque lo usan compras,
   construcción y ventas.

La sugerencia del enlace al asistente en el inicio de sesión también se
aceptó (§5).

## 11. Trabajo con agentes de IA

**Sesión 2026-10-31, borrador (Claude, rol C).** El agente revisó la spec 012 de
B, `menu.ts`, `App.tsx` y los componentes `TablaDatos` y `FormularioDatos` de la
base del frontend (spec 010), y propuso el borrador siguiendo esos patrones.
Las decisiones de §10 son propuestas del agente que valida el integrante C en
la revisión.

**Sesión 2026-11-01, revisión (Claude, rol C).** El agente aplicó los seis
cambios de la revisión de Douglas tras revisar en `develop` `CampoRelacion`
(`etiquetaInicial`), `useOpcionesPropiedad` y `useUnidadesDePropiedad`, y las
claves de caché del catálogo. Movió `total_comprometido` a la spec 017 y le
agregó `disponible`, que la regla 6 ya pedía calculado por la API. El
integrante C revisó y aceptó cada cambio.

**Plan de implementación:** (1) proveedores y constructoras; (2) asistente;
(3) contratos de compra; (4) proyectos, su detalle y sus pagos; (5) verificación
de §8.

**Paso 2, el asistente, implementado por A (Douglas) el 2026-11-02**, con
Claude Code y el acuerdo del equipo para el cierre, para que C se concentre en
compras y construcción:
- `/asistente` público, fuera de `RutaProtegida`, con un enlace "Iniciar
  sesión" o "Volver al sistema" según la sesión. Entrada *Asistente* en el
  menú y enlace desde el inicio de sesión.
- `RespuestaConCitas` enlaza cada `[n]` a su cita; un número que no está entre
  las citas queda como texto.
- Un 429 dice cuántos segundos esperar (`detalles.espera_segundos`); un 503,
  que el asistente no está disponible.
- `useConsultarAgente` es una mutación, no una consulta: cada pregunta es una
  llamada nueva a Gemini y no se guarda en caché.
- Verificado en local: sin sesión, el aviso, el 503 sin llave, y, con
  respuestas simuladas en el navegador, las citas, el 429 y la respuesta sin
  información. En producción el agente ya respondió con citas por la API.

**Paso 1, proveedores y constructoras, implementado por C el 2026-11-02**
(Claude, rol C), en `feature/018-proveedores-constructoras`:
- `api/compras/` y `api/construccion/` con las consultas y mutaciones de las
  dos entidades; cada escritura invalida `['compras']` o `['construccion']`.
- Listas con filtros y página en la URL, como `ListaClientes`: proveedores por
  tipo, país y `?buscar=`; constructoras por país, calificación mínima y
  `?buscar=`. Editar y Desactivar (con confirmación) solo para quien escribe.
- Formularios de crear y editar. La ciudad del proveedor depende del país
  (`dependeDe`) y al editar muestra la actual con `etiquetaInicial`.
- `ESCRIBEN_COMPRAS` y `ESCRIBEN_CONSTRUCCION` en `menu.ts`, usadas por el
  menú, las rutas y los botones (regla 2).
- **Hallazgo:** la regla 4 decía que el `NIT_OBLIGATORIO` de la API se mostraba
  junto al campo, pero desde #56 `FormularioDatos` solo pone junto a un campo
  los errores `VALIDACION`. En vez de cambiar el componente compartido, el
  esquema de Zod exige el NIT según el tipo, como el formulario de cliente, y
  la regla 4 se actualizó.
- Verificado en una réplica local (PostgreSQL 16 con pgvector, `seed_demo` y
  un usuario por rol) con un recorrido automático en el navegador:
  26 revisiones de los criterios 2 a 5 y de los permisos de CONSULTA, GERENTE
  y CONTABILIDAD, más los 409 de desactivar un proveedor con contrato en
  proceso y una constructora con proyecto activo. Prueba al revés: sin la
  regla del NIT en Zod, la revisión del aviso junto al campo falla.

**Pasos 3, 4 y 5, contratos, proyectos, pagos y verificación, implementados por
C el 2026-11-02** (Claude, rol C), en `feature/018-contratos-proyectos-pagos`:
- `DialogoMotivo` en `componentes/comunes/`: anular un contrato o un pago,
  suspender o cancelar un proyecto.
- `useOpcionesPropiedad(texto, _valores, estado)`: el `estado` va en tercer
  lugar porque `FormularioDatos` llama a cada `buscar` como
  `buscar(texto, valores)`. En segundo lugar, `NuevaCotizacion` (B), que usa el
  hook tal cual, mandaría sus valores como estado. Cada formulario de C lo
  envuelve en un hook propio que fija el estado
  (`useOpcionesPropiedadEnNegociacion`, `useOpcionesPropiedadAdquirida`).
- Contratos de compra: lista con filtro de estado; Completar (con
  confirmación) y Anular (con motivo) solo en `EN_PROCESO`; formulario de
  registro.
- Proyectos: lista con filtro de estado y formulario. El detalle muestra los
  datos, la barra de avance, presupuesto / comprometido / disponible y la
  tabla de pagos. Cada acción aparece solo en su estado (regla 3): Editar en
  uno activo con los tres campos, y en uno finalizado solo con el
  presupuesto (spec 017, regla 17); el finiquito solo se ofrece con la obra
  finalizada; Programar pago no aparece en un proyecto cancelado.
- `PAGAN_CONSTRUCCION` en `menu.ts` (administración, gerencia y contabilidad).
- Invalidación (§6): contratos y acciones del proyecto invalidan además
  `['catalogo']`; avance, edición y pagos, solo `['construccion']`.
- **Decisión:** la regla 6 pedía que el formulario de compra adelantara la suma
  como ayuda. `FormularioDatos` no expone sus valores a la página, y cambiar el
  componente compartido solo para una ayuda no se justificaba. La regla se
  actualizó.
- Verificado en la réplica con un recorrido automático en el navegador
  (33 revisiones), con propiedades creadas para la prueba: comprar (costo
  total de la API), completar (adquirida en la ficha), anular con motivo;
  crear, iniciar, programar, el 409 de presupuesto y subirlo, pagar, anular un
  pago, avanzar, el avance que baja, suspender, reanudar, finalizar y
  cancelar; los permisos de CONTABILIDAD y CONSULTA. Aparte: AGENTE sin
  botones de escritura (5 revisiones) y, con un edificio con unidades, la
  unidad pasa a disponible en la ficha sin recargar.
- Prueba al revés de la regla 7: si `useOpcionesPropiedad` ignora el estado,
  los dos formularios ofrecen las 11 propiedades y la revisión falla. La
  cotización de B sigue ofreciendo todas con y sin el cambio.

**Recorrido en producción (2026-11-03, A).** Douglas siguió la guía de
recorrido con la cuenta de administrador y un usuario de prueba por rol, y
reportó que todo salió como se esperaba:
- **Compras y construcción, solo lectura:** proveedores, contratos de compra,
  constructoras y el detalle del proyecto del hotel se revisaron sin crear ni
  cambiar nada, para no gastar las acciones que se muestran en vivo en la
  defensa (completar Las Lomas, iniciar la gasolinera, finalizar el hotel).
  Las escrituras de estas pantallas quedan cubiertas por la verificación local
  y las pruebas de API.
- **Permisos por rol:** los botones de escritura aparecen y desaparecen según
  el rol, como en §3.
- **Asistente público:** con el catálogo de propiedades indexado, respondió
  con citas (spec 020).
