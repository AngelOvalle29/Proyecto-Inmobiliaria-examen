# 003 · Catálogo: tipos de propiedad, propiedades y unidades

| Campo | Valor |
|---|---|
| **Número** | 003 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce) |
| **Fecha** | 2026-10-28 |
| **Apps afectadas** | `catalogo` (incluido su comando `cargar_demo_catalogo`) |
| **Rama** | `feature/003-catalogo-propiedades` |
| **Pull request** | [DouGMV/Proyecto-Inmobiliaria#34](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/34) (spec aprobada en #33) |

---

## 1. Problema

La agencia no tiene dónde registrar las propiedades que administra: terrenos,
casas, edificios de apartamentos, hoteles, bodegas, restaurantes y
gasolineras, con sus unidades cuando las hay. Sin ese registro no se pueden
cotizar, vender, arrendar, comprar ni construir, porque todas esas operaciones
apuntan a una propiedad.

Es el camino crítico del plan de una semana (`docs/roadmap.md`): cotizaciones,
ventas y arrendamientos (rol B) y compras y construcción (rol C) dependen de
`Propiedad`. Por eso esta spec se limita a lo que ellos necesitan, y avalúos y
documentos oficiales van en una spec posterior (§2).

## 2. Alcance

**Incluye:**
- Modelos `TipoPropiedad`, `Propiedad` y `Unidad`, con borrado lógico y campos
  de rastro
- API de lectura y escritura de los tres, con filtros y búsqueda
- El servicio `cambiar_estado_propiedad`, que usarán ventas, arrendamientos,
  compras y construcción
- Los siete tipos de propiedad, cargados con una migración de datos
- Auditoría de toda escritura
- Comando `cargar_demo_catalogo` con propiedades y unidades ficticias

**No incluye:**
- **Avalúos y documentos oficiales:** spec posterior. Dependen de dos decisiones
  abiertas: dónde se guardan los archivos en producción (`CLAUDE.md` §9) y el
  ciclo `DocumentoOficial` ↔ contratos de venta y compra, que se acuerda con
  B y C.
- **`EventoPropiedad`** (historial): queda para si sobra tiempo, según el plan.
  Mientras tanto, la bitácora de auditoría registra cada cambio de estado.
- **`Amenidad`:** queda para si sobra tiempo.
- **Reglas de transición de estados:** cada spec que cambia el estado (ventas,
  arrendamientos, compras, construcción) define las suyas (§3, regla 7).
- Pantallas: van sobre la base del frontend (#15).

## 3. Reglas de negocio

1. Una propiedad tiene un tipo, una ciudad, un precio de lista con su moneda y
   un estado. Su país es el de su ciudad.
2. **Solo las propiedades de un tipo que requiere unidades** (edificio de
   apartamentos, hotel) pueden tener unidades.
3. El código de una propiedad (`PROP-00001`) lo genera el sistema y no cambia.
   El código de una unidad (`A-101`) lo pone el usuario y es único dentro de su
   propiedad.
4. Precios y áreas son mayores que cero. No se exige que el área construida sea
   menor que la del terreno: en un edificio de varios niveles es mayor.
5. `es_publica` decide si el agente de IA, en modo público, puede mostrar la
   propiedad (`docs/modelo-datos.md`).
6. No se borra nada físicamente: desactivar marca `activo` en falso. Una
   propiedad con unidades activas no se puede desactivar.
7. El estado inicial es `EN_NEGOCIACION`. Los cambios de estado pasan siempre
   por el servicio `cambiar_estado_propiedad`, que audita el cambio. En esta
   spec solo `ADMINISTRADOR` y `GERENTE` cambian el estado a mano; las demás
   apps lo cambian desde sus servicios, con sus propias reglas.
8. Escriben `ADMINISTRADOR` y `GERENTE`. Leen todos los roles autenticados.

## 4. Modelo de datos

```
catalogo → core, usuarios, auditoria
```

### `catalogo.TipoPropiedad` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `nombre` | CharField(50) | Único |
| `descripcion` | CharField(255) | Opcional |
| `requiere_unidades` | BooleanField | Regla 2 |

Una migración de datos crea los siete: Apartamentos (edificio, con unidades),
Terreno, Casa, Hotel (con unidades), Bodega, Restaurante y Gasolinera.

### `catalogo.Propiedad` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(12) | Único, generado (`PROP-00001`); nulo solo durante la creación, como en la spec 004 |
| `nombre` | CharField(150) | |
| `tipo` | FK `TipoPropiedad` | `PROTECT` |
| `ciudad` | FK `core.Ciudad` | `PROTECT` |
| `direccion` | CharField(255) | |
| `latitud`, `longitud` | DecimalField(9, 6) | Opcionales |
| `area_m2` | DecimalField(12, 2) | > 0 |
| `area_construida_m2` | DecimalField(12, 2) | Opcional, > 0 |
| `estado` | CharField, enum `EstadoPropiedad` | `EN_NEGOCIACION`, `ADQUIRIDA`, `EN_CONSTRUCCION`, `DISPONIBLE`, `RESERVADA`, `VENDIDA`, `ARRENDADA`, `BAJA` |
| `precio_lista` | DecimalField(18, 2) | > 0 |
| `moneda` | FK `core.Moneda` | `PROTECT` |
| `es_publica` | BooleanField | Por defecto `False` |
| `descripcion` | TextField | Opcional |

Se elimina de `docs/modelo-datos.md` `fecha_registro`, porque `creado_en` guarda
lo mismo (mismo criterio que la spec 004).

**Constraints:** `precio_lista > 0`, `area_m2 > 0`, `area_construida_m2 > 0`
cuando existe. **Índices:** `codigo`, `estado`, `tipo`, `ciudad`
(`docs/modelo-datos.md` §11).

### `catalogo.Unidad` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `propiedad` | FK `Propiedad` | `PROTECT`, `related_name="unidades"` |
| `codigo` | CharField(20) | Único por propiedad |
| `nivel` | SmallIntegerField | Puede ser negativo (sótanos) |
| `area_m2` | DecimalField(12, 2) | > 0 |
| `habitaciones`, `banos` | PositiveSmallIntegerField | |
| `estado` | Mismo enum `EstadoPropiedad` | |
| `precio_lista` | DecimalField(18, 2) | > 0 |
| `moneda` | FK `core.Moneda` | `PROTECT` |

## 5. API

Configuración común de la spec 001. Permisos con `TieneRol` de la spec 004
(cerrado por defecto para escrituras).

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/api/v1/tipos-propiedad/` · `/{id}/` | Autenticado |
| POST · PATCH · DELETE | `/api/v1/tipos-propiedad/` · `/{id}/` | `ADMINISTRADOR` |
| GET | `/api/v1/propiedades/` · `/{id}/` | Autenticado |
| POST · PATCH · DELETE | `/api/v1/propiedades/` · `/{id}/` | `ADMINISTRADOR`, `GERENTE` |
| POST | `/api/v1/propiedades/{id}/cambiar-estado/` | `ADMINISTRADOR`, `GERENTE` |
| GET | `/api/v1/propiedades/{id}/unidades/` | Autenticado |
| POST | `/api/v1/propiedades/{id}/unidades/` | `ADMINISTRADOR`, `GERENTE` |
| GET · PATCH · DELETE | `/api/v1/unidades/{id}/` | Lectura autenticado; escritura `ADMINISTRADOR`, `GERENTE` |
| POST | `/api/v1/unidades/{id}/cambiar-estado/` | `ADMINISTRADOR`, `GERENTE` |

**Filtros de `/propiedades/`:** `?tipo=`, `?ciudad=`, `?pais=`, `?estado=`,
`?moneda=`, `?precio_min=`, `?precio_max=`, `?es_publica=` y `?buscar=` (código,
nombre o dirección), en `catalogo/filters.py`, como en la spec 004.

**`PATCH /propiedades/{id}/` no cambia el estado**: para eso está
`/cambiar-estado/`, que audita la transición con su propia acción. Lo mismo
vale para `PATCH /unidades/{id}/`.

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `TIPO_SIN_UNIDADES` | Se agrega una unidad a una propiedad cuyo tipo no las admite (regla 2) | 409 |
| `UNIDAD_DUPLICADA` | Ya existe una unidad con ese código en la propiedad (regla 3) | 409 |
| `PROPIEDAD_CON_UNIDADES` | Se desactiva una propiedad con unidades activas (regla 6) | 409 |
| `PROPIEDAD_NO_DISPONIBLE` | Otra app cambia el estado con `estado_requerido` y la propiedad o unidad no está en ese estado (agregado por la spec 007) | 409 |

## 6. Servicios y selectores

```python
# catalogo/services.py  (transaction.atomic y registrar_auditoria)
def crear_propiedad(*, datos: dict, autor: Usuario, ip: str | None) -> Propiedad
def actualizar_propiedad(*, propiedad: Propiedad, datos: dict, autor: Usuario, ip: str | None) -> Propiedad
def desactivar_propiedad(*, propiedad: Propiedad, autor: Usuario, ip: str | None) -> None
def cambiar_estado_propiedad(*, propiedad: Propiedad, estado: EstadoPropiedad,
                             autor: Usuario | None, ip: str | None, motivo: str,
                             estado_requerido: EstadoPropiedad | None = None) -> Propiedad
    """Punto único de cambio de estado: lo usan las vistas y los servicios de
    ventas, arrendamientos, compras y construcción. Audita estado anterior,
    nuevo y motivo. Si el estado no cambia, no hace nada. Con estado_requerido,
    comprueba el estado actual después de bloquear la fila y lanza
    PROPIEDAD_NO_DISPONIBLE si no coincide."""
def cambiar_estado_unidad(*, unidad: Unidad, estado: EstadoPropiedad,
                          autor: Usuario | None, ip: str | None, motivo: str,
                          estado_requerido: EstadoPropiedad | None = None) -> Unidad
    """Igual que cambiar_estado_propiedad, para una unidad. No cambia el
    estado de su propiedad: eso lo decide el servicio que la llama."""
def crear_unidad(*, propiedad: Propiedad, datos: dict, autor: Usuario, ip: str | None) -> Unidad
def actualizar_unidad(...) -> Unidad
def desactivar_unidad(...) -> None
def crear_tipo_propiedad(...) / actualizar_tipo_propiedad(...) / desactivar_tipo_propiedad(...)

# catalogo/selectors.py
def listar_propiedades() -> QuerySet[Propiedad]          # activas, con tipo, ciudad, país y moneda
def obtener_propiedad(*, propiedad_id: int) -> Propiedad
def listar_unidades(*, propiedad: Propiedad | None = None) -> QuerySet[Unidad]
def listar_propiedades_publicas() -> QuerySet[Propiedad] # para el agente de IA (rol C)
def listar_tipos_propiedad() -> QuerySet[TipoPropiedad]
```

**Para B y C:** las demás apps **solo** usan estos servicios y selectores, nunca
los modelos de `catalogo` directamente (`docs/arquitectura.md` §3). En
particular, cambian el estado con `cambiar_estado_propiedad` y
`cambiar_estado_unidad`.

## 7. Auditoría

Crear, editar y desactivar los tres modelos: `CREAR`, `ACTUALIZAR` y `ELIMINAR`,
como en la spec 004. **Cambiar de estado** (propiedad o unidad): `ACTUALIZAR` con
`{"estado": anterior}` → `{"estado": nuevo, "motivo": ...}`.
`cargar_demo_catalogo` no audita.

## 8. Criterios de aceptación

- [x] Los siete tipos de propiedad existen después de `migrate`
- [x] Un administrador o gerente crea una propiedad y recibe `PROP-NNNNN`
- [x] Agente, contabilidad y consulta leen propiedades y reciben 403 al escribir
- [x] La base rechaza precios y áreas menores o iguales a cero
- [x] Agregar una unidad a una casa devuelve 409 `TIPO_SIN_UNIDADES`
- [x] Dos unidades con el mismo código en la misma propiedad: 409 `UNIDAD_DUPLICADA`
- [x] Desactivar una propiedad con unidades activas: 409 `PROPIEDAD_CON_UNIDADES`
- [x] `PATCH` no cambia el estado; `/cambiar-estado/` sí, y lo audita con su motivo
- [x] Lo mismo para las unidades, con `/unidades/{id}/cambiar-estado/`
- [x] Los filtros y la búsqueda devuelven solo lo que corresponde, paginado
- [x] El listado de propiedades no hace una consulta por propiedad (N+1)
- [x] Toda escritura queda en la bitácora
- [x] `cargar_demo_catalogo` carga propiedades y unidades ficticias sin duplicar
- [x] `ruff`, `pytest` y `makemigrations --check` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Modelo | Constraints de precio, áreas y unidad única por propiedad |
| Servicio | Crear propiedad genera el código y audita con el código final |
| Servicio | `cambiar_estado_propiedad` audita anterior, nuevo y motivo; sin cambio no audita |
| Servicio | Unidad en tipo sin unidades y desactivar propiedad con unidades: rechazados |
| Selector | `listar_propiedades_publicas` solo trae públicas y activas |
| API | Matriz de permisos por rol en los endpoints de escritura |
| API | Filtros, búsqueda y número de consultas del listado |

## 10. Decisiones y alternativas descartadas

**Avalúos y documentos en otra spec.** Dependen de dos decisiones que no son
solo de A (almacenamiento y el ciclo con los contratos). Esperarlas atrasaría a
B y a C, que solo necesitan `Propiedad`.

**Estado solo por `cambiar_estado_propiedad`.** Si cada app escribiera
`propiedad.estado` por su cuenta, no habría un solo lugar donde auditar el
cambio ni donde, más adelante, generar el `EventoPropiedad`. Por la misma razón
el `PATCH` no lo cambia.

**Sin reglas de transición en esta spec.** Las conocen las specs que causan el
cambio: vender exige `DISPONIBLE` o `RESERVADA`, construir exige `ADQUIRIDA`…
Definirlas aquí obligaría a adivinar reglas de negocio de B y C.

**Tipos con migración de datos**, igual que los roles de la spec 001: el sistema
no funciona sin ellos, y deben existir en producción con solo `migrate`.

**Código `PROP-NNNNN` a partir del `id`**, con `codigo` nulo hasta asignarlo:
mismo patrón y misma razón que la spec 004.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-28, borrador (Claude Code, rol A).** Se redactó con el alcance
reducido del plan de una semana: solo lo que desbloquea a B y C.

**Plan de implementación:**
1. Modelos, constraints, migración de los tipos y panel ✅
2. Servicios (incluido `cambiar_estado_propiedad`) y selectores, con auditoría ✅
3. API, filtros y permisos ✅
4. `cargar_demo_catalogo` y cierre ✅

**Sesión 2026-10-28, implementación (Claude Code, rol A).** Lo que se descubrió
o se decidió al implementar:

- `listar_unidades` acepta `propiedad` opcional: `/unidades/{id}/` necesita
  todas las unidades activas, no solo las de una propiedad. Se agregaron
  `existe_unidad` y `contar_unidades_activas` para que los servicios no
  consulten los modelos directamente.
- El duplicado de código de unidad cuenta también las desactivadas, porque la
  restricción única de la base las incluye.
- Las relaciones se leen como resumen (`tipo: {id, nombre}`) y se escriben con
  su id (`tipo_id`), que solo acepta tipos, ciudades y monedas activos.
- Un `PUT` responde 403 y no 405: DRF revisa los permisos antes que el método,
  y `TieneRol` cierra todo método de escritura no declarado.
- Desactivar un tipo de propiedad no afecta a las propiedades que ya lo usan;
  la spec no pedía otra cosa.
- `TieneRol` se implementó aquí en `usuarios/permissions.py`, tal como lo
  define la spec 004, para que CRM lo reutilice.
- `seed_demo` llama a los comandos de demostración de cada app por nombre y
  omite los que aún no existen (DouGMV/Proyecto-Inmobiliaria#13).

**Sesión 2026-10-29, revisión cruzada con la spec 004 y la de ventas (Claude
Code, rol A).**

- `TieneRol` se copió tal cual del PR de CRM (DouGMV/Proyecto-Inmobiliaria#35):
  hacían lo mismo, y con archivos idénticos los dos PR se fusionan sin conflicto.
- `CiudadResumenSerializer` del catálogo pasó a llamarse
  `CiudadConPaisSerializer`: CRM tiene uno con el mismo nombre y otros campos, y
  la documentación de la API no admite dos componentes con el mismo nombre.
- **Agregado a pedido de la spec de ventas** (DouGMV/Proyecto-Inmobiliaria#37):
  `cambiar_estado_unidad` y `POST /unidades/{id}/cambiar-estado/`. En un
  edificio se vende o se arrienda cada apartamento, no el edificio. Por la
  regla 7, el `PATCH` de una unidad ya no cambia su estado. Los dos servicios
  comparten los mismos pasos (bloqueo, auditoría, sin cambio no audita).

**Ampliación de la spec 007 (DouGMV/Proyecto-Inmobiliaria#44, 2026-10-29).** B
agregó a los dos servicios el parámetro opcional `estado_requerido` y el error
`PROPIEDAD_NO_DISPONIBLE` (409).
- El estado actual se comprueba **después** de bloquear la fila, así que
  comprobar y cambiar quedan en el mismo paso.
- Sin eso, dos aprobaciones simultáneas de cotizaciones sobre la misma
  propiedad podían pasar las dos.
- Lo usan ventas y arrendamientos, por ejemplo: firmar exige `DISPONIBLE` o
  `RESERVADA`, y anular exige `VENDIDA`.
- Es opcional: quien no lo pasa, como la vista `/cambiar-estado/`, se comporta
  igual que antes.
- A lo revisó y aprobó en #44, y lo anota aquí para que la spec siga
  describiendo el código.
