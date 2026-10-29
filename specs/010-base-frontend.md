# 010 · Base del frontend: rutas, sesión, menú por rol y componentes genéricos

| Campo | Valor |
|---|---|
| **Número** | 010 |
| **Estado** | Implementada, en revisión |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce) |
| **Fecha** | 2026-10-29 |
| **Apps afectadas** | `frontend/` (ninguna app del backend) |
| **Rama** | `feature/010-base-frontend` |
| **Pull request** | — (spec aprobada en DouGMV/Proyecto-Inmobiliaria#41) |
| **Issue** | #15 |

---

## 1. Problema

Hoy el frontend es una sola página que muestra el estado de la API (spec 002,
§6). Para que cada integrante haga las pantallas de su bloque el fin de semana
(plan de una semana, `docs/roadmap.md`), falta lo que todas comparten:

- iniciar sesión;
- navegar entre pantallas con un menú que dependa del rol;
- listar datos paginados;
- llenar un formulario que muestre los errores de la API.

Si cada quien lo resuelve por su cuenta, salen cuatro maneras distintas de
hacer lo mismo y nadie puede explicar las demás en la defensa.

## 2. Alcance

**Incluye:**
- Rutas con React Router y protección por rol (`RutaProtegida`).
- Inicio y cierre de sesión con JWT, con renovación automática del token.
- Menú que se arma según el rol.
- Componentes genéricos que el plan pide reutilizar en todas las entidades:
  - `TablaDatos`, paginada contra el servidor;
  - `FormularioDatos`, con validación y errores de la API por campo.
- Utilidades comunes: `formatearMoneda`, `formatearFecha` y el mensaje de error
  de la API.
- Una **pantalla de ejemplo** que los demás copian: lista de propiedades con
  filtros y formulario para crear una.
- La regla de reescritura de Vercel para que recargar una ruta no dé 404
  (spec 002, §6.1).

**No incluye:**
- Recuperación de contraseña: el backend no tiene ese endpoint.
- Ficha de propiedad, mapa y gráficas: están en "solo si sobra tiempo" del
  plan.
- El resto de las pantallas del catálogo (sábado, rol A) y las de los demás
  bloques: cada rol hace las suyas sobre esta base.
- Pruebas automáticas del frontend: no hay ejecutor de pruebas instalado
  (§10).

## 3. Reglas

1. **Toda ruta, salvo `/login`, exige sesión.** Sin sesión, se redirige a
   `/login` y, después de entrar, se vuelve a la ruta pedida.
2. **Una ruta puede limitarse a ciertos roles.** Con sesión pero sin el rol, se
   muestra "No tiene permiso para ver esta página", sin redirigir.
3. **El menú solo muestra lo que el rol puede abrir.** El backend igual valida
   todo con `TieneRol`: el frontend nunca es la frontera de seguridad
   (`docs/frontend.md` §5).
4. **Tokens** (`docs/frontend.md` §5):
   - el de acceso se guarda **en memoria**;
   - el de refresco, en `localStorage`.
   Al recargar la página, si hay un token de refresco se pide uno de acceso
   nuevo y luego `/auth/yo/`; si falla, se borra todo y se va a `/login`.
5. **Renovación automática.** Si la API responde 401 con sesión iniciada, se
   renueva el token de acceso **una sola vez** y se repite la petición. Si
   varias peticiones reciben 401 a la vez, comparten la misma renovación. Si
   la renovación falla, se cierra la sesión. Un 401 de `/auth/login/` o de
   `/auth/refresh/` **nunca** dispara la renovación: así no hay un ciclo.
6. **Cerrar sesión** borra los dos tokens y la caché de TanStack Query, para que
   el siguiente usuario no vea datos del anterior.
7. **Toda lista se pagina en el servidor** (`?page=`, 25 por página, como la
   API). Los filtros viajan como parámetros de la URL de la API, nunca se
   filtra en el navegador.
8. **Errores de la API.**
   - Se muestra el `mensaje` del formato uniforme (spec 001).
   - En un formulario, cada error de `detalles` aparece junto a su campo.
   - Un error sin campo (409, 403, 500) se muestra arriba del formulario.
9. **Todo monto se muestra con su moneda**, con `formatearMoneda(monto,
   codigoMoneda)` sobre `Intl.NumberFormat`. Las fechas se muestran como
   `dd/mm/aaaa`.
10. **Sin `fetch` ni `axios` en los componentes.** Cada dominio tiene sus hooks
    en `api/<dominio>/consultas.ts` y `mutaciones.ts` (`docs/frontend.md` §3).

*Agregadas en la revisión de B (#41)*, para que las pantallas de los demás
bloques no los resuelvan cada una a mano:

11. **Relaciones con muchas opciones.** Un campo de tipo relación en
    `FormularioDatos` busca en la API con `?buscar=` mientras se escribe y
    muestra las primeras coincidencias. Sirve para clientes, propiedades y
    unidades, que pueden ser cientos. Para listas cortas (monedas, tipos),
    un selector normal.
12. **Campos condicionales y dependientes.**
    - Un campo puede declarar `visibleSi`: por ejemplo, razón social y NIT
      solo si el cliente es una empresa, o las cuotas solo si el contrato es
      financiado. Un campo oculto no se envía.
    - Un campo puede depender del valor de otro: las ciudades se buscan dentro
      del país elegido, y al cambiar el país se vacía la ciudad.
13. **Acciones por fila.** `TablaDatos` acepta una columna de acciones, cada una
    con su mutación: aprobar, pagar, rescindir… Las que no se pueden deshacer
    piden confirmación antes de llamar a la API.
14. **Tablas sin paginar.** `TablaDatos` también acepta una lista ya cargada,
    como las cuotas que vienen dentro del detalle de un contrato.

## 4. Modelo de datos

Sin cambios en el backend. Los tipos de las respuestas salen de
`npm run gen:api`.

## 5. Pantallas y rutas

| Ruta | Pantalla | Roles |
|---|---|---|
| `/login` | Inicio de sesión | Sin sesión |
| `/` | Inicio: usuario, rol y estado de la API (la página actual pasa aquí) | Todos |
| `/catalogo/propiedades` | **Ejemplo de lista:** `TablaDatos` con filtros por tipo, estado y búsqueda, y la acción por fila "Cambiar estado" (regla 13) | Todos; la acción, `ADMINISTRADOR` y `GERENTE` |
| `/catalogo/propiedades/nueva` | **Ejemplo de formulario:** `FormularioDatos` para crear una propiedad. El país y la ciudad muestran las reglas 11 y 12: la ciudad se busca dentro del país elegido | `ADMINISTRADOR`, `GERENTE` |

Endpoints que usa, todos existentes:
- `POST /auth/login/`
- `POST /auth/refresh/`
- `GET /auth/yo/`
- `GET /health/`
- `GET` y `POST /propiedades/`
- `POST /propiedades/{id}/cambiar-estado/`
- `GET /tipos-propiedad/`, `/paises/`, `/ciudades/` y `/monedas/`

**Único cambio en el backend:** `GET /ciudades/` acepta `?buscar=` (nombre),
para que la ciudad se pueda buscar como relación (regla 11). Es un filtro de
`core/filters.py`, del área de A.

## 6. Componentes y módulos

```
src/
├── App.tsx                        # rutas
├── menu.ts                        # [{ ruta, etiqueta, roles }]: una sola lista, y los roles
├── sesion/
│   ├── tokens.ts                  # acceso en memoria, refresco en localStorage
│   ├── useSesion.ts               # el contexto y su hook (único estado global)
│   └── ProveedorSesion.tsx        # recupera la sesión al cargar; abrir y cerrar sesión
├── api/
│   ├── cliente.ts                 # + interceptores: Authorization y renovación (regla 5)
│   ├── errores.ts                 # lee el formato uniforme de error (regla 8)
│   ├── paginacion.ts              # tamaño de página y total de páginas
│   ├── core/                      # useEstadoServicio, usePaises, useMonedas, useBuscarCiudades
│   ├── usuarios/                  # useUsuarioActual, useIniciarSesion
│   └── catalogo/                  # usePropiedades, useTiposPropiedad, useCrearPropiedad…
├── componentes/
│   ├── ui/                        # shadcn/ui, sin Radix
│   └── comunes/
│       ├── RutaProtegida.tsx      # reglas 1 y 2
│       ├── TablaDatos.tsx         # reglas 7, 13 y 14
│       ├── FormularioDatos.tsx    # reglas 8, 11 y 12
│       ├── CampoRelacion.tsx      # búsqueda mientras se escribe (regla 11)
│       └── Dialogo.tsx            # ventana modal con el <dialog> nativo
├── hooks/useRetraso.ts            # espera a que se deje de escribir
├── layouts/                       # LayoutAuth y LayoutPrincipal (menú por rol)
├── lib/                           # formato.ts (moneda y fecha) y utils.ts (cn)
└── paginas/
    ├── auth/Login.tsx
    ├── inicio/Inicio.tsx
    ├── errores/NoEncontrada.tsx
    └── catalogo/ListaPropiedades.tsx, NuevaPropiedad.tsx, DialogoCambiarEstado.tsx
```

**Cómo se agrega una pantalla nueva** (lo que copian los demás):
1. Agregar los hooks en `api/<dominio>/`.
2. Crear la página con `TablaDatos` o `FormularioDatos`.
3. Agregar una línea a la lista de rutas y una a `menu.ts` con sus roles.

**Dependencias nuevas**, todas ya listadas en `docs/frontend.md` §1:
- `react-router`
- `@tanstack/react-table`
- `react-hook-form`, `zod` y `@hookform/resolvers`
- Tailwind CSS (`tailwindcss` y `@tailwindcss/vite`)
- Los componentes de shadcn/ui que se usen: botón, campo, etiqueta, tabla,
  tarjeta y selector. Se copian al proyecto, con sus utilidades `clsx` y
  `tailwind-merge`.

Cada una se justifica en el pull request, como pide `CLAUDE.md` §11.

## 7. Auditoría

No aplica: el frontend no escribe en la bitácora. El inicio de sesión ya queda
registrado por el backend (`INICIAR_SESION` y `LOGIN_FALLIDO`, spec 001), y
crear una propiedad lo registra el servicio del catálogo (spec 003).

## 8. Criterios de aceptación

- [x] Sin sesión, cualquier ruta lleva a `/login`; después de entrar, vuelve a
      la ruta pedida
- [x] Credenciales incorrectas muestran el mensaje de la API, sin recargar
- [x] Al recargar la página con sesión, se sigue dentro sin volver a escribir
      la contraseña
- [x] Con el token de acceso vencido, la siguiente petición lo renueva sola y
      funciona
- [x] Cerrar sesión vuelve a `/login`; con el botón Atrás no se ven datos
- [x] Un usuario `CONSULTA` no ve "Nueva propiedad" en el menú, y al abrir la
      ruta a mano ve el aviso de permiso
- [x] La lista de propiedades pagina contra la API (25 por página) y sus
      filtros cambian la consulta, no filtran en el navegador
- [x] Los precios se ven con su moneda y las fechas como `dd/mm/aaaa`
- [x] Crear una propiedad con un precio de 0 muestra el error junto al campo;
      una válida aparece en la lista con su código `PROP-NNNNN`
- [x] La ciudad se busca al escribir y solo ofrece ciudades del país elegido;
      al cambiar el país, se vacía (reglas 11 y 12)
- [x] "Cambiar estado" pide confirmación y la lista se actualiza sin recargar
      (regla 13); un usuario `CONSULTA` no ve la acción
- [ ] En Vercel, recargar `/catalogo/propiedades` no da 404
- [x] `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Manual, local | Cada criterio de §8 contra el backend local con `seed_demo` |
| Manual, producción | Login, lista y recarga de una ruta en Vercel contra Render |
| Estático | `typecheck` con los tipos generados: si la API cambia un campo, el frontend deja de compilar |

## 10. Decisiones y alternativas descartadas

- **Refresco en `localStorage` y acceso en memoria**, como ya dice
  `docs/frontend.md` §5.
  - Una cookie `HttpOnly` protegería mejor el token de refresco contra XSS,
    pero exige cambiar el backend (SimpleJWT no la usa por defecto) y
    configurar CSRF.
  - Se acepta el riesgo para un proyecto académico y se mitiga con un token de
    acceso corto (30 minutos) y sin `dangerouslySetInnerHTML`.
- **Una sola renovación compartida.** Si cada petición con 401 renovara por su
  cuenta, una pantalla con cuatro consultas haría cuatro renovaciones a la vez.
- **Contexto de React para la sesión, sin Redux ni Zustand.** Es el único
  estado global (`docs/frontend.md` §3); lo demás lo guarda TanStack Query.
- **Formulario genérico por campos declarados**, en lugar de un formulario a
  mano por entidad. El plan de una semana pide reutilizarlo en las 17
  entidades. Cada pantalla declara sus campos y su esquema Zod, y el
  componente se encarga de mostrarlos, validar y poner los errores de la API.
- **Sin pruebas automáticas del frontend en esta spec.** Agregar Vitest y
  Testing Library es otra dependencia y otra configuración; con siete días, el
  tiempo va a las pantallas. La red de seguridad es el `typecheck` con los
  tipos generados y la verificación manual de §8. Se agregan si sobra tiempo.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-29 (Claude Code, rol A).** El agente redactó el borrador a
partir de:
- `docs/frontend.md`;
- la issue #15;
- el código actual del frontend (spec 002, §6);
- `/auth/yo/` y la configuración de SimpleJWT del backend.

**Plan de implementación:**
1. Dependencias, Tailwind y los componentes de shadcn/ui; rutas,
   `LayoutAuth` y `LayoutPrincipal`; la regla de reescritura de Vercel.
2. Sesión: tokens, interceptores, `ContextoSesion`, `Login` y `RutaProtegida`;
   menú por rol.
3. `TablaDatos`, `formatearMoneda` y la lista de propiedades.
4. `FormularioDatos`, errores por campo y la creación de propiedades; cierre
   con los criterios de §8.

**Revisión de B en #41 (aprobada en una ronda).** Marco aprobó y pidió que la
implementación cubriera:
- relaciones con búsqueda;
- campos condicionales y dependientes;
- acciones por fila;
- tablas sin paginar;
- que el login y la renovación no disparen la renovación.

Se agregaron como reglas 11 a 14 y en la regla 5. La regla 14 se comprueba con
la primera pantalla que la use: el detalle del contrato de la spec 007.

También señaló que el límite de intentos de login, de 10 por minuto por IP,
bloquearía a los evaluadores que entran desde la misma red. Se corrigió aparte,
en DouGMV/Proyecto-Inmobiliaria#45.

**Sesión 2026-10-29, implementación (Claude Code, rol A).** Los criterios de §8
se comprobaron en el navegador contra el backend local, con un gerente y un
usuario de consulta de prueba. Falta uno: la recarga en Vercel, que se comprueba
en la vista previa del PR. Lo que se decidió o se descubrió al implementar:

- **React Router 7 y TanStack Table 8**, no sus versiones 8 y 9. Las nuevas
  cambiaron la API; las anteriores son las de la documentación y los ejemplos
  que el equipo va a encontrar. Todas las dependencias se fijan con `==`,
  publicadas hace dos semanas o más, y `npm audit` no encuentra
  vulnerabilidades.
- **Los componentes de shadcn/ui se copiaron sin Radix**: el selector y la
  ventana modal usan los del navegador (`<select>` y `<dialog>`), que ya son
  accesibles.
- **Renovación:** la sesión solo se cierra si la API rechaza el token de
  refresco (401). Si falla la red, por ejemplo mientras Render despierta, se
  ofrece reintentar en vez de sacar al usuario.
- **El formulario valida solo el formato en el navegador.** Las reglas de
  negocio (precio mayor que cero) las valida la API, y su error aparece junto
  al campo (regla 8). Se comprobó con un precio de 0.
- **Error encontrado y corregido en la prueba:** el campo de relación borraba
  lo que se escribía después de elegir una opción. Un efecto vaciaba el texto
  cada vez que el valor quedaba vacío, y escribir lo vaciaba. Ahora el campo se
  vuelve a crear (con otra `key`) solo cuando cambia el campo del que depende.
- **El código de las tablas y la lectura de valores del formulario**
  (`useReactTable` y `watch`) lleva un aviso de oxlint para el React Compiler.
  Se desactiva con un comentario que explica por qué: el proyecto no lo usa.
- **El tipo de error de la API se escribe a mano** (`api/errores.ts`), porque
  el esquema OpenAPI no documenta el formato del manejador global. Es la única
  excepción a la regla de tipos generados.
- `api/paginacion.ts` no define un tipo genérico de respuesta paginada: cada
  una se toma del esquema (`PaginatedPropiedadList`…).
- **La compilación avisa que el paquete pasa de 500 kB.** No bloquea; dividirlo
  por rutas queda para cuando haya más pantallas.
