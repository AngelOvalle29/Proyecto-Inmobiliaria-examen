# 001 · Fundación del proyecto

| Campo | Valor |
|---|---|
| **Número** | 001 |
| **Estado** | Borrador |
| **Autor** | Equipo |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-08 |
| **Apps afectadas** | `config`, `core`, `usuarios` |
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
- Proyecto Django con la configuración separada por entorno
- Las once apps creadas y vacías
- Infraestructura local con Docker Compose (PostgreSQL con pgvector y RabbitMQ)
- Modelo base abstracto con campos de rastro
- Entidades de catálogo geográfico y monetario
- Autenticación JWT con roles
- Herramientas de calidad y documentación automática

**No incluye:**
- CRUD de propiedades (spec 002 en adelante)
- Despliegue en producción (spec 002)
- Frontend (fase 2; el stack está definido en `docs/frontend.md`)
- Celery y RabbitMQ conectados a flujos reales (se levanta el contenedor, pero
  el primer flujo llega en la fase 4)

## 3. Reglas de negocio

1. Todo usuario se autentica con su correo electrónico, no con nombre de
   usuario.
2. Todo usuario tiene exactamente un rol.
3. Un tipo de cambio es único por combinación de moneda origen, moneda destino
   y fecha.
4. Toda entidad de negocio registra quién la creó, quién la modificó y cuándo.
5. Las entidades de negocio no se borran físicamente: se marcan como inactivas.

## 4. Modelo de datos

### `core.ModeloBase` (abstracto)

| Campo | Tipo | Nota |
|---|---|---|
| `creado_en` | DateTimeField | `auto_now_add` |
| `creado_por` | FK Usuario | Nulo para registros del sistema |
| `actualizado_en` | DateTimeField | `auto_now` |
| `actualizado_por` | FK Usuario | Nulo |
| `activo` | BooleanField | Por defecto `True` |

Todas las entidades de negocio heredan de este modelo.

### `core.Pais`
`nombre` (único) · `codigo_iso` (3 caracteres, único) · `moneda_principal` (FK)

### `core.Ciudad`
`nombre` · `pais` (FK) · `region` — único por nombre y país

### `core.Moneda`
`codigo` (3 caracteres, único) · `nombre` · `simbolo`

### `core.TipoCambio`
`moneda_origen` (FK) · `moneda_destino` (FK) · `tasa` (Decimal 18,6) · `fecha`
— único por las tres primeras columnas

### `usuarios.Rol`
`nombre` (único, enum) · `descripcion`

### `usuarios.Usuario`
Extiende `AbstractUser`. `email` como campo de login, `nombre_completo`,
`rol` (FK), `pais` (FK), `telefono`, `ultimo_acceso`.

## 5. API

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | Obtener par de tokens | Público |
| POST | `/api/v1/auth/refresh/` | Renovar token de acceso | Público |
| GET | `/api/v1/auth/yo/` | Datos del usuario autenticado | Autenticado |
| GET | `/api/v1/paises/` | Listar países | Autenticado |
| GET | `/api/v1/ciudades/` | Listar ciudades, filtrable por país | Autenticado |
| GET | `/api/v1/monedas/` | Listar monedas | Autenticado |
| GET | `/api/v1/tipos-cambio/` | Tipos de cambio, filtrable por fecha | Autenticado |
| GET | `/api/v1/health/` | Estado del servicio | Público |

Las entidades de catálogo son de solo lectura vía API en esta fase; se
administran desde el panel de Django.

## 6. Servicios y selectores

```python
# core/selectors.py
def obtener_tipo_cambio(*, origen: Moneda, destino: Moneda, fecha: date) -> Decimal
    """Tasa vigente a la fecha. Si no hay exacta, usa la más reciente anterior."""

def convertir_monto(*, monto: Decimal, origen: Moneda, destino: Moneda, fecha: date) -> Decimal
    """Convierte usando la tasa vigente a la fecha de la transacción."""

# usuarios/services.py
def registrar_acceso(*, usuario: Usuario, ip: str) -> None
```

## 7. Auditoría

La tabla de auditoría se crea en esta spec, pero su uso generalizado llega con
las specs de CRUD. En esta fase solo se registra el inicio de sesión.

## 8. Criterios de aceptación

- [ ] `docker compose up -d` levanta PostgreSQL con pgvector y RabbitMQ
- [ ] `python manage.py migrate` corre sin errores sobre PostgreSQL
- [ ] Existen las once apps, cada una con su estructura de archivos
- [ ] `POST /api/v1/auth/login/` devuelve un par de tokens válidos
- [ ] Un endpoint protegido devuelve 401 sin token y 200 con token válido
- [ ] `GET /api/v1/health/` responde 200 sin autenticación
- [ ] `/api/docs/` muestra la documentación generada automáticamente
- [ ] `seed_demo` carga países, ciudades, monedas y tipos de cambio de prueba
- [ ] `ruff check` y `ruff format --check` pasan sin advertencias
- [ ] `pytest` pasa y corre contra PostgreSQL, no contra SQLite
- [ ] `obtener_tipo_cambio` devuelve la tasa correcta cuando no hay registro
      exacto para la fecha
- [ ] No hay ninguna credencial en el repositorio; todo viene de `.env`

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Servicio | `obtener_tipo_cambio` con fecha exacta |
| Servicio | `obtener_tipo_cambio` sin fecha exacta, toma la anterior más cercana |
| Servicio | `obtener_tipo_cambio` sin ninguna tasa disponible lanza excepción |
| Servicio | `convertir_monto` entre dos monedas distintas |
| API | Login correcto devuelve tokens |
| API | Login con credenciales inválidas devuelve 401 |
| API | Endpoint protegido sin token devuelve 401 |
| Modelo | No se pueden crear dos tipos de cambio iguales para la misma fecha |

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

## 11. Trabajo con agentes de IA

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó.
