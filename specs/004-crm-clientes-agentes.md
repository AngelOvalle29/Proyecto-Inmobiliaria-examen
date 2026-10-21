# 004 · CRM: clientes y agentes

| Campo | Valor |
|---|---|
| **Número** | 004 |
| **Estado** | Borrador |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-21 |
| **Apps afectadas** | `crm`, `usuarios` (permisos por rol), `core` (`seed_demo`) |
| **Rama** | `feature/004-crm-clientes-agentes` |
| **Pull request** | — |

---

## 1. Problema

La agencia no tiene dónde registrar a sus clientes ni a los agentes que los
atienden. Sin ese registro no se pueden emitir cotizaciones, firmar contratos
de venta ni de arrendamiento, porque todos apuntan a un cliente y a un agente.

Además, cada agente trabaja su propia cartera: no debe ver ni modificar los
clientes de otro. La agencia necesita saber en todo momento qué agente atiende
a cada cliente y poder reasignarlos cuando un agente se va.

Esta spec crea `Cliente` y `Agente`, que no dependen del catálogo de
propiedades, y define el **primer esquema de permisos por rol** del sistema:
las specs siguientes lo reutilizan.

## 2. Alcance

**Incluye:**
- Modelos `Agente` y `Cliente`, con borrado lógico y campos de rastro
- API de lectura y escritura de agentes y clientes, con filtros y búsqueda
- Reasignación de un cliente a otro agente
- Permisos por rol y por objeto (cartera propia del agente)
- Clases de permiso reutilizables en `usuarios/permissions.py`
- Auditoría de toda escritura
- Datos de demostración ficticios: agentes y clientes en `seed_demo`

**No incluye:**
- Cotizaciones y su detalle: necesitan `Propiedad` (spec 003). Van en una spec
  propia del rol B cuando el catálogo esté en `develop`.
- Pantallas del frontend: se construyen sobre la base del frontend (rol A). Van
  en una spec posterior del rol B.
- Alta y edición de usuarios vía API: los usuarios se siguen creando desde el
  panel de Django (spec 001, §7).
- Reactivar un cliente o un agente desactivado vía API: se hace desde el panel.
- Comisiones calculadas: el porcentaje se guarda aquí, el cálculo llega con
  ventas.

## 3. Reglas de negocio

**Agentes**

1. Un agente es un usuario con rol `AGENTE` y un perfil comercial: código,
   porcentaje de comisión y fecha de ingreso. Un usuario tiene como máximo un
   perfil de agente.
2. Su nombre, teléfono, correo y país son los de su usuario. No se duplican en
   el agente.
3. El porcentaje de comisión está entre 0 y 100, con dos decimales.
4. Un agente con clientes activos asignados no se puede desactivar. Primero se
   reasigna su cartera.
5. Un agente desactivado no puede recibir clientes nuevos ni reasignados.

**Clientes**

6. Un cliente es una `PERSONA` o una `EMPRESA`.
   - Una persona tiene obligatoriamente nombre, apellidos y documento de
     identidad.
   - Una empresa tiene obligatoriamente razón social y NIT.
7. No puede haber dos personas con el mismo documento de identidad en el mismo
   país, ni dos empresas con el mismo NIT en el mismo país, aunque una de ellas
   esté desactivada.
8. Todo cliente tiene exactamente un agente asignado.
9. La ciudad del cliente es opcional, pero si se indica debe pertenecer a su
   país.
10. El código del cliente (`CLI-00001`) y el del agente (`AGT-001`) los genera
    el sistema y no cambian.

**Permisos (primer esquema del sistema)**

11. `ADMINISTRADOR` y `GERENTE` ven y modifican todos los clientes, y son los
    únicos que administran agentes y reasignan clientes.
12. Un `AGENTE` solo ve y modifica los clientes de su cartera. Los clientes que
    crea quedan asignados a él. No puede reasignarlos.
13. `CONTABILIDAD` y `CONSULTA` ven todos los clientes y agentes, sin
    modificarlos.
14. Un agente que pide un cliente que no es de su cartera recibe 404, no 403:
    no debe poder averiguar qué clientes existen.

## 4. Modelo de datos

### Dependencias

```
crm → core, usuarios, auditoria
```

`crm` es la primera app de dominio. Las siguientes (`ventas`,
`arrendamientos`) dependerán de ella.

### `crm.Agente` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `usuario` | OneToOne `settings.AUTH_USER_MODEL` | `PROTECT`, `related_name="agente"` |
| `codigo` | CharField(10) | Único, generado (`AGT-001`) |
| `porcentaje_comision` | DecimalField(5, 2) | Constraint: entre 0 y 100 |
| `fecha_ingreso` | DateField | |

Se elimina de `docs/modelo-datos.md`: `nombre_completo`, `telefono` y `pais`
(regla 2) y `activo` como campo propio (viene de `ModeloBase`).

### `crm.Cliente` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `codigo` | CharField(10) | Único, generado (`CLI-00001`) |
| `tipo` | CharField, enum `TipoCliente` | `PERSONA`, `EMPRESA` |
| `nombre` | CharField(100) | Obligatorio si es persona |
| `apellidos` | CharField(100) | Obligatorio si es persona |
| `razon_social` | CharField(200) | Obligatorio si es empresa |
| `documento_identidad` | CharField(30) | Obligatorio si es persona |
| `nit` | CharField(30) | Obligatorio si es empresa; opcional para persona |
| `email` | EmailField | Opcional |
| `telefono` | CharField(30) | Opcional |
| `pais` | FK `core.Pais` | Obligatorio, `PROTECT` |
| `ciudad` | FK `core.Ciudad` | Opcional, `PROTECT` |
| `direccion` | CharField(255) | Opcional |
| `agente_asignado` | FK `Agente` | Obligatorio, `PROTECT`, `related_name="clientes"` |
| `notas` | TextField | Opcional |

Se elimina de `docs/modelo-datos.md`: `fecha_registro`, porque `creado_en` de
`ModeloBase` guarda lo mismo.

Los campos de texto opcionales usan cadena vacía, no nulo (mismo criterio que
`Ciudad.region` en la spec 001).

**Constraints en la base de datos:**
- `CheckConstraint`: si `tipo = PERSONA`, `nombre`, `apellidos` y
  `documento_identidad` no están vacíos (regla 6).
- `CheckConstraint`: si `tipo = EMPRESA`, `razon_social` y `nit` no están
  vacíos (regla 6).
- `UniqueConstraint` sobre (`pais`, `documento_identidad`) con condición
  `tipo = PERSONA` (regla 7).
- `UniqueConstraint` sobre (`pais`, `nit`) con condición `tipo = EMPRESA`
  (regla 7).

La regla 9 (ciudad del país) se valida en el servicio, porque compara con otra
tabla.

**Índices:** `codigo` (único), `agente_asignado`, `pais` (claves foráneas,
`docs/modelo-datos.md` §11).

**Generación de códigos (regla 10):** el servicio crea el registro y, en la
misma transacción, asigna el código a partir del `id`:
`CLI-{id:05d}` y `AGT-{id:03d}`. El `id` lo da PostgreSQL, así que no hay dos
iguales aunque dos usuarios creen clientes al mismo tiempo.

## 5. API

Configuración común de la spec 001: JWT, paginación de 25, errores uniformes.

### Agentes

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| GET | `/api/v1/agentes/` | Agentes activos. Filtros: `?pais=<id>`, `?buscar=` (nombre, correo o código) | Autenticado |
| GET | `/api/v1/agentes/{id}/` | Detalle, con la cantidad de clientes activos | Autenticado |
| POST | `/api/v1/agentes/` | Crear el perfil de agente de un usuario | `ADMINISTRADOR`, `GERENTE` |
| PATCH | `/api/v1/agentes/{id}/` | Editar comisión o fecha de ingreso | `ADMINISTRADOR`, `GERENTE` |
| DELETE | `/api/v1/agentes/{id}/` | Desactivar (borrado lógico) | `ADMINISTRADOR`, `GERENTE` |

**Crear agente. Petición:**

```json
{ "usuario": 7, "porcentaje_comision": "3.50", "fecha_ingreso": "2026-10-01" }
```

**Agente. Respuesta 200 / 201:**

```json
{
  "id": 3,
  "codigo": "AGT-003",
  "usuario": { "id": 7, "email": "agente1@demo.test", "nombre_completo": "Agente Demo Uno" },
  "telefono": "",
  "pais": { "id": 1, "nombre": "Guatemala" },
  "porcentaje_comision": "3.50",
  "fecha_ingreso": "2026-10-01",
  "clientes_activos": 12
}
```

### Clientes

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| GET | `/api/v1/clientes/` | Clientes activos visibles para el usuario (reglas 11 a 13). Filtros: `?tipo=`, `?pais=<id>`, `?ciudad=<id>`, `?agente=<id>`, `?buscar=` (nombre, apellidos, razón social, documento, NIT, correo o código) | Autenticado |
| GET | `/api/v1/clientes/{id}/` | Detalle | Autenticado, con cartera (regla 14) |
| POST | `/api/v1/clientes/` | Crear | `ADMINISTRADOR`, `GERENTE`, `AGENTE` |
| PATCH | `/api/v1/clientes/{id}/` | Editar datos (no el agente) | `ADMINISTRADOR`, `GERENTE`, `AGENTE` de su cartera |
| DELETE | `/api/v1/clientes/{id}/` | Desactivar (borrado lógico) | `ADMINISTRADOR`, `GERENTE`, `AGENTE` de su cartera |
| POST | `/api/v1/clientes/{id}/reasignar/` | Cambiar el agente asignado | `ADMINISTRADOR`, `GERENTE` |

En `POST /clientes/`, `agente_asignado` es obligatorio para administrador y
gerente, y se ignora para un agente, que siempre queda asignado a sí mismo
(regla 12).

**Crear cliente. Petición (persona):**

```json
{
  "tipo": "PERSONA",
  "nombre": "Cliente",
  "apellidos": "Demo Uno",
  "documento_identidad": "1234567890101",
  "email": "cliente1@demo.test",
  "pais": 1,
  "ciudad": 2,
  "agente_asignado": 3
}
```

**Cliente. Respuesta 200 / 201:**

```json
{
  "id": 15,
  "codigo": "CLI-00015",
  "tipo": "PERSONA",
  "nombre": "Cliente",
  "apellidos": "Demo Uno",
  "razon_social": "",
  "documento_identidad": "1234567890101",
  "nit": "",
  "email": "cliente1@demo.test",
  "telefono": "",
  "pais": { "id": 1, "nombre": "Guatemala" },
  "ciudad": { "id": 2, "nombre": "Quetzaltenango" },
  "direccion": "",
  "agente_asignado": { "id": 3, "codigo": "AGT-003", "nombre_completo": "Agente Demo Uno" },
  "notas": "",
  "creado_en": "2026-10-21T15:30:00Z"
}
```

**Reasignar. Petición:** `{ "agente": 5 }`

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `CLIENTE_DUPLICADO` | Ya existe una persona con ese documento, o una empresa con ese NIT, en el mismo país (regla 7) | 409 |
| `CIUDAD_FUERA_DEL_PAIS` | La ciudad no pertenece al país del cliente (regla 9) | 400 |
| `AGENTE_INACTIVO` | Se asigna o reasigna un cliente a un agente desactivado (regla 5) | 409 |
| `AGENTE_CON_CLIENTES` | Se intenta desactivar un agente con clientes activos (regla 4) | 409 |
| `USUARIO_NO_ES_AGENTE` | Se crea un perfil de agente para un usuario sin rol `AGENTE` (regla 1) | 400 |
| `USUARIO_YA_ES_AGENTE` | El usuario ya tiene perfil de agente (regla 1) | 409 |
| `SIN_PERFIL_DE_AGENTE` | Un usuario con rol `AGENTE` sin perfil intenta crear un cliente | 403 |

Los datos que faltan según el tipo de cliente (regla 6) se responden con
`VALIDACION` (400), indicando el campo.

## 6. Servicios y selectores

```python
# usuarios/permissions.py  (capa HTTP, reutilizable por todas las apps)
class TieneRol(BasePermission)
    """Permite el acceso solo a los roles listados en la vista (roles_permitidos)."""

# crm/selectors.py
def listar_agentes() -> QuerySet[Agente]
    """Agentes activos, con su usuario y la cantidad de clientes activos."""

def obtener_agente_de_usuario(*, usuario: Usuario) -> Agente | None
    """Perfil de agente del usuario, o None si no lo tiene."""

def listar_clientes_visibles(*, usuario: Usuario) -> QuerySet[Cliente]
    """Clientes activos que el usuario puede ver (reglas 11 a 13). Un agente,
    solo su cartera."""

# crm/services.py  (todas con transaction.atomic y registrar_auditoria)
def crear_agente(*, usuario_agente: Usuario, porcentaje_comision: Decimal,
                 fecha_ingreso: date, autor: Usuario, ip: str | None) -> Agente
def actualizar_agente(*, agente: Agente, datos: dict, autor: Usuario,
                      ip: str | None) -> Agente
def desactivar_agente(*, agente: Agente, autor: Usuario, ip: str | None) -> None

def crear_cliente(*, datos: dict, autor: Usuario, ip: str | None) -> Cliente
    """Si el autor es agente, el cliente queda asignado a él (regla 12)."""
def actualizar_cliente(*, cliente: Cliente, datos: dict, autor: Usuario,
                       ip: str | None) -> Cliente
def desactivar_cliente(*, cliente: Cliente, autor: Usuario, ip: str | None) -> None
def reasignar_cliente(*, cliente: Cliente, agente: Agente, autor: Usuario,
                      ip: str | None) -> Cliente
```

Los servicios reciben al `autor` para llenar `creado_por` y `actualizado_por`
y para la auditoría. Los permisos de rol se verifican en la vista (`TieneRol`);
la cartera, en el selector (regla 14: el cliente ajeno simplemente no se
encuentra).

## 7. Auditoría

Toda escritura de esta spec registra en `auditoria_log_sistema`, dentro de la
transacción del servicio, con el usuario autor y su IP:

| Operación | Acción | Valores |
|---|---|---|
| Crear agente o cliente | `CREAR` | `valores_nuevos`: todos los campos |
| Editar agente o cliente | `ACTUALIZAR` | Solo los campos que cambiaron, antes y después |
| Reasignar cliente | `ACTUALIZAR` | `agente_asignado` antes y después |
| Desactivar agente o cliente | `ELIMINAR` | `activo`: `true` → `false` |

`seed_demo` no registra auditoría, igual que en la spec 001.

## 8. Criterios de aceptación

**Agentes**
- [ ] Un administrador o gerente crea el perfil de agente de un usuario con rol
      `AGENTE`, y el sistema le asigna el código `AGT-NNN`
- [ ] Crear un agente para un usuario sin rol `AGENTE` devuelve 400
      `USUARIO_NO_ES_AGENTE`
- [ ] Un agente con clientes activos no se puede desactivar (409
      `AGENTE_CON_CLIENTES`)
- [ ] Un agente, contabilidad o consulta que intenta crear o editar un agente
      recibe 403

**Clientes**
- [ ] Un agente crea un cliente y queda asignado a él, aunque envíe otro agente
- [ ] Un agente lista solo sus clientes, y el detalle de un cliente ajeno
      devuelve 404
- [ ] Contabilidad y consulta listan todos los clientes, y reciben 403 al
      intentar escribir
- [ ] Una persona sin documento de identidad, o una empresa sin NIT, devuelve
      400 indicando el campo
- [ ] Un documento o NIT repetido en el mismo país devuelve 409
      `CLIENTE_DUPLICADO`; en otro país se acepta
- [ ] Una ciudad de otro país devuelve 400 `CIUDAD_FUERA_DEL_PAIS`
- [ ] Solo administrador y gerente reasignan, y no a un agente desactivado
- [ ] Los filtros y la búsqueda devuelven solo lo que corresponde, paginado de
      25 en 25

**Transversales**
- [ ] Toda escritura deja su registro de auditoría con valores anteriores y
      nuevos
- [ ] Los registros nunca se borran físicamente: desactivar marca `activo` en
      falso
- [ ] `seed_demo` carga agentes y clientes ficticios, sin duplicar al correrlo
      dos veces
- [ ] `ruff`, `pytest` y `makemigrations --check` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Modelo | La base rechaza una persona sin documento y una empresa sin NIT |
| Modelo | La base rechaza un documento repetido en el mismo país y lo acepta en otro |
| Modelo | La base rechaza un porcentaje de comisión fuera de 0 a 100 |
| Servicio | `crear_agente` genera el código y audita; rechaza usuarios sin rol `AGENTE` o con perfil |
| Servicio | `desactivar_agente` rechaza a un agente con clientes activos |
| Servicio | `crear_cliente` asigna al autor si es agente y genera el código |
| Servicio | `crear_cliente` rechaza una ciudad de otro país y un agente inactivo |
| Servicio | `actualizar_cliente` audita solo los campos que cambiaron |
| Servicio | `reasignar_cliente` cambia el agente y audita antes y después |
| Selector | `listar_clientes_visibles` da al agente solo su cartera y a los demás roles todo |
| API | Matriz de permisos: cada rol contra cada endpoint de escritura (403 donde corresponde) |
| API | Detalle de un cliente ajeno para un agente devuelve 404 |
| API | Filtros `?pais`, `?agente`, `?tipo` y `?buscar` |
| API | 409 `CLIENTE_DUPLICADO` con formato uniforme |

## 10. Decisiones y alternativas descartadas

**Cartera propia para el agente (decidido por el equipo).** `docs/arquitectura.md`
§9 pide que un agente solo vea su cartera. Se descartó que los agentes vean a
todos los clientes (más simple, pero no cumple la arquitectura) y los permisos
solo por rol, sin cartera (no protege los datos personales de los clientes de
otros agentes).

**La cartera se aplica en el selector, no en la vista.** `listar_clientes_visibles`
recibe al usuario y devuelve solo lo que puede ver; la vista de detalle busca
dentro de esa misma consulta. Así un cliente ajeno es un 404 sin código extra,
y la regla queda en un solo lugar que también podrá usar el agente de IA en
modo interno (rol C).

**404 y no 403 para el cliente ajeno.** Un 403 confirmaría que el cliente
existe. Es el mismo criterio que el login de la spec 001, que no revela qué
correos tienen cuenta.

**Permiso de rol reutilizable en `usuarios/permissions.py`.** Cada vista
declara `roles_permitidos = [NombreRol.ADMINISTRADOR, ...]` y una sola clase
`TieneRol` lo verifica. Se descartó una clase por combinación de roles
(`EsGerenteOAdministrador`, …): se multiplican con cada spec. Se descartaron
los permisos y grupos de Django porque la spec 001 eligió un rol por usuario
y no grupos.

**Agente sin datos duplicados (decidido por el equipo).** Nombre, teléfono,
correo y país ya están en `Usuario`. Mismo criterio que la spec 001 con
`last_login` e `is_active`: dos campos con el mismo significado terminan
desincronizados.

**Solo usuarios con rol `AGENTE` tienen perfil de agente.** Se descartó
permitirlo a gerentes: si un gerente atiende clientes, se le crea un usuario
agente. Mantiene una sola regla de cartera. *A confirmar en la revisión.*

**Documento único por país (decidido por el equipo).** El mismo número de
documento puede existir en dos países distintos (DPI de Guatemala y cédula de
Costa Rica son sistemas independientes). Se validan con constraints
condicionales en la base, no solo en Python, igual que los tipos de cambio en
la spec 001. Se descartó validar por correo: un cliente puede no tenerlo.

**Bloquear la desactivación de un agente con cartera (decidido por el
equipo).** Ningún cliente queda sin atender. Se descartó reasignar en el mismo
paso (una operación con dos efectos es más difícil de auditar y explicar) y
dejar clientes sin agente (obligaría a que `agente_asignado` fuera opcional y
complicaría todos los reportes por agente).

**Reasignar es una acción aparte (`/reasignar/`), no un campo del PATCH.**
Tiene permisos distintos (solo gerente y administrador) y es una operación de
negocio con nombre propio en la bitácora. Si fuera un campo más del PATCH, la
vista tendría que revisar campo por campo quién puede cambiar qué.

**`DELETE` es un borrado lógico.** Cumple la regla transversal de borrado
lógico de `CLAUDE.md` §7 y conserva los verbos estándar de REST. Se registra
como `ELIMINAR` en la bitácora.

**Código generado a partir del `id`.** Se descartó buscar el último código y
sumarle uno: dos peticiones simultáneas obtendrían el mismo. El `id` lo
asigna PostgreSQL de forma segura. Los códigos pueden tener huecos si una
transacción se revierte; no es un problema para un identificador legible.

**`pais` obligatorio y `ciudad` opcional.** Los reportes agrupan por país, así
que siempre debe existir. La ciudad es opcional porque el catálogo solo tiene
algunas ciudades por país y un cliente puede vivir en otra.

**Datos personales y el agente de IA.** Los clientes tienen datos personales.
`CLAUDE.md` prohíbe enviar datos personales reales a la API de Gemini; los
datos de `seed_demo` son ficticios (`*@demo.test`, documentos inventados). Las
herramientas del agente de IA sobre clientes las diseña el rol C con esta
restricción.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-21, borrador de la spec (Claude Code, rol B).** El agente leyó
`docs/modelo-datos.md`, `docs/arquitectura.md`, la spec 001 y el código de
`core`, `usuarios` y `auditoria`, y propuso el borrador. Las cuatro decisiones
de negocio las tomó el integrante B entre opciones planteadas por el agente:
esquema de permisos, datos del agente, duplicados y desactivación de agentes.
Las demás decisiones de §10 son propuestas del agente que se validan en la
revisión.

**Plan de implementación (un commit por incremento):**

1. `TieneRol` en `usuarios/permissions.py`, con pruebas
2. Modelos `Agente` y `Cliente`, constraints y panel de Django
3. Excepciones de `crm` y servicios de agentes, con auditoría
4. Servicios de clientes, con auditoría
5. Selectores, incluida la cartera
6. API de agentes
7. API de clientes y reasignación
8. Datos de demostración en `seed_demo`
9. Cierre: verificación de criterios y esta sección

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.
