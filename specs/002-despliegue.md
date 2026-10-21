# 002 · Despliegue en producción e integración continua

| Campo | Valor |
|---|---|
| **Número** | 002 |
| **Estado** | En revisión |
| **Autor** | Equipo |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-08 (actualizada el 2026-10-21) |
| **Apps afectadas** | `config`, `core` (migración de pgvector, tarea de diagnóstico), `usuarios` (pendiente de la spec 001), `frontend/`, infraestructura |
| **Rama** | `feature/002-despliegue` |
| **Pull request** | — |

---

## 1. Problema

El enunciado es explícito: **los sistemas no desplegados no serán revisados**.
El despliegue vale 1 punto directo, pero su ausencia pone en riesgo los 15.

El error típico es dejarlo para el final, cuando ya no hay tiempo de resolver
problemas de configuración. Esta spec monta producción cuando el sistema
todavía es mínimo, para que los errores se descubran ahora y no en noviembre.

## 2. Alcance

**Incluye:**
- Backend desplegado en Railway: API, worker de Celery, PostgreSQL con pgvector
  y RabbitMQ
- Frontend mínimo desplegado en Vercel: una página que consulta el estado de la
  API (§6)
- Settings de producción para correr detrás del proxy de Railway (§5.2)
- Archivos estáticos servidos con WhiteNoise (§5.3)
- Corrección del `Dockerfile` para que la imagen se construya (§5.4)
- Configuración mínima de Celery y un worker conectado a RabbitMQ (§5.5)
- Migración que habilita la extensión `vector` (§5.6)
- Verificación de todo el backend con Python 3.12 dentro de un contenedor
  (§7), porque GitHub Actions no se está ejecutando
- Variables de entorno y secretos configurados en ambos proveedores
- Despliegue automático al fusionar `develop` en `main`
- Cierre de los pendientes de la spec 001 (§5.7)

**No incluye:**
- Flujos reales de mensajería (notificaciones, ingesta de documentos): fase 4,
  rol D. Aquí solo se deja Celery funcionando.
- Base completa del frontend (rutas, login, menú, componentes): spec propia,
  rol A. Aquí solo se crea el proyecto con las reglas de `docs/frontend.md`.
- Protección de ramas en GitHub: no está disponible en el plan gratuito y el
  equipo decidió usar reglas internas (`docs/convenciones.md` §1.1).
- Dominio propio (se usan los subdominios de Railway y Vercel)
- Almacenamiento de documentos oficiales en producción: decisión abierta de
  `CLAUDE.md` §9; se resuelve con la spec de catálogo.
- Monitoreo avanzado ni alertas
- Respaldos fuera de los automáticos de Railway

## 3. Decisión de proveedor

**Railway para el backend, Vercel para el frontend.**

Se compararon cuatro rutas:

| Opción | Costo mensual | Esfuerzo de montaje | Mantenimiento |
|---|---|---|---|
| **Railway + Vercel** | ~$15–20 | 1–2 horas | Ninguno |
| Hetzner + Coolify | ~€11 | Medio día | Bajo |
| Hetzner + Docker Compose | ~€6 | 1 día | Continuo |
| Render administrado | ~$43 | 2 horas | Ninguno |
| Oracle Cloud capa gratuita | $0 | 1 día | Continuo, con riesgo |

**Railway gana por el criterio correcto para este proyecto.** El despliegue
vale 1 punto de 15; los otros 14 están en el agente de IA, la mensajería, la
auditoría y la reportería. Cada hora dedicada a administrar un servidor es una
hora que no se invierte en lo que sí se evalúa. Unos $15 al mes entre cuatro
personas son alrededor de Q35 cada uno.

**Se descartó Render** porque su plan gratuito no sirve (las bases de datos
expiran a los 30 días, los servicios se apagan tras 15 minutos de inactividad
y no hay trabajadores en segundo plano, así que no habría Celery) y su plan de
pago sale cerca de $43 al mes sin siquiera incluir RabbitMQ.

**Se descartó la capa gratuita de Oracle Cloud** pese a ser generosa (2 OCPU
ARM y 12 GB de memoria) porque reclama las instancias que permanezcan inactivas
y la disponibilidad de ese tipo de instancia es históricamente escasa. El
riesgo de encontrar el sistema caído el día de la defensa no compensa el
ahorro.

**La decisión es reversible.** Todo corre en contenedores, así que migrar a
Hetzner o a Oracle es cuestión de levantar el mismo `docker-compose.yml` en un
servidor. Esa portabilidad es parte de la decisión, no un accidente.

## 4. Arquitectura de despliegue

```
                  ┌──────────────┐
   Navegador ────▶│    Vercel    │  React estático, HTTPS, CDN
                  └──────┬───────┘
                         │ llamadas a la API
                         ▼
                  ┌──────────────────────────────────┐
                  │           Railway                │
                  │                                  │
                  │  ┌────────────┐  ┌────────────┐  │
                  │  │   api      │  │  worker    │  │
                  │  │  Django    │  │  Celery    │  │
                  │  │ gunicorn   │  │            │  │
                  │  └─────┬──────┘  └─────┬──────┘  │
                  │        │               │         │
                  │  ┌─────▼───────────────▼──────┐  │
                  │  │  PostgreSQL + pgvector     │  │
                  │  └────────────────────────────┘  │
                  │  ┌────────────────────────────┐  │
                  │  │        RabbitMQ            │  │
                  │  └────────────────────────────┘  │
                  └──────────────────────────────────┘
```

Cuatro servicios, no cinco: **Redis se omite al inicio**. Celery usa RabbitMQ
como broker y, mientras no se necesite consultar el resultado de las tareas, el
backend de resultados sobra. Si más adelante hace falta cache, se agrega.

## 5. Backend en Railway

### 5.1 Servicios

| Servicio | Origen | Comando de arranque |
|---|---|---|
| `api` | Repositorio, raíz `backend/`, `Dockerfile` | El `CMD` del `Dockerfile`: `migrate` y luego gunicorn con **2** procesos |
| `worker` | Mismo repositorio y `Dockerfile` | `celery -A config worker -l info` |
| `postgres` | **Plantilla de Railway con pgvector** | — |
| `rabbitmq` | Plantilla de Railway | — |

- **La plantilla de PostgreSQL debe traer pgvector.** La plantilla estándar
  puede no incluirla, y entonces la migración de §5.6 falla. Al crear el
  servicio se comprueba con
  `select * from pg_available_extensions where name = 'vector'`.
- **Las migraciones corren al arrancar `api`**, antes de gunicorn. Es seguro
  porque hay una sola instancia de `api`; si algún día hubiera varias, habría
  que moverlas a un paso de despliegue aparte.
- **2 procesos de gunicorn y no 3**: cada proceso es una copia completa de
  Django en memoria, y Railway cobra por memoria usada. Con el tráfico de una
  demostración, 2 sobran.
- **Despliegue automático** desde la rama `main`, en `api` y `worker`.
- **Ruta de salud** de Railway: `/api/v1/health/`.

**Variables de `api` y `worker`:**

| Variable | Valor |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | Clave aleatoria generada para producción, distinta de la de desarrollo |
| `DATABASE_URL` | Referencia a la variable que inyecta el servicio `postgres` |
| `RABBITMQ_URL` | Referencia a la variable de conexión AMQP que inyecta el servicio `rabbitmq` |
| `ALLOWED_HOSTS` | `<proyecto>.up.railway.app` |
| `CORS_ALLOWED_ORIGINS` | `https://<proyecto>.vercel.app` |
| `NUM_PROXIES` | `1` (spec 001, §6: define de dónde se toma la IP real) |

Las cadenas de conexión se referencian entre servicios en el panel de Railway,
nunca se copian a mano.

**Límite de gasto:** se configura antes de crear los servicios. Railway cobra
por uso y un bucle infinito en una tarea de Celery puede generar una sorpresa.
Con el tope puesto, el servicio se detiene en lugar de seguir cobrando.

**Quién paga:** *pendiente, lo decide el equipo antes del incremento 6.* El
roadmap estima entre $15 y $20 al mes.

### 5.2 Settings de producción

`config/settings/prod.py` agrega, además de lo que ya tiene:

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`: Railway
  termina HTTPS en su proxy y le pasa la petición a Django por HTTP. Sin esto
  Django cree que la conexión no es segura, y las cookies seguras y el CSRF
  del panel fallan.
- `RABBITMQ_URL` obligatoria, sin valor por defecto, como `SECRET_KEY`.
- Registro de errores en la salida estándar (`LOGGING`). Con `DEBUG = False`,
  Django no imprime las trazas de los errores 500 en la consola; sin esto, un
  error en producción no deja rastro en los registros de Railway.

No se activa `SECURE_SSL_REDIRECT`, porque Railway ya redirige a HTTPS en su
proxy y la verificación de salud del `Dockerfile` llama por HTTP dentro del
contenedor. Tampoco se activa HSTS por ahora, porque un error de configuración
de HSTS no se puede deshacer desde el servidor.

### 5.3 Archivos estáticos

Se agrega **WhiteNoise**: un middleware que sirve los archivos estáticos desde
el mismo proceso de Django, comprimidos y con caché de larga duración. Lo
necesitan el panel de Django y la documentación de `/api/docs/`, que sin estilos
quedan inutilizables.

- `whitenoise.middleware.WhiteNoiseMiddleware` va justo después de
  `SecurityMiddleware`.
- `STORAGES["staticfiles"]` usa su almacenamiento comprimido con manifiesto:
  cada archivo lleva un hash en el nombre, así que el navegador puede guardarlo
  en caché sin riesgo de usar una versión vieja.

### 5.4 `Dockerfile`

Hoy la imagen no se puede construir: corre `collectstatic` con los settings de
producción, y esos settings exigen `SECRET_KEY`, `DATABASE_URL` y, con esta
spec, `RABBITMQ_URL`, que no existen durante la construcción.

La corrección pasa **valores ficticios solo a ese paso** (`RUN SECRET_KEY=...
python manage.py collectstatic`). Esas variables existen únicamente durante ese
comando: no quedan guardadas en la imagen ni llegan al contenedor en ejecución,
que recibe las reales desde Railway. `collectstatic` no se conecta a la base ni
al broker, así que los valores ficticios no se usan para nada.

### 5.5 Celery

Se agrega la dependencia `celery` y la configuración mínima:

- `config/celery.py`: crea la aplicación de Celery, lee su configuración de los
  settings y descubre las tareas de cada app.
- `config/__init__.py` importa esa aplicación, como indica la documentación de
  Celery, para que las tareas se registren al arrancar Django.
- Broker: `RABBITMQ_URL`. Sin backend de resultados (§4).
- En `test.py`, las tareas se ejecutan en el mismo proceso
  (`CELERY_TASK_ALWAYS_EAGER`), para que las pruebas no necesiten RabbitMQ.
- Una tarea de diagnóstico en `apps/core/tasks.py`, que solo escribe en el
  registro que el worker la recibió. Sirve para comprobar el despliegue (§8) y
  no contiene lógica de negocio.

Las colas (`documentos`, `notificaciones`, `reportes`), los reintentos y los
flujos reales los define la spec de mensajería del rol D. **El incremento de
Celery lo revisa D**, porque es la base sobre la que construye.

### 5.6 pgvector

Una migración en `core` habilita la extensión con la operación
`CreateExtension("vector")` de Django, sin dependencias nuevas. Va en `core` y
no en `ia` para que la extensión ya exista cuando el rol C cree los modelos con
vectores, y para que el entorno sea reproducible: nadie la habilita a mano.

### 5.7 Pendientes de la spec 001

- `obtener_id_usuario_por_email` busca sin distinguir mayúsculas (`iexact`),
  igual que el login (observación de la revisión de DouGMV/Proyecto-Inmobiliaria#4).
- La cabecera de la spec 001 pasa a "Implementada".

## 6. Frontend en Vercel

**Frontend mínimo:** el proyecto se crea en esta spec con React 19, Vite y
TypeScript en modo estricto, y una sola página que muestra el estado de la API.
El roadmap dice que en la fase 1 basta una página en blanco; esta consulta
`/health/` para probar de punta a punta que el frontend desplegado llega al
backend desplegado y que CORS está bien configurado.

Aunque sea una sola página, **respeta las reglas de `docs/frontend.md` desde el
primer archivo**, porque es la base sobre la que todo el equipo construye:

- La petición pasa por un hook de TanStack Query (`api/core/consultas.ts`) y un
  cliente de Axios (`api/cliente.ts`); nunca un `fetch` en el componente.
- Los tipos se generan desde el esquema OpenAPI con `npm run gen:api`
  (openapi-typescript) y no se escriben a mano.
- ESLint, Prettier y los scripts `lint`, `typecheck`, `build` y `gen:api`, que
  usa la integración continua.

Quedan fuera rutas, login, menú, shadcn/ui y componentes comunes: son la base
del frontend, con su propia spec.

**Configuración en Vercel:**
- Proyecto apuntando a la carpeta `frontend/`
- Comando de compilación `npm run build`, salida en `dist/`
- Variable `VITE_API_URL` con la URL pública de Railway (`.../api/v1`)
- Despliegue automático: cada pull request genera una vista previa, cada fusión
  a `main` actualiza producción

El plan Hobby es gratuito y está restringido a uso personal y no comercial, lo
cual un proyecto académico cumple.

## 7. Integración continua y verificación

Flujo en `.github/workflows/ci.yml`, ejecutado en cada pull request y cada push
a `develop` y a `main`:

1. Levanta PostgreSQL como servicio del flujo
2. Instala dependencias del backend
3. Corre `ruff check` y `ruff format --check`
4. Verifica que no falten migraciones
5. Corre `pytest` con cobertura
6. Instala dependencias del frontend, corre `lint`, `typecheck` y `build`

**Estado al 2026-10-21: GitHub Actions no se ha ejecutado nunca** en este
repositorio, ni con pushes ni con pull requests. El workflow es válido y está
activo, así que el bloqueo está en la cuenta de GitHub; lo resuelve el rol A
revisando la facturación.

**Mientras tanto**, la verificación se hace a mano según
`docs/convenciones.md` §1.1, regla 5. Y como nada ha probado el código con
**Python 3.12**, que es la versión del stack, esta spec corre la suite completa
dentro de un contenedor `python:3.12-slim`.

Sin protección de ramas, un flujo en rojo **no bloquea técnicamente** la
fusión: la regla es del equipo. Un pull request con el flujo en rojo no se
fusiona.

## 8. Criterios de aceptación

**Antes de desplegar (local)**
- [ ] La imagen del `Dockerfile` se construye sin variables de entorno reales
- [ ] El contenedor arranca con settings de producción, aplica las migraciones y
      `/api/v1/health/` responde 200
- [ ] `pytest` pasa completo con Python 3.12, dentro de un contenedor
- [ ] El panel de Django se ve con sus estilos sirviendo desde WhiteNoise
- [ ] Un worker de Celery local se conecta a RabbitMQ y ejecuta la tarea de
      diagnóstico
- [ ] La extensión `vector` queda habilitada después de `migrate`
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan en `frontend/`
- [ ] El frontend local muestra el estado de la API local

**En producción**
- [ ] `https://<proyecto>.up.railway.app/api/v1/health/` responde 200
- [ ] `https://<proyecto>.vercel.app` carga el frontend y muestra el estado de
      la API, sin errores de CORS
- [ ] `/api/docs/` y el panel de Django son accesibles y se ven con estilos
- [ ] Login contra la API desplegada devuelve tokens
- [ ] El worker aparece conectado a RabbitMQ y ejecuta la tarea de diagnóstico
- [ ] La extensión `vector` está habilitada en la base de producción
- [ ] Las migraciones corren automáticamente en cada despliegue
- [ ] `DEBUG` es `False` y un error 500 no muestra trazas al cliente, pero sí
      queda en los registros de Railway
- [ ] Una fusión de `develop` en `main` despliega automáticamente en Railway y
      en Vercel
- [ ] El límite de gasto está configurado en Railway
- [ ] No hay ninguna credencial en el repositorio

**Integración continua**
- [ ] GitHub Actions se ejecuta en cada pull request. *Depende de resolver el
      bloqueo de la cuenta; si no se resuelve, queda documentado y se sigue con
      la verificación manual.*

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Unidad | La tarea de diagnóstico se ejecuta (en modo `ALWAYS_EAGER`) |
| Unidad | La extensión `vector` existe en la base de pruebas después de migrar |
| Contenedor | La imagen se construye y responde `/health/` con settings de producción |
| Contenedor | `pytest` completo con Python 3.12 |
| Humo | El endpoint de salud responde desde fuera de la red del equipo |
| Humo | Login contra la API desplegada devuelve tokens |
| Integración | Una tarea encolada en producción se ejecuta en el worker desplegado |
| Frontend | La página de estado muestra "ok" cuando la API responde y un error claro cuando no |

## 10. Decisiones y alternativas descartadas

Ver la sección 3 para el proveedor. Para la defensa oral conviene poder
explicar:

- Por qué una plataforma administrada y no un servidor propio: el tiempo del
  equipo se invierte en los componentes evaluados, y la portabilidad se
  conserva con contenedores.
- Por qué el frontend va en un proveedor distinto al backend: son artefactos
  distintos (archivos estáticos frente a procesos permanentes) y separarlos
  deja el frontend gratuito, con CDN global.
- Por qué se omite Redis: RabbitMQ ya sirve como broker de Celery y el backend
  de resultados no se necesita todavía. Agregar un servicio que no se usa es
  costo y superficie de fallo sin beneficio.

**WhiteNoise sobre un servicio de archivos aparte.** Las alternativas eran
Nginx delante de gunicorn o un almacenamiento de objetos con CDN. Las dos
agregan un servicio que configurar y pagar para servir unos pocos megas de CSS
y JavaScript del panel. WhiteNoise lo hace desde el mismo proceso y es la
recomendación habitual para Django en contenedores.

**Valores ficticios solo en el paso de `collectstatic`.** Se descartó dar
valores por defecto a `SECRET_KEY` y `DATABASE_URL` en `prod.py`, porque
entonces producción podría arrancar con una clave falsa sin que nadie lo note
(spec 001, §10). También se descartó correr `collectstatic` al arrancar el
contenedor: haría más lento cada despliegue y cada reinicio.

**Frontend mínimo con las reglas completas.** Una página en blanco no probaría
nada. Una página con `fetch` directo sería más rápida de escribir, pero dejaría
la primera pieza del frontend violando `docs/frontend.md`, y lo primero que se
escribe es lo que los demás copian.

**Celery mínimo en esta spec y no en la de mensajería.** El worker es parte de
la infraestructura que se despliega. Si se dejara para la fase 4, el primer
despliegue del worker ocurriría junto con los flujos reales, y un error de
configuración se confundiría con un error del flujo.

**pgvector en `core`.** La extensión es infraestructura de la base, no un
modelo de la app `ia`. Habilitarla antes permite comprobar en este despliegue
que la plantilla de Railway la soporta, en lugar de descubrirlo en la fase 5.

**Sin protección de ramas.** GitHub la ofrece en repositorios privados solo con
el plan Pro. El equipo prefirió reglas internas escritas antes que cambiar de
plan o hacer público el repositorio (`docs/convenciones.md` §1.1).

## 11. Trabajo con agentes de IA

**Sesión 2026-10-21, revisión de la spec antes de implementar (Claude Code).**
El agente revisó el borrador contra el `Dockerfile`, los settings y la
integración continua reales, y encontró cinco cosas que habrían bloqueado el
despliegue: la imagen no se podía construir, los archivos estáticos no se
servían, la plantilla de PostgreSQL podría no traer pgvector, no existía
configuración de Celery para el worker, y Vercel no tenía qué desplegar.
También confirmó que GitHub Actions no se ejecuta por un bloqueo en la cuenta y
no por el workflow. El equipo aceptó las decisiones de las secciones 5 a 7.

**Plan de implementación (un commit por incremento):**

1. Pendientes de la spec 001 (§5.7)
2. Settings de producción para Railway y WhiteNoise (§5.2 y §5.3)
3. Corrección del `Dockerfile`; construir y correr la imagen localmente, y la
   suite completa con Python 3.12 (§5.4 y §7)
4. Configuración mínima de Celery y la tarea de diagnóstico (§5.5). Revisa D.
5. Migración de pgvector (§5.6)
6. Frontend mínimo (§6)
7. Configuración de Railway y Vercel, guiada paso a paso; la hace A en los
   paneles de los proveedores (§5.1 y §6)
8. Primera fusión de `develop` en `main`, verificación de los criterios en
   producción y documentación del despliegue en el README

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.
