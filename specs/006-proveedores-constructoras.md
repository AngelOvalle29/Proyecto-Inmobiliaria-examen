# 006 · Compras y construcción: proveedores y constructoras

| Campo | Valor |
|---|---|
| **Número** | 006 |
| **Estado** | Implementada |
| **Autor** | Angel Glicerio Ovalle Fernandez (rol C) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `compras` (incluido `cargar_demo_compras`), `construccion` (incluido `cargar_demo_construccion`), `config/urls.py` |
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
  `Propiedad`. Van en la spec 017 del rol C.
- Reglas de desactivación con contratos o proyectos abiertos: se agregan en la
  spec 017, cuando esas entidades existan (§10).
- Reactivar un registro desactivado: ni por la API ni por el panel, que es de
  solo lectura como en la spec 004 (§10).
- Llamar a los comandos de demo desde `seed_demo`: lo ajusta A en `core`, como
  en la spec 004.
- Pantallas: van sobre la base del frontend, con la lista y el formulario
  genéricos.

## 3. Reglas de negocio

**Proveedores**

1. Un proveedor tiene un tipo: `PROPIETARIO_PARTICULAR`, `INMOBILIARIA`,
   `BANCO`, `GOBIERNO` u `OTRO`.
2. El NIT es obligatorio para todos los tipos **excepto**
   `PROPIETARIO_PARTICULAR`, para quien es opcional. *Validada en la revisión
   del PR #39* (§10).
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

Para la regla 7 se reutiliza `CiudadFueraDelPais` de `core`, la misma excepción
que usa `crm`. También hay un error `NIT_OBLIGATORIO` (400) para un NIT que falta
o que queda vacío al normalizarlo, por ejemplo `"-"`.

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

La normalización del NIT es `normalizar_documento` de `core/normalizacion.py`, la
misma que usa `crm`: el equipo ya la había movido a `core` en las revisiones de
#35 y #39, así que esta spec no tuvo que tocarla.

`obtener_proveedor` y `obtener_constructora` no se escribieron como funciones
aparte: las vistas de detalle usan `get_object()` sobre `listar_proveedores()` y
`listar_constructoras()`, igual que `crm`, y un registro inactivo o inexistente
responde 404.

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

- [x] Se puede crear, listar, ver, editar y desactivar proveedores y
      constructoras por la API.
- [x] El código se genera solo (`PRV-0001`, `CST-0001`) y un `PATCH` no lo cambia.
- [x] Un banco sin NIT responde 400; un propietario particular sin NIT se crea.
- [x] Dos proveedores con el mismo NIT en el mismo país responden 409
      `PROVEEDOR_DUPLICADO`, aunque el primero esté desactivado y aunque uno se
      escriba con guiones y el otro sin ellos.
- [x] El mismo NIT en dos países distintos sí se permite.
- [x] Varios propietarios particulares sin NIT en el mismo país se permiten.
- [x] Una constructora con calificación 0 o 6 responde 400; sin calificación se crea.
- [x] Una ciudad de otro país responde 400.
- [x] Un usuario `AGENTE`, `CONTABILIDAD` o `CONSULTA` lee pero no escribe (403).
- [x] Un registro desactivado no aparece en los listados.
- [x] Toda escritura queda en la bitácora del sistema.
- [x] Los comandos de demo crean datos ficticios y, corridos dos veces, no
      duplican nada.
- [x] `ruff`, `makemigrations --check` y `pytest` pasan
      (`docs/convenciones.md` §1.1).

## 9. Pruebas

- **Servicios:** códigos, normalización y duplicados, regla 2, ciudad del país,
  auditoría de cada escritura.
- **Selectores:** filtros y exclusión de inactivos.
- **API:** un caso feliz y uno de error por endpoint, y los permisos por rol.

## 10. Decisiones y alternativas descartadas

**NIT opcional solo para el propietario particular (validada en el PR #39).** Un banco, una
inmobiliaria o una entidad de gobierno siempre tienen NIT. Una persona que vende
su casa puede no tenerlo registrado o no querer darlo en el primer contacto.
Se descartó exigirlo a todos (frenaría el registro de particulares) y hacerlo
opcional para todos (permitiría bancos duplicados sin forma de detectarlos).

**Calificación opcional.** Obligarla al registrar forzaría un número inventado
que después ensuciaría los reportes de constructoras. Por eso `?calificacion_min=`
deja fuera a las que no tienen calificación.

**Las reglas también en la base.** NIT obligatorio, NIT único por país y
calificación de 1 a 5 son constraints de PostgreSQL además de validaciones del
servicio: aunque alguien se salte el servicio, la base no acepta esos datos.

**`NitObligatorio` en cada app.** `compras` y `construccion` tienen cada una la
suya, con el mismo código. Ponerla en `core` habría tocado una app de A por un
error que solo usan estas dos; repetir una clase de diez líneas mantiene a las
dos apps independientes, que es lo que pide `docs/arquitectura.md` §3.

**Datos de demostración sin auditoría.** Mismo criterio que `cargar_demo_crm`
(spec 004): son la foto inicial de la demostración, no operaciones del negocio.
Si un país todavía no existe, el registro se omite en lugar de fallar.

**Reglas de desactivación en la spec 017.** "No se desactiva un proveedor con un
contrato `EN_PROCESO`" o "una constructora con un proyecto `EN_EJECUCION`" son
reglas correctas, pero hablan de entidades que todavía no existen. Escribirlas
aquí obligaría a adivinar los estados de la spec 017.

**Panel de Django de solo lectura** (corregido en la revisión del PR #63). La
primera versión dejaba el panel editable para reactivar registros, y la
revisión mostró que así se saltaban las reglas: un proveedor creado desde el
panel quedaba sin código y con el NIT sin normalizar, editar no se auditaba y
borrar eliminaba el registro. Se usa el mismo `AdminSoloLectura` de `crm` y
`catalogo`, una copia por app para que las apps no dependan entre sí.

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

**Implementación, 2026-10-31 (Claude, rol C).** Los cinco incrementos se
agruparon en dos commits, uno por app:

| Commit | Incrementos |
|---|---|
| `feat(compras): agregar proveedores con API, auditoría y datos de demostración` | 1, 2, 4 y 5 de `compras` |
| `feat(construccion): agregar constructoras con API, auditoría y datos de demostración` | 1, 3, 4 y 5 de `construccion` |

**Qué generó el agente.** El código de las dos apps, sus pruebas y los datos de
demostración. Antes de escribirlo, el integrante C le mostró el código real de
`crm`, `usuarios/permissions.py`, `core/normalizacion.py` y `core/exceptions.py`,
para seguir los mismos patrones y nombres en lugar de suponerlos. El agente lo
corrió en una réplica con PostgreSQL: pruebas, `ruff`, `makemigrations --check`
y el esquema de `drf-spectacular`.

**Qué verificó el integrante C en su máquina:** las migraciones
`compras.0001_proveedores` y `construccion.0001_constructoras`, generadas ahí;
la suite completa con 583 pruebas (62 nuevas), `ruff` y `makemigrations --check`
limpios; y los dos comandos de demostración (6 proveedores y 4 constructoras, y
0 nuevos al correrlos otra vez).

**Revisión de Marco (PR #63), 2026-10-31.** Señaló que el panel de Django
permitía escribir sin reglas ni auditoría, que los serializadores debían usar
`listar_paises()` y `listar_ciudades()` como `crm`, y que la spec mencionaba la
007 en lugar de la 017. Se aceptaron los tres: el panel es de solo lectura (con
una prueba por app) y los serializadores usan los selectores de `core`.

**Pendiente para A (Douglas):** agregar `cargar_demo_compras` y
`cargar_demo_construccion` a `COMANDOS_DE_DEMO` de `seed_demo`.
