# 006 · Compras y construcción: proveedores y constructoras

| Campo | Valor |
|---|---|
| **Número** | 006 |
| **Estado** | En revisión |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `compras` (incluido `cargar_demo_compras`), `construccion` (incluido `cargar_demo_construccion`) |
| **Rama** | `feature/006-proveedores-constructoras` |
| **Pull request** | — |

---

## 1. Problema

La agencia compra propiedades a terceros (particulares, inmobiliarias, bancos,
el gobierno) y contrata constructoras para levantar o remodelar. Hoy no tiene
dónde registrar a esos proveedores ni a las constructoras, así que no puede
firmar contratos de compra ni abrir proyectos de construcción, porque los dos
apuntan a ellos.

Esta spec crea `Proveedor` y `Constructora`, que **no dependen del catálogo de
propiedades**, para que el rol C avance mientras `Propiedad` (spec 003) llega a
`develop`. Son 2 de las 17 entidades con CRUD del plan de una semana
(`docs/roadmap.md`).

## 2. Alcance

**Incluye:**
- Modelos `compras.Proveedor` y `construccion.Constructora`, con borrado lógico
  y campos de rastro
- API de lectura y escritura de los dos, con filtros y búsqueda
- Auditoría de toda escritura
- Comandos `cargar_demo_compras` y `cargar_demo_construccion` con datos ficticios

**No incluye:**
- `ContratoCompra`, `ProyectoConstruccion` y `PagoConstructora`: necesitan
  `Propiedad`. Van en la spec 007 del rol C.
- Reglas de desactivación con contratos o proyectos abiertos: se agregan en la
  spec 007, cuando esas entidades existan (§10).
- Reactivar un registro desactivado vía API: se hace desde el panel, como en la
  spec 004.
- Llamar a los comandos de demo desde `seed_demo`: lo ajusta A en `core`, como
  en la spec 004.
- Pantallas: van sobre la base del frontend, con la lista y el formulario
  genéricos.

## 3. Reglas de negocio

**Proveedores**

1. Un proveedor tiene un tipo: `PROPIETARIO_PARTICULAR`, `INMOBILIARIA`,
   `BANCO`, `GOBIERNO` u `OTRO`.
2. El NIT es obligatorio para todos los tipos **excepto**
   `PROPIETARIO_PARTICULAR`, para quien es opcional. *Decisión a validar en la
   revisión* (§10).
3. No puede haber dos proveedores con el mismo NIT en el mismo país, aunque uno
   esté desactivado. El NIT se guarda normalizado, igual que en la spec 004:
   sin espacios ni guiones y en mayúsculas.

**Constructoras**

4. El NIT de una constructora es obligatorio: siempre es una empresa.
5. No puede haber dos constructoras con el mismo NIT en el mismo país, aunque
   una esté desactivada. Mismo criterio de normalización que la regla 3.
6. La calificación va de 1 a 5 y es **opcional**: una constructora recién
   registrada todavía no tiene trabajos que calificar.

**Comunes**

7. El país es obligatorio. La ciudad, cuando el modelo la tiene, es opcional,
   pero si se indica debe pertenecer al país (mismo criterio que la regla 9 de
   la spec 004).
8. El código lo genera el sistema y no cambia: `PRV-0001` para proveedores y
   `CST-0001` para constructoras.
9. No se borra nada físicamente: eliminar marca `activo` en falso.
10. Escriben `ADMINISTRADOR` y `GERENTE`. Leen todos los roles autenticados.

## 4. Modelo de datos

```
compras      → core, usuarios, auditoria
construccion → core, usuarios, auditoria
```

Las dos apps no dependen entre sí ni de `catalogo`.

### `compras.Proveedor` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`PRV-0001`). Nulo solo durante la creación |
| `tipo` | CharField, enum `TipoProveedor` | Regla 1 |
| `nombre` | CharField(200) | Nombre de la persona o razón social |
| `nit` | CharField(30) | Normalizado. Vacío solo si es `PROPIETARIO_PARTICULAR` |
| `email` | EmailField | Opcional |
| `telefono` | CharField(30) | Opcional |
| `pais` | FK `core.Pais` | Obligatorio, `PROTECT` |
| `ciudad` | FK `core.Ciudad` | Opcional, `PROTECT` |
| `direccion` | CharField(255) | Opcional |

### `construccion.Constructora` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`CST-0001`). Nulo solo durante la creación |
| `nombre` | CharField(200) | Razón social |
| `nit` | CharField(30) | Obligatorio, normalizado |
| `contacto` | CharField(150) | Nombre de la persona de contacto. Opcional |
| `email` | EmailField | Opcional |
| `telefono` | CharField(30) | Opcional |
| `pais` | FK `core.Pais` | Obligatorio, `PROTECT` |
| `calificacion` | PositiveSmallIntegerField | Opcional (nulo), entre 1 y 5 |

`activo` viene de `ModeloBase`; no se repite como campo propio (mismo criterio
que la spec 004). Los textos opcionales usan cadena vacía, no nulo.

**Constraints en la base de datos:**
- `Proveedor`: `CheckConstraint` — el NIT no está vacío salvo que el tipo sea
  `PROPIETARIO_PARTICULAR` (regla 2).
- `Proveedor`: `UniqueConstraint` sobre (`pais`, `nit`) con condición
  `nit <> ''` (regla 3). La condición permite varios particulares sin NIT.
- `Constructora`: `CheckConstraint` — NIT no vacío (regla 4).
- `Constructora`: `UniqueConstraint` sobre (`pais`, `nit`) (regla 5).
- `Constructora`: `CheckConstraint` — `calificacion` nula o entre 1 y 5 (regla 6).

La regla 7 (ciudad del país) se valida en el servicio, porque compara con otra
tabla.

**Índices:** `codigo` (único), `pais`, `ciudad`, `tipo`
(`docs/modelo-datos.md` §11).

**Códigos (regla 8):** mismo patrón que la spec 004. El servicio inserta con
`codigo` nulo y, en la misma transacción, asigna `PRV-{id:04d}` o
`CST-{id:04d}`. El `id` lo da PostgreSQL, así que no hay dos códigos iguales
aunque dos usuarios creen registros al mismo tiempo.

## 5. API

Configuración común de la spec 001. Permisos con `TieneRol` de la spec 004
(cerrado por defecto para escrituras).

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/api/v1/proveedores/` · `/{id}/` | Autenticado |
| POST · PATCH · DELETE | `/api/v1/proveedores/` · `/{id}/` | `ADMINISTRADOR`, `GERENTE` |
| GET | `/api/v1/constructoras/` · `/{id}/` | Autenticado |
| POST · PATCH · DELETE | `/api/v1/constructoras/` · `/{id}/` | `ADMINISTRADOR`, `GERENTE` |

`DELETE` desactiva (regla 9) y responde 204.

**Filtros**, en `filters.py` de cada app:
- `/proveedores/`: `?tipo=`, `?pais=`, `?ciudad=`, `?buscar=` (código, nombre o NIT)
- `/constructoras/`: `?pais=`, `?calificacion_min=`, `?buscar=` (código, nombre o NIT)

**Ejemplo de petición** (`POST /api/v1/proveedores/`):

```json
{
  "tipo": "BANCO",
  "nombre": "Banco Demo de Occidente",
  "nit": "1234567-8",
  "email": "adjudicados@bancodemo.test",
  "pais": 1,
  "ciudad": 2
}
```

**Ejemplo de respuesta 201:**

```json
{
  "id": 1,
  "codigo": "PRV-0001",
  "tipo": "BANCO",
  "nombre": "Banco Demo de Occidente",
  "nit": "12345678",
  "email": "adjudicados@bancodemo.test",
  "telefono": "",
  "pais": { "id": 1, "nombre": "Guatemala" },
  "ciudad": { "id": 2, "nombre": "Quetzaltenango" },
  "direccion": "",
  "activo": true
}
```

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `PROVEEDOR_DUPLICADO` | Ya existe un proveedor con ese NIT en ese país (regla 3) | 409 |
| `CONSTRUCTORA_DUPLICADA` | Ya existe una constructora con ese NIT en ese país (regla 5) | 409 |
| `CIUDAD_FUERA_DEL_PAIS` | La ciudad no pertenece al país (regla 7) | 400 |

Para la regla 7 se reutiliza el código que haya definido la spec 004, si ya
existe, en lugar de crear uno nuevo.

## 6. Servicios y selectores

```python
# compras/services.py  (transaction.atomic y registrar_auditoria)
def crear_proveedor(*, datos: dict, autor: Usuario, ip: str | None) -> Proveedor
def actualizar_proveedor(*, proveedor: Proveedor, datos: dict, autor: Usuario, ip: str | None) -> Proveedor
def desactivar_proveedor(*, proveedor: Proveedor, autor: Usuario, ip: str | None) -> None

# compras/selectors.py
def listar_proveedores(*, filtros: dict) -> QuerySet[Proveedor]
def obtener_proveedor(*, proveedor_id: int) -> Proveedor
    """Lanza NoEncontrado si no existe o está inactivo."""

# construccion/services.py
def crear_constructora(*, datos: dict, autor: Usuario, ip: str | None) -> Constructora
def actualizar_constructora(*, constructora: Constructora, datos: dict, autor: Usuario, ip: str | None) -> Constructora
def desactivar_constructora(*, constructora: Constructora, autor: Usuario, ip: str | None) -> None

# construccion/selectors.py
def listar_constructoras(*, filtros: dict) -> QuerySet[Constructora]
def obtener_constructora(*, constructora_id: int) -> Constructora
```

La normalización del NIT es la misma función que usa `crm`. Si la spec 004 la
dejó en `crm`, se mueve a `core` para que la usen las tres apps sin depender
entre sí (se coordina con B en el PR).

## 7. Auditoría

| Acción | Cuándo | Valores |
|---|---|---|
| `CREAR` | Alta de proveedor o constructora | Todos los campos |
| `ACTUALIZAR` | `PATCH` | Valores anteriores y nuevos de los campos que cambiaron |
| Desactivación | `DELETE` | `activo` anterior y nuevo |

Para la desactivación se usa la misma acción de `AccionAuditoria` que use la
spec 004. Entidades: `compras_proveedor` y `construccion_constructora`. Se
registra dentro de la transacción del servicio (spec 001).

## 8. Criterios de aceptación

- [ ] Se puede crear, listar, ver, editar y desactivar proveedores y
      constructoras por la API.
- [ ] El código se genera solo (`PRV-0001`, `CST-0001`) y un `PATCH` no lo cambia.
- [ ] Un banco sin NIT responde 400; un propietario particular sin NIT se crea.
- [ ] Dos proveedores con el mismo NIT en el mismo país responden 409
      `PROVEEDOR_DUPLICADO`, aunque el primero esté desactivado y aunque uno se
      escriba con guiones y el otro sin ellos.
- [ ] El mismo NIT en dos países distintos sí se permite.
- [ ] Varios propietarios particulares sin NIT en el mismo país se permiten.
- [ ] Una constructora con calificación 0 o 6 responde 400; sin calificación se crea.
- [ ] Una ciudad de otro país responde 400.
- [ ] Un usuario `AGENTE`, `CONTABILIDAD` o `CONSULTA` lee pero no escribe (403).
- [ ] Un registro desactivado no aparece en los listados.
- [ ] Toda escritura queda en la bitácora del sistema.
- [ ] Los comandos de demo crean datos ficticios y, corridos dos veces, no
      duplican nada.
- [ ] `ruff`, `makemigrations --check` y `pytest` pasan
      (`docs/convenciones.md` §1.1).

## 9. Pruebas

- **Servicios:** códigos, normalización y duplicados, regla 2, ciudad del país,
  auditoría de cada escritura.
- **Selectores:** filtros y exclusión de inactivos.
- **API:** un caso feliz y uno de error por endpoint, y los permisos por rol.

## 10. Decisiones y alternativas descartadas

**NIT opcional solo para el propietario particular (a validar).** Un banco, una
inmobiliaria o una entidad de gobierno siempre tienen NIT. Una persona que vende
su casa puede no tenerlo registrado o no querer darlo en el primer contacto.
Se descartó exigirlo a todos (frenaría el registro de particulares) y hacerlo
opcional para todos (permitiría bancos duplicados sin forma de detectarlos).

**Calificación opcional.** Obligarla al registrar forzaría un número inventado
que después ensuciaría los reportes de constructoras.

**Reglas de desactivación en la spec 007.** "No se desactiva un proveedor con un
contrato `EN_PROCESO`" o "una constructora con un proyecto `EN_EJECUCION`" son
reglas correctas, pero hablan de entidades que todavía no existen. Escribirlas
aquí obligaría a adivinar los estados de la spec 007.

**`Constructora` sin ciudad.** `docs/modelo-datos.md` no la incluye y una
constructora suele trabajar en varias ciudades de su país. Se mantiene el modelo
como está.

**Mismos patrones que la spec 004** (código a partir del `id`, NIT normalizado
con constraint condicional, `TieneRol` por método, comando de demo propio). Ya
fueron revisados y aprobados por el equipo: repetirlos hace esta spec más rápida
de revisar y el código más fácil de explicar en la defensa.

**Dependencia de la spec 004.** Esta spec usa `TieneRol`
(`usuarios/permissions.py`) y la normalización del NIT, que crea la spec 004.
Si al implementar todavía no están en `develop`, se espera ese PR o se coordina
con B. No se duplica el código.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-28, borrador (Claude, rol C).** El agente leyó
`docs/modelo-datos.md` §6 y §7, `docs/roadmap.md` y las specs 003 y 004, y
propuso el borrador siguiendo los patrones ya aprobados en la 004. Quedan para
validar en la revisión: la regla 2 (NIT del particular) y la calificación
opcional.

**Plan de implementación (un commit por incremento):**

1. Modelos `Proveedor` y `Constructora`, constraints, migraciones y panel
2. Servicios y selectores de proveedores, con auditoría y pruebas
3. Servicios y selectores de constructoras, con auditoría y pruebas
4. API, filtros y permisos de las dos
5. Comandos de demostración y cierre

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.