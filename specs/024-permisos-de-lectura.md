# 024 · Permisos de lectura de compras, construcción y agentes

| Campo | Valor |
|---|---|
| **Número** | 024 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-11-03 |
| **Apps afectadas** | `usuarios` (`TieneRol`), `compras`, `construccion`, `crm` y `frontend/` (`menu.ts`) |
| **Rama** | `feature/024-permisos-de-lectura` |
| **Pull request** | Enlace, una vez abierto |

---

## 1. Problema

Las specs 006 y 017 dejaron compras y construcción abiertas a la lectura de
todos los roles. Así un agente comercial ve cuánto pagó la agencia por cada
propiedad, con sus gastos e impuestos, y puede calcular el margen mientras
negocia con un cliente. También ve el presupuesto y los pagos de cada obra,
aunque los reportes con esos mismos datos (R13 y R15) ya estaban cerrados para
él. La pantalla contradecía al reporte.

Además, la lista de agentes (spec 004) mostraba a cada agente el porcentaje de
comisión y el teléfono de sus compañeros, un dato que no necesita para vender.

## 2. Alcance

**Incluye:**
- Leer proveedores, contratos de compra, constructoras, proyectos y pagos a
  constructoras: solo `ADMINISTRADOR`, `GERENTE` y `CONTABILIDAD`.
- Un `AGENTE` ve en `/agentes/` solo su propio perfil.
- El menú, las rutas y el tablero de Inicio siguen esas mismas reglas.
- `TieneRol` trata `HEAD` como `GET`: una vista que restringe la lectura no
  queda abierta por el otro método de lectura.

**No incluye:**
- Los datos personales de los clientes para `CONSULTA` ni la descarga de
  documentos oficiales: se dejan como están hasta que el equipo lo decida.
- Cambios en quién escribe: siguen las reglas de las specs 004, 006 y 017.

## 3. Reglas de negocio

1. **Compras y construcción se leen solo en administración, gerencia y
   contabilidad.** `AGENTE` y `CONSULTA` reciben 403 en la lista y el detalle
   de proveedores, contratos de compra, constructoras, proyectos y pagos. Es
   la misma regla que ya tenían R13 y R15 (spec 021).
2. **Un agente solo ve su propio perfil de agente.** En `/agentes/` y
   `/agentes/{id}/`, un `AGENTE` encuentra solo el suyo; el de otro responde
   404, como un cliente fuera de su cartera (spec 004, regla 14). Los demás
   roles siguen viendo a todos.
3. **El menú no muestra lo que el rol no puede leer.** Compras y Construcción
   desaparecen para `AGENTE` y `CONSULTA`, y Agentes para `AGENTE`. Ocultar no
   es seguridad: la API responde 403 o 404 de todos modos.
4. **`HEAD` sigue a `GET`.** Si una vista declara roles para `GET`, `HEAD`
   usa los mismos.

Reemplaza la parte de lectura de la regla 10 de la spec 006, de la regla 24
de la spec 017 y de la regla 13 de la spec 004 en lo que toca a agentes.

## 4. Modelo de datos

Sin cambios.

## 5. API

| Endpoint | Antes | Ahora |
|---|---|---|
| `GET /proveedores/`, `/proveedores/{id}/` | Todos | `ADMINISTRADOR`, `GERENTE`, `CONTABILIDAD` |
| `GET /contratos-compra/`, `/contratos-compra/{id}/` | Todos | Ídem |
| `GET /constructoras/`, `/constructoras/{id}/` | Todos | Ídem |
| `GET /proyectos-construccion/`, `/{id}/`, `/{id}/pagos/` | Todos | Ídem |
| `GET /pagos-constructora/` | Todos | Ídem |
| `GET /agentes/`, `/agentes/{id}/` | Todos ven a todos | `AGENTE` ve solo el suyo |

Sin códigos de error nuevos: 403 `PERMISO_DENEGADO` y 404 como hasta ahora.

## 6. Servicios y selectores

- `usuarios/permissions.py`: `TieneRol` usa los roles de `GET` para `HEAD`.
- `compras/views.py` y `construccion/views.py`: una lista `LEEN` declarada como
  `"GET"` en `roles_por_metodo` de cada vista de lectura.
- `crm/selectors.py`: `listar_agentes_visibles(usuario=...)`, que aplica la
  regla 2 sobre `listar_agentes`. Las vistas de agentes la usan;
  `listar_agentes` sigue igual para los campos que eligen un agente.
- `frontend/src/menu.ts`: `LEEN_COMPRAS`, `LEEN_CONSTRUCCION` y
  `VEN_AGENTES` en las entradas del menú. El tablero de Inicio toma los roles
  del menú, así que se ajusta solo.

## 7. Auditoría

No aplica: no hay escrituras nuevas.

## 8. Criterios de aceptación

- [x] `AGENTE` y `CONSULTA` reciben 403 en la lista y el detalle de compras y
      construcción; `CONTABILIDAD` sigue leyendo
- [x] Un `AGENTE` ve solo su perfil en `/agentes/`, y el de otro responde 404
- [x] `HEAD` sobre una vista con `GET` restringido responde 403 al rol excluido
- [x] El menú y el tablero de Inicio no muestran Compras ni Construcción a
      `AGENTE` ni a `CONSULTA`, ni Agentes a `AGENTE`
- [x] `pytest`, `ruff`, `npm run lint`, `npm run typecheck` y `npm run build`
      pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| API | Por rol, 200 o 403 en cada lista y detalle de compras y construcción |
| API | `/agentes/` como `AGENTE` devuelve solo su perfil; el detalle de otro, 404 |
| Permiso | `HEAD` usa los roles de `GET` |
| Estático | `typecheck` con el menú nuevo |

## 10. Decisiones y alternativas descartadas

- **Cerrar la lectura y no esconder campos.** Ocultar solo los montos al agente
  dejaría proveedores y obras visibles sin que los use para vender, y
  obligaría a dos serializadores por recurso.
- **El perfil propio del agente y no un 403 en `/agentes/`.** Algunas
  pantallas y reportes leen el agente del usuario; con su propio perfil siguen
  funcionando.
- **Datos de clientes para `CONSULTA` y documentos oficiales, fuera.** Son
  decisiones de negocio que el equipo no ha tomado.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-03 (Claude Code, rol A).** Douglas pidió revisar lo que ve
cada rol porque sentía que había accesos de más. El agente comparó, vista por
vista, `roles_por_metodo` y los selectores contra el menú, y presentó seis
hallazgos. Douglas eligió aplicar los de compras, construcción y agentes, y
dejar para el equipo los datos de clientes y los documentos oficiales. Al
revisar `TieneRol` apareció que `HEAD` no seguía a `GET`, y se corrigió en el
mismo cambio.
