# 001 · Fundación del proyecto

| Campo | Valor |
|---|---|
| **Número** | 001 |
| **Estado** | En revisión |
| **Autor** | Equipo |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-08 |
| **Apps afectadas** | `config`, `core`, `usuarios`, `auditoria` (y creación vacía de las once apps) |
| **Rama** | `feature/001-fundacion` |
| **Pull request** | — |

---

## 1. Problema

El equipo no puede trabajar en paralelo mientras no exista el esqueleto del
proyecto. Sin modelos base comunes, sin autenticación y sin infraestructura
local, cada integrante tomaría decisiones distintas y el código no encajaría
después.

Esta spec levanta la base mínima sobre la que los cuatro integrantes construyen
sus dominios sin bloquearse.

## 2. Alcance

**Incluye:**
- Proyecto Django con la configuración separada por entorno (`base`, `dev`,
  `test`, `prod`)
- Las once apps creadas y vacías, con la estructura de `docs/arquitectura.md` §3
- Infraestructura local con Docker Compose (PostgreSQL con pgvector y RabbitMQ)
- Modelo base abstracto con campos de rastro
- Entidades de catálogo geográfico y monetario, con su conversión de montos
- Autenticación JWT por correo, con roles
- Bitácora de auditoría del sistema, usada en esta fase solo para los accesos
- Configuración transversal de la API: errores uniformes, paginación, filtros,
  límite de peticiones, CORS y documentación automática
- Herramientas de calidad: `ruff`, `pytest` contra PostgreSQL
- Comando `seed_demo` con datos geográficos y monetarios ficticios

**No incluye:**
- CRUD de propiedades (spec 003 en adelante)
- Despliegue en producción (spec 002). Eso incluye cómo se sirven los archivos
  estáticos en producción y los ajustes al `Dockerfile`
- Configuración de Celery (`config/celery.py`): se levanta el contenedor de
  RabbitMQ, pero Celery se conecta en la spec 002 (worker) y su primer flujo
  real llega en la fase 4
- Extensión `vector` de PostgreSQL: se habilita con una migración en la spec
  002 o en la app `ia` (fase 5). Aquí solo se usa la imagen que la trae
- Bitácora del agente de IA (`auditoria_log_agente`): llega con la fase 5
- Escritura de catálogos vía API: en esta fase se administran desde el panel
  de Django
- Permisos asociados a cada rol: se definen con las primeras specs de CRUD
- Frontend (fase 2; el stack está definido en `docs/frontend.md`)

## 3. Reglas de negocio

1. Todo usuario se autentica con su correo electrónico. No existe nombre de
   usuario.
2. Todo usuario tiene exactamente un rol. Un rol con usuarios asignados no se
   puede borrar.
3. Todo superusuario tiene el rol `ADMINISTRADOR`.
4. Un tipo de cambio es único por combinación de moneda origen, moneda destino
   y fecha.
5. Una tasa de cambio es siempre mayor que cero, y su moneda origen es distinta
   de su moneda destino.
6. La tasa vigente a una fecha es la registrada en esa fecha o, si no hay, la
   más reciente anterior. Nunca se usa una tasa posterior a la fecha.
7. Convertir un monto a la misma moneda usa tasa 1. No se calculan tasas
   inversas: si se necesita GTQ→USD, debe existir un registro GTQ→USD.
8. Un monto convertido se redondea a 2 decimales, con redondeo comercial
   (`ROUND_HALF_UP`).
9. Toda entidad de negocio registra quién la creó, quién la modificó y cuándo.
   Los catálogos de `core` no son entidades de negocio (ver §10).
10. Las entidades de negocio y los catálogos no se borran físicamente: se marcan
    como inactivos.
11. Todo inicio de sesión, exitoso o fallido, queda registrado en la bitácora
    de auditoría.

## 4. Modelo de datos

### Dependencias entre apps

```
core          ← no importa ninguna app
auditoria     ← no importa ninguna app (al usuario lo referencia con
                settings.AUTH_USER_MODEL)
usuarios      → core, auditoria
apps de dominio (fase 2+) → core, usuarios, auditoria
```

Ningún modelo concreto de `core` hereda de `ModeloBase`. Si lo hiciera,
`core` dependería de `usuarios` en las migraciones, y como `Usuario` apunta a
`core.Pais`, se formaría un ciclo.

### `core.ModeloBase` (abstracto)

| Campo | Tipo | Nota |
|---|---|---|
| `creado_en` | DateTimeField | `auto_now_add` |
| `creado_por` | FK `settings.AUTH_USER_MODEL` | Nulo para registros del sistema. `PROTECT`, sin relación inversa (`related_name="+"`) |
| `actualizado_en` | DateTimeField | `auto_now` |
| `actualizado_por` | FK `settings.AUTH_USER_MODEL` | Nulo. `PROTECT`, sin relación inversa |
| `activo` | BooleanField | Por defecto `True` |

Lo heredan las entidades de negocio a partir de la fase 2. Los campos
`creado_por` y `actualizado_por` los llena el servicio que escribe, no el
modelo.

### `core.Moneda`
`codigo` (3 caracteres, único) · `nombre` · `simbolo` · `activo`

### `core.Pais`
`nombre` (único) · `codigo_iso` (3 caracteres, único) ·
`moneda_principal` (FK Moneda, `PROTECT`) · `activo`

### `core.Ciudad`
`nombre` · `pais` (FK, `PROTECT`) · `region` (opcional) · `activo`
— único por nombre y país

### `core.TipoCambio`
`moneda_origen` (FK, `PROTECT`) · `moneda_destino` (FK, `PROTECT`) ·
`tasa` (Decimal 18,6) · `fecha` (DateField)

Constraints en la base de datos:
- Único por `moneda_origen`, `moneda_destino` y `fecha`
- `tasa > 0`
- `moneda_origen <> moneda_destino`

No lleva `activo`: una tasa equivocada se corrige editándola, no se desactiva.

### `usuarios.Rol`
`nombre` (único, enum `NombreRol`: `ADMINISTRADOR`, `GERENTE`, `AGENTE`,
`CONTABILIDAD`, `CONSULTA`) · `descripcion`

Los cinco roles se crean con una **migración de datos**, para que existan
antes del primer `createsuperuser`.

### `usuarios.Usuario`
Extiende `AbstractUser`, con estos cambios:

| Campo | Tipo | Nota |
|---|---|---|
| `username` | — | Eliminado. El login es por `email` |
| `first_name`, `last_name` | — | Eliminados. Los sustituye `nombre_completo` |
| `email` | EmailField | Único. `USERNAME_FIELD` |
| `nombre_completo` | CharField | Obligatorio. En `REQUIRED_FIELDS` |
| `rol` | FK Rol | Obligatorio, `PROTECT` |
| `pais` | FK `core.Pais` | Opcional, `PROTECT` |
| `telefono` | CharField | Opcional |

- Se reutiliza `last_login` de Django como último acceso. No se agrega
  `ultimo_acceso`.
- Se reutiliza `is_active` de Django como borrado lógico. No se agrega
  `activo`, porque Django ya impide autenticarse a un usuario inactivo.
- Un manager propio (`UsuarioManager`) crea usuarios por correo; su
  `create_superuser` asigna el rol `ADMINISTRADOR`.

### `auditoria.LogAuditoria` (tabla `auditoria_log_sistema`)

Campos de `docs/arquitectura.md` §5. Detalles que fija esta spec:

- `usuario`: FK `settings.AUTH_USER_MODEL`, nulo, `PROTECT`.
- `entidad_id`: nulo (un login fallido con un correo inexistente no tiene
  registro asociado).
- `accion`: `CREAR`, `ACTUALIZAR`, `ELIMINAR`, `APROBAR`, `ANULAR`,
  `INICIAR_SESION`, `LOGIN_FALLIDO`.
- Índices por (`entidad`, `entidad_id`) y por `fecha`.
- Es de solo inserción: nunca se edita ni se borra.

## 5. API

Configuración común a todos los endpoints:

- Autenticación por defecto: JWT. Permiso por defecto: autenticado.
- Paginación por número de página, 25 elementos (`?page=N`).
- Filtros con `django-filter`.
- Tokens: acceso de 30 minutos, refresco de 7 días, tomados de
  `JWT_ACCESS_TOKEN_MINUTES` y `JWT_REFRESH_TOKEN_DAYS`.
- Límite de peticiones en `auth/login/` y `auth/refresh/`: 10 por minuto por IP.
- CORS restringido a `CORS_ALLOWED_ORIGINS`.

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | Obtener par de tokens con correo y contraseña | Público |
| POST | `/api/v1/auth/refresh/` | Renovar token de acceso | Público |
| GET | `/api/v1/auth/yo/` | Datos del usuario autenticado | Autenticado |
| GET | `/api/v1/paises/` | Listar países activos | Autenticado |
| GET | `/api/v1/ciudades/` | Listar ciudades activas. Filtro: `?pais=<id>` | Autenticado |
| GET | `/api/v1/monedas/` | Listar monedas activas | Autenticado |
| GET | `/api/v1/tipos-cambio/` | Tipos de cambio, de la fecha más reciente a la más antigua. Filtros: `?moneda_origen=<id>`, `?moneda_destino=<id>`, `?fecha=`, `?fecha_desde=`, `?fecha_hasta=` | Autenticado |
| GET | `/api/v1/health/` | Estado del servicio y de la base de datos | Público |
| GET | `/api/schema/` · `/api/docs/` | Esquema OpenAPI y su interfaz | Público |

**Login. Petición:**

```json
{ "email": "admin@demo.test", "password": "••••••••••" }
```

**Login. Respuesta 200:**

```json
{ "access": "<jwt>", "refresh": "<jwt>" }
```

**`/auth/yo/`. Respuesta 200:**

```json
{
  "id": 1,
  "email": "admin@demo.test",
  "nombre_completo": "Administrador Demo",
  "rol": "ADMINISTRADOR",
  "pais": { "id": 1, "nombre": "Guatemala" },
  "telefono": "",
  "ultimo_acceso": "2026-10-08T15:30:00Z"
}
```

**`/health/`. Respuestas:** `200 {"estado": "ok", "base_datos": "ok"}`, o
`503 {"estado": "error", "base_datos": "error"}` si `SELECT 1` falla.

**Formato de error.** Todas las respuestas de error usan el formato de
`docs/arquitectura.md` §4. Un manejador global (`apps/core/manejador_errores.py`)
traduce tanto las excepciones de dominio como las de DRF:

| Código | Situación | HTTP |
|---|---|---|
| `VALIDACION` | Datos de entrada inválidos (`detalles` lleva los errores por campo) | 400 |
| `CREDENCIALES_INVALIDAS` | Login con correo o contraseña incorrectos, o usuario inactivo | 401 |
| `NO_AUTENTICADO` | Falta el token, o es inválido o está vencido | 401 |
| `SIN_PERMISO` | Autenticado pero sin permiso | 403 |
| `NO_ENCONTRADO` | Recurso inexistente | 404 |
| `DEMASIADAS_PETICIONES` | Se superó el límite de peticiones | 429 |
| `TIPO_CAMBIO_NO_DISPONIBLE` | No hay tasa vigente para la fecha | 422 |

Las excepciones de dominio heredan de una clase base `ErrorDominio`
(`apps/core/exceptions.py`) que lleva `codigo`, `mensaje`, `detalles` y el
estado HTTP.

## 6. Servicios y selectores

```python
# core/selectors.py
def obtener_tipo_cambio(*, origen: Moneda, destino: Moneda, fecha: date) -> Decimal
    """Tasa vigente a la fecha (reglas 6 y 7). Lanza TipoCambioNoDisponible si no hay."""

def convertir_monto(*, monto: Decimal, origen: Moneda, destino: Moneda, fecha: date) -> Decimal
    """Convierte con la tasa vigente a la fecha de la transacción (regla 8)."""

def verificar_base_datos() -> bool
    """True si la base de datos responde. Lo usa el endpoint de salud."""

# auditoria/services.py
def registrar_auditoria(
    *, usuario: Usuario | None, entidad: str, entidad_id: int | None,
    accion: AccionAuditoria, valores_anteriores: dict | None = None,
    valores_nuevos: dict | None = None, ip: str | None = None,
    user_agent: str | None = None,
) -> LogAuditoria
    """Registra una operación. Se llama dentro de la transacción de quien escribe."""

# usuarios/services.py
def registrar_acceso(*, usuario: Usuario, ip: str | None, user_agent: str | None) -> None
    """Actualiza last_login y registra INICIAR_SESION, en una sola transacción."""

def registrar_login_fallido(*, email: str, ip: str | None, user_agent: str | None) -> None
    """Registra LOGIN_FALLIDO con el correo intentado. Nunca guarda la contraseña."""
```

`last_login` se actualiza explícitamente en `registrar_acceso` y no con la
opción `UPDATE_LAST_LOGIN` de SimpleJWT, para que la escritura sea visible en
el código.

La IP del cliente se obtiene en la capa HTTP (`apps/core/http.py`): primer
valor de `X-Forwarded-For` si existe (Railway pone la API detrás de un proxy),
si no `REMOTE_ADDR`. El servicio recibe la IP ya resuelta y no conoce
`request`.

## 7. Auditoría

- La tabla `auditoria_log_sistema` se crea en esta spec.
- Se registran `INICIAR_SESION` (con `usuario` y `entidad_id`) y
  `LOGIN_FALLIDO` (con `usuario` nulo y el correo intentado en
  `valores_nuevos`), ambos con IP y `user_agent`.
- **Excepción temporal documentada:** las ediciones de catálogos en el panel de
  Django **no** se auditan en esta fase. Los catálogos no tienen servicios de
  escritura todavía. Cuando una spec agregue escritura de catálogos vía API, esa
  escritura pasará por servicios auditados. Para respetar la regla 10, el panel
  no permite borrar catálogos: se desactivan con `activo`.
- La bitácora del panel de Django (`django_admin_log`) sigue existiendo y deja
  rastro mínimo de esas ediciones mientras tanto.

## 8. Criterios de aceptación

**Infraestructura y configuración**
- [ ] `docker compose up -d` levanta PostgreSQL con pgvector y RabbitMQ
- [ ] `python manage.py migrate` corre sin errores sobre PostgreSQL
- [ ] Existen las once apps bajo `backend/apps/`, cada una con su estructura de
      archivos
- [ ] Existen `config/settings/base.py`, `dev.py`, `test.py` y `prod.py`
- [ ] `prod.py` falla al arrancar si faltan `SECRET_KEY` o `DATABASE_URL` (sin
      valores por defecto)
- [ ] No hay ninguna credencial en el repositorio; todo viene de `.env`

**Usuarios y autenticación**
- [ ] `createsuperuser` pide correo y nombre completo (no nombre de usuario) y
      asigna el rol `ADMINISTRADOR`
- [ ] Los cinco roles existen después de `migrate`, sin pasos manuales
- [ ] `POST /api/v1/auth/login/` devuelve un par de tokens válidos
- [ ] Un login con credenciales inválidas devuelve 401 con el código
      `CREDENCIALES_INVALIDAS` en el formato uniforme
- [ ] Un endpoint protegido devuelve 401 sin token y 200 con token válido
- [ ] El undécimo intento de login en un minuto desde la misma IP devuelve 429
- [ ] Un login exitoso actualiza `last_login` y deja un registro `INICIAR_SESION`
- [ ] Un login fallido deja un registro `LOGIN_FALLIDO` sin la contraseña
- [ ] Las contraseñas de menos de 10 caracteres se rechazan

**Catálogos**
- [ ] Los listados están paginados de 25 en 25
- [ ] `/api/v1/ciudades/?pais=<id>` devuelve solo ciudades de ese país
- [ ] `/api/v1/tipos-cambio/` filtra por monedas y rango de fechas
- [ ] La base de datos rechaza dos tipos de cambio iguales para la misma fecha,
      una tasa menor o igual a cero, y una moneda convertida a sí misma
- [ ] El panel de Django no permite borrar catálogos
- [ ] `obtener_tipo_cambio` devuelve la tasa correcta cuando no hay registro
      exacto para la fecha
- [ ] `seed_demo` carga países, ciudades, monedas y tipos de cambio ficticios, y
      correrlo dos veces no duplica datos

**API y calidad**
- [ ] `GET /api/v1/health/` responde 200 sin autenticación
- [ ] `/api/docs/` muestra la documentación generada automáticamente
- [ ] `ruff check` y `ruff format --check` pasan sin advertencias
- [ ] `pytest` pasa y corre contra PostgreSQL, no contra SQLite
- [ ] `makemigrations --check` no detecta migraciones pendientes

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Selector | `obtener_tipo_cambio` con fecha exacta |
| Selector | `obtener_tipo_cambio` sin fecha exacta, toma la anterior más cercana |
| Selector | `obtener_tipo_cambio` ignora tasas posteriores a la fecha |
| Selector | `obtener_tipo_cambio` sin ninguna tasa disponible lanza `TipoCambioNoDisponible` |
| Selector | `obtener_tipo_cambio` con la misma moneda devuelve 1 |
| Selector | `convertir_monto` entre dos monedas distintas, redondeado a 2 decimales |
| Servicio | `registrar_auditoria` guarda todos los campos |
| Servicio | `registrar_acceso` actualiza `last_login` y registra `INICIAR_SESION` |
| Servicio | `registrar_login_fallido` registra el correo y no la contraseña |
| Modelo | No se pueden crear dos tipos de cambio iguales para la misma fecha |
| Modelo | Se rechaza una tasa menor o igual a cero y una moneda origen igual a la destino |
| Modelo | `create_superuser` asigna el rol `ADMINISTRADOR` |
| API | Login correcto devuelve tokens |
| API | Login con credenciales inválidas devuelve 401 con formato uniforme |
| API | `/auth/yo/` devuelve 401 sin token y 200 con token |
| API | `/health/` devuelve 200 sin autenticación |
| API | `/ciudades/?pais=` filtra correctamente |
| API | Los listados devuelven como máximo 25 elementos por página |

## 10. Decisiones y alternativas descartadas

**Django REST Framework sobre Spring Boot.** Se evaluaron ambos. Django gana por
el ecosistema de Python para el agente de IA y el RAG (pgvector, SDKs maduros),
por la velocidad de desarrollo del CRUD de 25 entidades, y porque Celery con
RabbitMQ es el camino más directo para el requisito de mensajería asíncrona.
Spring Boot ofrecía mejor estructura por defecto, pero el costo en tiempo de los
componentes de IA y reportería era mayor del que el equipo puede absorber.

**Capa de servicios y selectores sobre el Django canónico.** Django por defecto
concentra lógica en vistas y modelos, lo que choca con el requisito de
arquitectura lógica del curso. La capa explícita cuesta algo de verbosidad pero
hace la arquitectura defendible oralmente, que es lo que se evalúa.

**Auditoría explícita sobre señales de Django.** Las señales serían menos código,
pero son difíciles de rastrear y de explicar. Llamar a `registrar_auditoria`
desde cada servicio deja la intención visible en el código.

**PostgreSQL única para datos y vectores.** Se descartó un motor de vectores
aparte (Pinecone, Qdrant) para no multiplicar la infraestructura a desplegar.
pgvector cubre el volumen de este proyecto con holgura.

**`auditoria` como app transversal.** La regla original decía que solo `core` y
`usuarios` podían ser importadas por todas, pero el login (en `usuarios`)
necesita registrar auditoría. Se descartó mover el login a `auditoria` (mezcla
responsabilidades) y se declaró `auditoria` transversal. No importa ninguna app
y referencia al usuario con `settings.AUTH_USER_MODEL`, así que no se forma un
ciclo de importaciones.

**Los catálogos de `core` no heredan `ModeloBase`.** País, ciudad, moneda y tipo
de cambio son datos de referencia, no operaciones del negocio. Si heredaran
`ModeloBase`, `core` dependería de `usuarios` y `usuarios` de `core` (por
`Usuario.pais`), y las migraciones quedarían en ciclo. Django puede romper ese
ciclo partiendo migraciones, pero el resultado es difícil de explicar.

**`Rol` como tabla y no como campo de texto con opciones.** La spec pide un rol
por usuario, y `docs/modelo-datos.md` prevé asociarle permisos. Una tabla permite
eso sin migrar datos después. Se descartó usar directamente los `Group` de Django
porque un usuario puede estar en varios grupos, y la regla dice exactamente uno.

**Login por correo eliminando `username`.** Mantener `username` junto a `email`
obliga a decidir qué se guarda en él y abre la puerta a dos identificadores.
Se elimina y se escribe un manager propio, que es el patrón documentado por
Django.

**Reutilizar `last_login` e `is_active`.** Agregar `ultimo_acceso` y `activo` al
usuario duplicaría campos que Django ya tiene y que su sistema de autenticación
ya usa. Dos campos con el mismo significado terminan desincronizados.

**Sin tasas inversas automáticas.** Calcular GTQ→USD como 1 / (USD→GTQ) parece
cómodo, pero en la práctica las casas de cambio publican tasas de compra y de
venta distintas. Exigir el registro explícito es más simple de explicar y más
fiel al negocio.

**Ediciones del panel sin auditar, como excepción temporal.** Auditarlas
requeriría servicios de escritura para catálogos que todavía no los necesitan.
Se documenta la excepción (§7) en lugar de dejarla implícita.

**`prod.py` sin valores por defecto para secretos.** Si falta `SECRET_KEY` o
`DATABASE_URL`, producción no arranca, en lugar de arrancar con valores falsos.
El `Dockerfile` corre `collectstatic` con los settings de producción al
construir la imagen, así que la spec 002 debe pasar valores ficticios solo a ese
paso y decidir cómo se sirven los archivos estáticos.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-08, revisión de la spec antes de implementar (Claude Code).**
Se le pidió al agente leer la spec, la arquitectura y el resto de los documentos,
proponer un plan por incrementos y señalar huecos sin escribir código. Detectó:

- La contradicción entre la regla de dependencias de `arquitectura.md` y el
  modelo de datos (ciclo `core` ↔ `usuarios` y `usuarios` → `auditoria`)
- La falta de una acción de auditoría para el login
- Campos de `Usuario` duplicados con `AbstractUser`
- Reglas sin definir en `obtener_tipo_cambio` (misma moneda, inversa, redondeo)
- Configuración transversal de la API ausente de los criterios de aceptación
- La inconsistencia sobre Redis entre documentos

El equipo aceptó las recomendaciones y la spec se actualizó a esta versión.

**Plan de implementación acordado (un commit por incremento):**

1. Proyecto Django, settings por entorno, requisitos, ruff y pytest (sin migrar)
2. Las once apps con su estructura de archivos
3. Modelos de `core` (sin migrar todavía)
4. `Usuario` y `Rol`, `AUTH_USER_MODEL`, migración de datos de roles. **Primer
   `migrate`**: hacerlo antes de este punto crea las tablas con el usuario por
   defecto de Django, y cambiarlo después obliga a recrear la base
5. Selectores de tipo de cambio y conversión, con pruebas
6. Configuración de DRF, manejador de errores, CORS, health y documentación
7. `LogAuditoria` y `registrar_auditoria`
8. Autenticación JWT con registro de acceso y límite de peticiones en login.
   El límite se movió aquí desde el incremento 6 durante la implementación:
   solo aplica a `auth/login/` y `auth/refresh/`, y necesita decidir dónde
   guarda DRF los contadores (ver la nota del incremento 6)
9. Endpoints de catálogos con filtros
10. `seed_demo`
11. Cierre: README y esta sección

**Nota del incremento 6.** DRF guarda los contadores del límite de peticiones
en la caché de Django. Sin Redis, la caché por defecto vive en la memoria de
cada proceso, y en producción gunicorn corre 3 procesos: cada uno contaría por
separado y el límite real sería el triple. Hay que decidir entre la caché en
la base de datos de Django (tabla propia en PostgreSQL) o aceptar la
imprecisión. Se resuelve antes del incremento 8.

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.
