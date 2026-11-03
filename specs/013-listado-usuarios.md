# 013 · Listado de usuarios para elegir el de un agente

| Campo | Valor |
|---|---|
| **Número** | 013 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce) |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `usuarios` |
| **Rama** | `feature/013-listado-usuarios` |
| **Pull request** | DouGMV/Proyecto-Inmobiliaria#59 (spec aprobada en #54, correcciones en #69) |

---

## 1. Problema

Para registrar un agente hay que elegir el usuario al que pertenece (spec 004,
regla 1). La pantalla "Nuevo agente" de la spec 012 no tiene de dónde sacar esa
lista: la API solo expone el usuario de la sesión (`/auth/yo/`).

La alternativa de crear los agentes desde el panel de Django no sirve, porque
el panel de `crm` es de solo lectura (spec 004, §2). Sin este listado, un
agente nuevo no se podría crear desde la aplicación.

## 2. Alcance

**Incluye:**
- `GET /api/v1/usuarios/`: lista paginada de usuarios activos, de solo lectura.
- Filtros por rol y búsqueda por nombre o correo.

**No incluye:**
- **Crear, editar o desactivar usuarios desde la API.** Se siguen gestionando
  en el panel de Django, como hasta ahora. Se agrega solo si una spec lo pide.
- **Filtrar "usuarios que todavía no son agentes".** `usuarios` no puede
  importar `crm` (`docs/arquitectura.md` §3). Si se elige un usuario que ya es
  agente, la API de agentes responde 409 `USUARIO_YA_ES_AGENTE` (spec 004).
- La pantalla "Nuevo agente": es de la spec 012 (rol B).

**La pantalla "Nuevo agente" debe pedir `?rol=AGENTE`** (observación de B en la
revisión). No es opcional: `crear_agente` rechaza a un usuario con otro rol
(`USUARIO_NO_ES_AGENTE`, spec 004, regla 1). Con el filtro, la pantalla solo
ofrece usuarios que la API puede aceptar.

## 3. Reglas

1. **Solo `ADMINISTRADOR` y `GERENTE`** ven el listado. Son los únicos que crean
   agentes (spec 004, regla 11). Los demás roles reciben 403, porque el
   listado tiene correos y nombres de todo el personal.
2. **Solo usuarios activos.** Un usuario desactivado no puede iniciar sesión, y
   no tiene sentido ofrecerlo para un perfil nuevo.
3. **Datos mínimos:** id, correo, nombre completo, rol y país. Nada de
   contraseña, teléfono, último acceso ni permisos.
4. **Filtros:**
   - `?rol=AGENTE` (nombre del rol);
   - `?buscar=` (nombre completo o correo, sin distinguir mayúsculas).
   - Orden por nombre completo, 25 por página.

## 4. Modelo de datos

Sin cambios.

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/api/v1/usuarios/?rol=&buscar=&page=` | `ADMINISTRADOR`, `GERENTE` |

**Respuesta:**

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "email": "agente1@demo.test",
      "nombre_completo": "Agente Demo Uno",
      "rol": "AGENTE",
      "pais": { "id": 1, "nombre": "Guatemala" }
    },
    {
      "id": 9,
      "email": "agente4@demo.test",
      "nombre_completo": "Agente Demo Cuatro",
      "rol": "AGENTE",
      "pais": null
    }
  ]
}
```

`pais` es `null` si el usuario no tiene país (observación de B). El campo
siempre viene en la respuesta: el tipo generado lo declara
`PaisResumen | null`, no opcional, y la pantalla debe tener en cuenta el `null`.

**Errores:** los comunes. 401 sin sesión, 403 con otro rol, y 400 `VALIDACION`
con un rol que no existe en `?rol=`.

## 6. Servicios y selectores

```python
# usuarios/selectors.py: listar_usuarios_activos() ya existe (spec 004);
# solo se ordena por nombre completo y se carga el país en la misma consulta.
def listar_usuarios_activos() -> QuerySet[Usuario]

# usuarios/filters.py (nuevo)
class UsuarioFilter(FilterSet): rol, buscar
```

La vista es una `ListAPIView` con `TieneRol` y `roles_por_metodo =
{"GET": [ADMINISTRADOR, GERENTE]}`. Como `GET` queda declarado, deja de estar
abierto a cualquier autenticado (spec 004, `TieneRol`). No hay servicios: no
escribe nada.

## 7. Auditoría

No aplica: es una lectura.

## 8. Criterios de aceptación

- [x] Un administrador y un gerente reciben la lista paginada
- [x] Agente, contabilidad y consulta reciben 403; sin sesión, 401
- [x] Un usuario desactivado no aparece
- [x] `?rol=AGENTE` trae solo agentes; `?buscar=` filtra por nombre o correo, sin
      distinguir mayúsculas
- [x] Un rol que no existe en `?rol=` responde 400 `VALIDACION` (agregado por B)
- [x] `pais` puede venir `null`, y el tipo generado lo refleja (agregado por B)
- [x] La respuesta no incluye contraseña, teléfono ni último acceso
- [x] El listado no hace una consulta por usuario (rol y país en la misma
      consulta)
- [x] `ruff`, `pytest`, `makemigrations --check` y el esquema OpenAPI pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| API | Matriz de permisos por rol, y 401 sin sesión |
| API | Filtro por rol, rol inexistente (400), búsqueda, orden, omite desactivados, campos de la respuesta, país nulo |
| API | Número de consultas constante con 1 y con 5 usuarios |

## 10. Decisiones y alternativas descartadas

- **Endpoint y no panel de Django** (decidido por A): el panel de `crm` es de
  solo lectura, y "Nuevo agente" es parte del flujo que se demuestra.
- **Solo lectura.** Crear usuarios desde la API exigiría reglas de contraseña,
  roles y auditoría que nadie pidió; el panel de Django ya lo hace.
- **Restringido a administración y gerencia**, y no abierto a todos los
  autenticados: el listado expone datos personales del personal.
- **Sin el filtro "sin perfil de agente"**, para no romper la regla de
  dependencias. La pantalla debe usar `?rol=AGENTE` (§2). Si aun así se elige
  a alguien que ya es agente, la API de agentes lo rechaza con un mensaje
  claro (`USUARIO_YA_ES_AGENTE`).

## 11. Trabajo con agentes de IA

**Sesión 2026-10-31 (Claude Code, rol A).** Lo pidió el rol B para la pantalla
"Nuevo agente" de la spec 012. El agente comparó las dos opciones que planteó B
(endpoint o panel de Django), encontró que el panel de `crm` es de solo
lectura y propuso el endpoint. A lo eligió.

**Plan de implementación:** un solo incremento, con el filtro, el
serializador, la vista y la ruta, más sus pruebas.

**Revisión de B en #54 (aprobada en una ronda).** Tres observaciones,
aplicadas al implementar:
- la pantalla debe filtrar por `?rol=AGENTE`, por `USUARIO_NO_ES_AGENTE`;
- `pais` puede venir `null`;
- faltaba el criterio del rol inexistente.

**Sesión 2026-10-31, implementación (Claude Code, rol A).**
- **`listar_usuarios_activos`:** ahora carga rol y país en la misma consulta y
  ordena por nombre, con el id como desempate para que la paginación sea
  estable. Lo usa también la API de agentes de `crm`, para validar el id
  recibido; sus pruebas siguen pasando.
- **`?rol=` es un `ChoiceFilter`**, no un texto libre: un rol mal escrito
  (`AGENT`) responde 400 en vez de una lista vacía que parecería correcta.
- **13 pruebas nuevas**, una o más por criterio. La suite completa da 519.
- Se regeneraron los tipos del frontend (`UsuarioListado`), para que B haga
  la pantalla sobre ellos.
