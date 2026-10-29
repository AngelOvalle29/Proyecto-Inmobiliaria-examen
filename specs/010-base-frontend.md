# 010 · Base del frontend: rutas, sesión, menú por rol y componentes genéricos

| Campo | Valor |
|---|---|
| **Número** | 010 |
| **Estado** | En revisión |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-29 |
| **Apps afectadas** | `frontend/` (ninguna app del backend) |
| **Rama** | `feature/010-base-frontend` |
| **Pull request** | — |
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
   la renovación falla, se cierra la sesión.
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

## 4. Modelo de datos

Sin cambios en el backend. Los tipos de las respuestas salen de
`npm run gen:api`.

## 5. Pantallas y rutas

| Ruta | Pantalla | Roles |
|---|---|---|
| `/login` | Inicio de sesión | Sin sesión |
| `/` | Inicio: usuario, rol y estado de la API (la página actual pasa aquí) | Todos |
| `/catalogo/propiedades` | **Ejemplo de lista:** `TablaDatos` con filtros por tipo, estado y búsqueda | Todos |
| `/catalogo/propiedades/nueva` | **Ejemplo de formulario:** `FormularioDatos` para crear una propiedad | `ADMINISTRADOR`, `GERENTE` |

Endpoints que usa, todos existentes:
- `POST /auth/login/`
- `POST /auth/refresh/`
- `GET /auth/yo/`
- `GET /health/`
- `GET` y `POST /propiedades/`
- `GET /tipos-propiedad/`, `/ciudades/` y `/monedas/`

## 6. Componentes y módulos

```
src/
├── App.tsx                        # rutas
├── sesion/
│   ├── ContextoSesion.tsx         # usuario actual, iniciar y cerrar sesión (único estado global)
│   └── tokens.ts                  # acceso en memoria, refresco en localStorage
├── api/
│   ├── cliente.ts                 # + interceptores: Authorization y renovación (regla 5)
│   ├── errores.ts                 # lee el formato uniforme de error (regla 8)
│   ├── paginacion.ts              # tipo de la respuesta paginada de DRF
│   ├── usuarios/                  # useIniciarSesion, useUsuarioActual
│   └── catalogo/                  # usePropiedades, useCrearPropiedad, useTiposPropiedad…
├── componentes/comunes/
│   ├── RutaProtegida.tsx          # reglas 1 y 2
│   ├── TablaDatos.tsx             # columnas + página + total; usa TanStack Table
│   └── FormularioDatos.tsx        # campos declarados + esquema Zod + mutación
├── layouts/
│   ├── LayoutAuth.tsx
│   └── LayoutPrincipal.tsx        # menú por rol (regla 3) y cerrar sesión
├── menu.ts                        # [{ ruta, etiqueta, roles }]: una sola lista
├── lib/formato.ts                 # formatearMoneda, formatearFecha
└── paginas/
    ├── auth/Login.tsx
    ├── inicio/Inicio.tsx
    └── catalogo/ListaPropiedades.tsx, NuevaPropiedad.tsx
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

- [ ] Sin sesión, cualquier ruta lleva a `/login`; después de entrar, vuelve a
      la ruta pedida
- [ ] Credenciales incorrectas muestran el mensaje de la API, sin recargar
- [ ] Al recargar la página con sesión, se sigue dentro sin volver a escribir
      la contraseña
- [ ] Con el token de acceso vencido, la siguiente petición lo renueva sola y
      funciona
- [ ] Cerrar sesión vuelve a `/login`; con el botón Atrás no se ven datos
- [ ] Un usuario `CONSULTA` no ve "Nueva propiedad" en el menú, y al abrir la
      ruta a mano ve el aviso de permiso
- [ ] La lista de propiedades pagina contra la API (25 por página) y sus
      filtros cambian la consulta, no filtran en el navegador
- [ ] Los precios se ven con su moneda y las fechas como `dd/mm/aaaa`
- [ ] Crear una propiedad con un precio de 0 muestra el error junto al campo;
      una válida aparece en la lista con su código `PROP-NNNNN`
- [ ] En Vercel, recargar `/catalogo/propiedades` no da 404
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan

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
