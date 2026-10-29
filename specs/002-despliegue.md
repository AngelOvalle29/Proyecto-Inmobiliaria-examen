# 002 · Despliegue en producción e integración continua

| Campo | Valor |
|---|---|
| **Número** | 002 |
| **Estado** | Aprobada, en implementación. **El cambio de proveedor (§3) requiere nueva revisión** |
| **Autor** | Equipo |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce) |
| **Fecha** | 2026-10-08 (actualizada el 2026-10-21) |
| **Apps afectadas** | `config`, `core` (migración de pgvector, tarea de diagnóstico), `usuarios` (pendiente de la spec 001, administrador inicial), `frontend/`, infraestructura |
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
- Backend desplegado **sin costo**: API y worker de Celery en Render, PostgreSQL
  con pgvector en Neon y RabbitMQ en CloudAMQP (§3 a §5)
- Frontend mínimo desplegado en Vercel: una página que consulta el estado de la
  API (§6)
- Settings de producción para correr detrás del proxy de Render (§5.2)
- Archivos estáticos servidos con WhiteNoise (§5.3)
- Corrección del `Dockerfile` y un script de arranque que levanta la API y el
  worker en el mismo contenedor (§5.4)
- Configuración mínima de Celery y un worker conectado a RabbitMQ (§5.5)
- Migración que habilita la extensión `vector` (§5.6)
- Lo que obliga el plan gratuito: administrador inicial y datos de demostración
  cargados al arrancar, porque no hay acceso a una terminal (§5.8)
- La configuración de Render versionada en `render.yaml` (§5.1)
- Verificación de todo el backend con Python 3.12 dentro de un contenedor
  (§7), porque GitHub Actions no se está ejecutando
- Despliegue automático al fusionar `develop` en `main`
- Cierre de los pendientes de la spec 001 (§5.7)

**No incluye:**
- Flujos reales de mensajería (notificaciones, ingesta de documentos): fase 4,
  rol D. Aquí solo se deja Celery funcionando.
- Base completa del frontend (rutas, login, menú, componentes): spec propia,
  rol A. Aquí solo se crea el proyecto con las reglas de `docs/frontend.md`.
- Almacenamiento de documentos oficiales: decisión abierta de `CLAUDE.md` §9.
  El plan gratuito de Render no tiene disco persistente, así que tendrá que ser
  un almacenamiento externo; lo decide la spec de catálogo.
- Protección de ramas en GitHub: no está disponible en el plan gratuito y el
  equipo decidió usar reglas internas (`docs/convenciones.md` §1.1).
- Dominio propio (se usan los subdominios de Render y Vercel)
- Monitoreo avanzado ni alertas
- Respaldos fuera de los automáticos de Neon

## 3. Decisión de proveedor

**Decisión vigente (2026-10-21): solo servicios con plan gratuito.**

| Pieza | Proveedor | Plan gratuito |
|---|---|---|
| API y worker | **Render** | Un servicio web; se duerme tras 15 minutos sin tráfico y tarda alrededor de un minuto en despertar; 750 horas al mes |
| PostgreSQL con pgvector | **Neon** | Soporta pgvector; se duerme a los 5 minutos y despierta en menos de un segundo; 100 horas de cómputo al mes y almacenamiento pequeño |
| RabbitMQ | **CloudAMQP** (plan *Little Lemur*) | 1 millón de mensajes al mes y 20 conexiones |
| Frontend | **Vercel** (plan Hobby) | Sin cambios |

**Por qué se cambió.** La primera versión de esta spec eligió Railway (abajo),
que cuesta entre $15 y $20 al mes. El equipo prefirió no pagar. Se evaluaron
tres rutas gratuitas:

| Opción | A cambio de | Decisión |
|---|---|---|
| **Render + Neon + CloudAMQP** | La API se duerme; la API y el worker comparten un contenedor (§5.4) | **Elegida** |
| Máquina virtual de Oracle Cloud | Administrar un servidor Linux, HTTPS y despliegues por SSH; Oracle apaga las máquinas que considera inactivas y en 2026 recortó su plan gratuito a la mitad sin anunciarlo | Descartada |
| Créditos del Student Developer Pack (DigitalOcean, Azure) | Activar el Student Pack y, en una máquina virtual, administrarla | Descartada por ahora |

**Render + Neon + CloudAMQP gana** porque es la única ruta gratuita sin un
servidor que administrar, y quedan pocas semanas. La siesta de la API se
resuelve abriendo el sistema un par de minutos antes de una revisión o de la
defensa (§5.8). Una espera de un minuto es un riesgo menor que encontrar la
máquina apagada.

**Lo que se descartó dentro de Render:** su PostgreSQL gratuito se borra a los
30 días, y los workers no tienen plan gratuito. Por eso la base va en Neon y el
worker comparte el contenedor de la API.

**La decisión es reversible.** Todo sigue en contenedores. Si el equipo decide
pagar, el `Dockerfile` corre igual en Railway o en un plan de pago de Render, y
la API y el worker se separan cambiando solo el comando de arranque.

### Decisión anterior: Railway (2026-10-08, reemplazada)

Se comparó Railway + Vercel (~$15–20 al mes, 1–2 horas de montaje), Hetzner con
Coolify (~€11), Hetzner con Docker Compose (~€6), Render de pago (~$43) y la
capa gratuita de Oracle. Railway ganaba por ahorrar tiempo de administración. Se
descartó Render de pago por su precio y el plan gratuito de Render porque, solo,
no alcanza: es la limitación que esta versión resuelve combinándolo con Neon y
CloudAMQP.

## 4. Arquitectura de despliegue

```
                  ┌──────────────┐
   Navegador ────▶│    Vercel    │  React estático, HTTPS, CDN
                  └──────┬───────┘
                         │ llamadas a la API
                         ▼
           ┌─────────────────────────────┐
           │  Render (servicio web)      │
           │  un contenedor:             │
           │   ├─ gunicorn (Django)      │
           │   └─ worker de Celery       │
           └──────┬───────────────┬──────┘
                  │               │
                  ▼               ▼
     ┌────────────────────┐  ┌──────────────┐
     │ Neon               │  │ CloudAMQP    │
     │ PostgreSQL+pgvector│  │ RabbitMQ     │
     └────────────────────┘  └──────────────┘
```

Los tres servicios del backend se crean en la misma región (este de Estados
Unidos), para que cada consulta y cada mensaje no crucen el continente.

**Redis sigue fuera**: Celery usa RabbitMQ como broker y no hay backend de
resultados.

## 5. Backend

### 5.1 Servicios y configuración

**Render (servicio web `inmobiliaria-api`):**
- Construye el `Dockerfile` de `backend/` y arranca con el script de §5.4.
- Plan gratuito, región este de Estados Unidos, despliegue automático desde
  `main`.
- **Ruta de salud:** `/api/v1/health/`. Render la llama con el host
  `<servicio>.onrender.com`, que expone en la variable
  `RENDER_EXTERNAL_HOSTNAME`; `prod.py` lo agrega a `ALLOWED_HOSTS` (§5.2). Si
  la ruta no responde en 15 minutos al desplegar, Render cancela el despliegue
  y sigue sirviendo la versión anterior.
- **La configuración vive en `render.yaml`** en la raíz del repositorio
  (*Blueprint*): servicio, plan, región, ruta de salud y nombres de las
  variables. Los valores secretos no van ahí: se marcan para cargarlos en el
  panel. Así la configuración se revisa en un pull request como el código.
- *Corregido en el primer despliegue:* con `rootDir: backend`, Render resuelve
  `dockerfilePath` y `dockerContext` **relativas a `backend/`**, aunque su
  documentación dice que son relativas a la raíz. Con `./backend` buscaba
  `backend/backend` y la construcción fallaba; las rutas correctas son
  `./Dockerfile` y `.`.

**Neon:** un proyecto con su base. `DATABASE_URL` usa la cadena de **conexión
directa** (no la del *pooler*) con `sslmode=require`.

**CloudAMQP:** una instancia *Little Lemur*. `RABBITMQ_URL` es su URL `amqps://`.

**Variables del servicio web:**

| Variable | Valor |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | Clave aleatoria generada para producción |
| `DATABASE_URL` | Cadena de conexión directa de Neon |
| `RABBITMQ_URL` | URL de CloudAMQP |
| `ALLOWED_HOSTS` | Vacía salvo que se agregue un dominio propio (`prod.py` agrega `RENDER_EXTERNAL_HOSTNAME`) |
| `CORS_ALLOWED_ORIGINS` | `https://proyecto-inmobiliaria-chi.vercel.app`, sin barra final |
| `NUM_PROXIES` | `3`: Cloudflare, el borde de Render y un proxy interno. Medido en producción (§8) |
| `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_NOMBRE_COMPLETO`, `DJANGO_SUPERUSER_PASSWORD` | Datos del administrador inicial (§5.8). La contraseña la elige A y solo existe en el panel de Render |
| `CARGAR_DATOS_DEMO` | `true` para que el arranque corra `seed_demo` (§5.8) |

**Ningún proveedor requiere tarjeta en su plan gratuito**, así que no hay
límite de gasto que configurar: si se agota una cuota, el servicio se detiene
en lugar de cobrar.

### 5.2 Settings de producción

`config/settings/prod.py` agrega, además de lo que ya tiene:

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`: Render
  termina HTTPS en su proxy y le pasa la petición a Django por HTTP. Sin esto
  Django cree que la conexión no es segura, y las cookies seguras y el CSRF
  del panel fallan.
- `ALLOWED_HOSTS` toma la lista de la variable de entorno y le agrega
  `RENDER_EXTERNAL_HOSTNAME` cuando existe (§5.1).
- `RABBITMQ_URL` obligatoria, sin valor por defecto, como `SECRET_KEY`.
- `SECRET_KEY` de al menos 50 caracteres, o producción no arranca. *Agregado
  en el incremento 3:* la clave también firma los tokens JWT, y con menos de 32
  bytes la firma es débil. Lo descubrió la suite al correr con una clave de
  prueba corta, la misma que usaba `ci.yml`.
- Conexiones a la base reutilizables (`CONN_MAX_AGE` con verificación de
  salud): abrir una conexión nueva a Neon en cada petición agrega latencia.
- Registro de errores en la salida estándar (`LOGGING`). Con `DEBUG = False`,
  Django no imprime las trazas de los errores 500 en la consola; sin esto, un
  error en producción no deja rastro en los registros de Render.

No se activa `SECURE_SSL_REDIRECT`, porque Render ya redirige a HTTPS en su
proxy. Tampoco se activa HSTS por ahora, porque un error de configuración de
HSTS no se puede deshacer desde el servidor.

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
- Los archivos se recopilan al construir la imagen y viajan dentro de ella, así
  que no dependen del disco del servicio, que en el plan gratuito se borra.

### 5.4 `Dockerfile` y script de arranque

**Construcción.** Hoy la imagen no se puede construir: corre `collectstatic` con
los settings de producción, y esos settings exigen `SECRET_KEY`, `DATABASE_URL`
y `RABBITMQ_URL`, que no existen durante la construcción. La corrección pasa
**valores ficticios solo a ese paso** (`RUN SECRET_KEY=... python manage.py
collectstatic`). Esas variables existen únicamente durante ese comando: no
quedan guardadas en la imagen ni llegan al contenedor en ejecución.
`collectstatic` no se conecta a la base ni al broker.

**Se agrega `backend/.dockerignore`.** Sin él, `COPY . .` metía en la imagen el
entorno virtual local (en Windows, binarios que no corren en Linux), los cachés
y el `.env` con secretos de desarrollo. *Encontrado en el incremento 3.*

**Se quita el `HEALTHCHECK` del `Dockerfile`.** Llamaba a `localhost`, que no
está en `ALLOWED_HOSTS` con settings de producción, y Render no lo usa: tiene su
propia ruta de salud (§5.1).

**Script de arranque (`backend/scripts/iniciar.sh`)**, el comando del contenedor:

1. `migrate`.
2. Crea el administrador inicial si no existe (§5.8).
3. Si `CARGAR_DATOS_DEMO` es `true`, corre `seed_demo`, que es idempotente.
4. Arranca el worker de Celery en segundo plano, con el pool `solo`: un solo
   proceso que ejecuta una tarea a la vez. **Corre dentro de un ciclo que lo
   vuelve a levantar a los 5 segundos si se cae**, y deja un aviso en el
   registro cada vez (observación de la revisión del rol B; agregado en el
   incremento 4).
5. Encola la tarea de diagnóstico (`encolar_diagnostico`). Si RabbitMQ no
   responde, avisa y sigue: la API no debe quedar caída por el diagnóstico.
6. Arranca gunicorn con **1 proceso**, en primer plano, con `exec` para que
   reciba las señales de apagado de Render.

Los pasos 2 y 3 llegan en el incremento 5, junto con el comando
`asegurar_administrador`.

**La API y el worker comparten el contenedor** porque Render no tiene workers
gratuitos. El plan gratuito tiene 512 MB de memoria: un proceso de gunicorn y un
worker sin procesos hijos caben con holgura; más procesos no.

*Consecuencias, que se aceptan y conviene saber explicar:*
- Si la API se duerme, el worker también. Las tareas no se pierden: esperan en
  RabbitMQ y se ejecutan cuando el contenedor despierta. Como los flujos de la
  fase 4 se disparan por peticiones a la API, el contenedor ya está despierto
  cuando se encolan.
- Si el worker se cae, el ciclo del script lo vuelve a levantar y la API sigue
  respondiendo mientras tanto. El aviso queda en los registros de Render.
- Al apagar el contenedor, una tarea que se estaba ejecutando puede
  interrumpirse. Para una demostración es aceptable; con un plan de pago se
  separa el worker en su propio servicio.

### 5.5 Celery

Se agrega la dependencia `celery` y la configuración mínima:

- `config/celery.py`: crea la aplicación de Celery, lee su configuración de los
  settings y descubre las tareas de cada app.
- `config/__init__.py` importa esa aplicación, como indica la documentación de
  Celery, para que las tareas se registren al arrancar Django.
- Broker: `RABBITMQ_URL`. Sin backend de resultados (§4).
- **Ajustes para la cuota de CloudAMQP:** un pool de conexiones mínimo y el
  worker sin eventos ni mensajes de coordinación entre workers (no hay otro
  worker con quien coordinarse). Cada uno de esos mensajes cuenta contra el
  millón mensual.
- En `test.py`, las tareas se ejecutan en el mismo proceso
  (`CELERY_TASK_ALWAYS_EAGER`), para que las pruebas no necesiten RabbitMQ.
- Una tarea de diagnóstico en `apps/core/tasks.py`, que solo escribe en el
  registro que el worker la recibió. Sirve para comprobar el despliegue (§8) y
  no contiene lógica de negocio. El script de arranque la encola en cada
  despliegue con el comando `encolar_diagnostico`, porque en Render no hay
  terminal para encolarla a mano.
- `prod.py` rechaza una `RABBITMQ_URL` vacía, no solo ausente: es como queda
  si en el panel de Render se crea la variable y se olvida su valor.

Las colas (`documentos`, `notificaciones`, `reportes`), los reintentos y los
flujos reales los define la spec de mensajería del rol D. **El incremento de
Celery lo revisa D**, porque es la base sobre la que construye.

### 5.6 pgvector

Una migración en `core` habilita la extensión con la operación
`CreateExtension("vector")` de Django, sin dependencias nuevas. Va en `core` y
no en `ia` para que la extensión ya exista cuando el rol C cree los modelos con
vectores, y para comprobar en este despliegue que Neon la soporta.

### 5.7 Pendientes de la spec 001 (hechos en el incremento 1)

- `obtener_id_usuario_por_email` busca sin distinguir mayúsculas (`iexact`),
  igual que el login (observación de la revisión de DouGMV/Proyecto-Inmobiliaria#4).
- La cabecera de la spec 001 pasa a "Implementada".

### 5.8 Lo que obliga el plan gratuito

**Sin terminal.** El plan gratuito de Render no da acceso a una terminal, así que
no se puede correr `createsuperuser` ni `seed_demo` a mano:

- **Administrador inicial:** un comando de `usuarios`
  (`asegurar_administrador`) lo crea con las variables `DJANGO_SUPERUSER_*` si
  todavía no existe ningún superusuario, y no hace nada si ya existe. Lo llama el
  script de arranque. Si las variables no están definidas, no crea nada.
  La lógica vive en el servicio `asegurar_administrador_inicial`: valida la
  contraseña con los mismos validadores del panel (si no los cumple, el
  contenedor no arranca y Render conserva la versión anterior) y audita la
  creación como `CREAR`, con usuario nulo porque la hace el sistema.
- **Datos de demostración:** el script corre `seed_demo` cuando
  `CARGAR_DATOS_DEMO` es `true`. Como es idempotente (spec 001), correrlo en cada
  arranque no duplica nada.

**Sin disco persistente.** Los archivos que el sistema escriba en el disco del
contenedor se pierden al reiniciar. Hoy no se escribe ninguno; los documentos
oficiales irán en un almacenamiento externo (§2).

**La siesta.** La primera petición después de 15 minutos sin tráfico tarda
alrededor de un minuto. Para una revisión o la defensa, se abre el sistema un
par de minutos antes. **No se mantiene despierta todo el tiempo con un
monitor externo**: cada llamada a `/health/` consulta la base, así que Neon
tampoco dormiría y agotaría sus 100 horas de cómputo antes de terminar el mes.
Un monitor se puede encender solo en las semanas de evaluación.

## 6. Frontend en Vercel

**Frontend mínimo:** el proyecto se crea en esta spec con React 19, Vite y
TypeScript en modo estricto, y una sola página que muestra el estado de la API.
Prueba de punta a punta que el frontend desplegado llega al backend desplegado
y que CORS está bien configurado.

Aunque sea una sola página, **respeta las reglas de `docs/frontend.md` desde el
primer archivo**, porque es la base sobre la que todo el equipo construye:

- La petición pasa por un hook de TanStack Query (`api/core/consultas.ts`) y un
  cliente de Axios (`api/cliente.ts`); nunca un `fetch` en el componente.
- Los tipos se generan desde el esquema OpenAPI con `npm run gen:api`
  (openapi-typescript) y no se escriben a mano.
- oxlint, Prettier y los scripts `lint`, `typecheck`, `build` y `gen:api`, que
  usa la integración continua.
- Mientras la API despierta, la página dice que el servidor está despertando,
  en lugar de parecer rota.

Quedan fuera rutas, login, menú, shadcn/ui y componentes comunes: son la base
del frontend, con su propia spec.

**Configuración en Vercel:**
- Proyecto apuntando a la carpeta `frontend/`
- Comando de compilación `npm run build`, salida en `dist/`
- Variable `VITE_API_URL` con la URL pública de Render (`.../api/v1`)
- Despliegue automático: cada pull request genera una vista previa, cada fusión
  a `main` actualiza producción

El plan Hobby es gratuito y está restringido a uso personal y no comercial, lo
cual un proyecto académico cumple.

### 6.1 Mientras tanto: sitio estático en Render

*Agregado el 2026-10-28.* Al crear la cuenta, Vercel la marcó para una
verificación manual ("Your account requires further verification"), que puede
tardar días. Mientras se resuelve, el frontend se publica como **sitio
estático gratuito de Render**, definido en el mismo `render.yaml`
(`inmobiliaria-web`):

- Se construye con `cd frontend && npm ci && npm run build` y publica
  `./frontend/dist`. **No usa `rootDir`**: con `rootDir`, Render resolvió las
  rutas de la API relativas a `backend/` aunque su documentación dice que son
  relativas a la raíz (§5.1). Escribiendo la ruta completa desde la raíz, la
  configuración es correcta con cualquiera de las dos reglas.
- `NODE_VERSION=24`, porque Vite 8 necesita Node 20.19 o superior.
- `VITE_API_URL` se carga en el panel, porque depende del nombre que Render le
  dio a la API.
- Los sitios estáticos de Render **no se duermen**: solo la API lo hace.
- La regla de reescritura de `/*` a `/index.html`, que necesitará el enrutador
  de React, se agrega con la base del frontend (#15). Hoy hay una sola página.

Cuando Vercel habilite la cuenta, se decide si volver a Vercel o quedarse en
Render. Mientras tanto, `CORS_ALLOWED_ORIGINS` apunta al sitio estático.

**Cerrado el 2026-10-29: el frontend volvió a Vercel**, como estaba decidido.
Vercel habilitó la cuenta, y el sitio estático nunca llegó a crearse en Render:
se quitó de `render.yaml` antes de que la configuración llegara a `main`.
Vercel además da una vista previa por pull request, que Render no da. Lo que se
aprendió al configurarlo:

- **Rama de producción:** Vercel toma la rama por defecto del repositorio, que
  es `develop`. Se cambia a `main` en *Settings → Git → Production Branch*, para
  que producción solo publique lo que pasó por el PR de `develop` a `main`.
- **`VITE_API_URL` como tipo *Config*, no *Secret*:** Vercel no acepta como
  secreta una variable con el prefijo `VITE_`, porque de todos modos queda
  visible en el código que descarga el navegador. Debe terminar en `/api/v1`.
- **Las vistas previas no llegan a la API:** cada una tiene su propia URL, que
  no está en `CORS_ALLOWED_ORIGINS`. Sirven para revisar cómo se ven las
  pantallas.

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
activo, así que el bloqueo está en la cuenta de GitHub; lo revisa el rol A.

**Mientras tanto**, la verificación se hace a mano según
`docs/convenciones.md` §1.1, regla 5. Y como nada ha probado el código con
**Python 3.12**, que es la versión del stack, esta spec corre la suite completa
dentro de un contenedor `python:3.12-slim`.

Sin protección de ramas, un flujo en rojo **no bloquea técnicamente** la
fusión: la regla es del equipo. Un pull request con el flujo en rojo no se
fusiona.

## 8. Criterios de aceptación

**Antes de desplegar (local)**
- [x] La imagen del `Dockerfile` se construye sin variables de entorno reales
- [x] El contenedor arranca con settings de producción: aplica las migraciones,
      crea el administrador inicial, carga los datos de demostración, levanta el
      worker y `/api/v1/health/` responde 200
- [x] Arrancar el contenedor dos veces no duplica el administrador ni los datos
- [x] `pytest` pasa completo con Python 3.12, dentro de un contenedor
- [x] El panel de Django se ve con sus estilos sirviendo desde WhiteNoise
- [x] El worker del contenedor se conecta a RabbitMQ y ejecuta la tarea de
      diagnóstico
- [x] La extensión `vector` queda habilitada después de `migrate`
- [x] `npm run lint`, `npm run typecheck` y `npm run build` pasan en `frontend/`
- [x] El frontend local muestra el estado de la API local

**En producción**
- [x] `https://<servicio>.onrender.com/api/v1/health/` responde 200
- [x] El servicio pasa la verificación de salud de Render en cada despliegue
- [x] `https://<proyecto>.vercel.app` carga el frontend y muestra el estado de
      la API, sin errores de CORS
- [x] Con la API dormida, el frontend avisa que el servidor está despertando y
      después muestra el estado
- [x] `/api/docs/` y el panel de Django son accesibles y se ven con estilos
- [x] El administrador inicial puede entrar al panel y hacer login en la API
- [x] El worker ejecuta la tarea de diagnóstico encolada desde producción
- [x] La extensión `vector` está habilitada en la base de Neon (0.8.0)
- [x] La IP que registra la bitácora en un login de producción es la IP pública
      real de quien inició sesión (confirmado con `NUM_PROXIES=3`)
- [x] Las migraciones corren automáticamente en cada despliegue
- [ ] `DEBUG` es `False` y un error 500 no muestra trazas al cliente, pero sí
      queda en los registros de Render. *Comprobado a medias el 2026-10-29:*
      una ruta inexistente responde la página 404 genérica, sin la lista de
      rutas, así que `DEBUG` es `False`. El error 500 queda por probar: hoy
      ningún endpoint falla a propósito
- [ ] Una fusión de `develop` en `main` despliega automáticamente en Render y
      en Vercel
- [x] Todos los servicios están en su plan gratuito
- [x] No hay ninguna credencial en el repositorio

**Integración continua**
- [ ] GitHub Actions se ejecuta en cada pull request. *Depende de resolver el
      bloqueo de la cuenta; si no se resuelve, queda documentado y se sigue con
      la verificación manual.*

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Unidad | La tarea de diagnóstico se ejecuta (en modo `ALWAYS_EAGER`) |
| Unidad | La extensión `vector` existe en la base de pruebas después de migrar |
| Unidad | `asegurar_administrador` crea el superusuario con rol `ADMINISTRADOR` una sola vez, y no hace nada sin variables |
| Contenedor | La imagen se construye y el arranque completo deja `/health/` en 200 con settings de producción |
| Contenedor | `pytest` completo con Python 3.12 |
| Humo | El endpoint de salud responde desde fuera de la red del equipo |
| Humo | Login contra la API desplegada devuelve tokens |
| Integración | Una tarea encolada en producción se ejecuta en el worker desplegado |
| Frontend | La página de estado muestra "ok", "despertando" o un error claro según responda la API |

## 10. Decisiones y alternativas descartadas

Ver la sección 3 para el proveedor. Para la defensa oral conviene poder
explicar:

- **Por qué servicios administrados gratuitos y no un servidor propio:** el
  tiempo del equipo se invierte en los componentes evaluados, y la portabilidad
  se conserva con contenedores.
- **Por qué el frontend va en un proveedor distinto al backend:** son artefactos
  distintos (archivos estáticos frente a procesos permanentes) y separarlos
  deja el frontend gratuito, con CDN global.
- **Por qué se omite Redis:** RabbitMQ ya sirve como broker de Celery y el
  backend de resultados no se necesita todavía.

**API y worker en el mismo contenedor.** Es la única forma de tener worker sin
pagar en Render. Se descartó un servicio de workers en otro proveedor gratuito:
agregaría otra cuenta, otro despliegue y otra forma de fallar. Se descartó
también no tener worker en producción: la mensajería vale 2 puntos y debe
funcionar desplegada. Las consecuencias están en §5.4.

**Pool `solo` y 1 proceso de gunicorn.** Con 512 MB, cada proceso extra de
Django ocupa una porción grande de la memoria. Para el tráfico de una
demostración, un proceso de cada uno es suficiente.

**Neon en lugar del PostgreSQL gratuito de Render.** El de Render se borra a los
30 días, con sus datos. Neon soporta pgvector, no expira y se duerme solo.

**No mantener la API despierta todo el tiempo.** Sería posible con un monitor
externo, pero mantendría despierta también a Neon y agotaría su cuota mensual
(§5.8).

**Administrador y datos de demostración en el arranque.** Sin terminal no hay
otra forma de crearlos. Se descartó una migración de datos para el
administrador: dejaría una contraseña en el historial de migraciones o
dependería de variables de entorno durante `migrate`, que es más difícil de
explicar.

**`render.yaml` en el repositorio.** La configuración del servicio queda
versionada y se revisa en un pull request, en lugar de vivir solo en un panel
web donde nadie más la ve.

**WhiteNoise sobre un servicio de archivos aparte.** Nginx o un almacenamiento
de objetos con CDN agregan un servicio que configurar para servir unos pocos
megas de CSS y JavaScript del panel. WhiteNoise lo hace desde el mismo proceso.

**Valores ficticios solo en el paso de `collectstatic`.** Se descartó dar
valores por defecto a los secretos en `prod.py`, porque entonces producción
podría arrancar con una clave falsa sin que nadie lo note (spec 001, §10).

**Frontend mínimo con las reglas completas.** Una página en blanco no probaría
nada. Una página con `fetch` directo dejaría la primera pieza del frontend
violando `docs/frontend.md`, y lo primero que se escribe es lo que los demás
copian.

**Celery mínimo en esta spec y no en la de mensajería.** El worker es parte de
la infraestructura que se despliega. Si se dejara para la fase 4, un error de
configuración se confundiría con un error del flujo.

**pgvector en `core`.** La extensión es infraestructura de la base, no un
modelo de `ia`. Habilitarla ahora comprueba que Neon la soporta.

**Sin protección de ramas.** GitHub la ofrece en repositorios privados solo con
el plan Pro. El equipo prefirió reglas internas escritas
(`docs/convenciones.md` §1.1).

## 11. Trabajo con agentes de IA

**Sesión 2026-10-21, revisión de la spec antes de implementar (Claude Code).**
El agente revisó el borrador contra el `Dockerfile`, los settings y la
integración continua reales, y encontró cinco cosas que habrían bloqueado el
despliegue: la imagen no se podía construir, los archivos estáticos no se
servían, la base podría no traer pgvector, no existía configuración de Celery
para el worker, y Vercel no tenía qué desplegar. También confirmó que GitHub
Actions no se ejecuta por un bloqueo en la cuenta y no por el workflow.

**Revisión de la spec (rol B, 2026-10-21).** Marco aprobó la versión con
Railway con tres observaciones: `ALLOWED_HOSTS` bloqueaba la verificación de
salud, el `worker` heredaba un `HEALTHCHECK` que no podía pasar y `NUM_PROXIES`
debía comprobarse en producción. Las tres siguen resueltas en esta versión
(§5.1, §5.4 y §8).

**Cambio de proveedor (2026-10-21).** El equipo decidió no pagar Railway. El
agente comparó las capas gratuitas vigentes (Render, Neon, CloudAMQP, Koyeb,
Oracle, Google Cloud y los créditos del Student Pack) y el integrante A eligió
Render + Neon + CloudAMQP. Al verificar la documentación de Render aparecieron
tres restricciones que cambian el diseño: el host de la verificación de salud,
la falta de terminal y la falta de disco persistente (§5.1 y §5.8). **Este
cambio necesita una nueva revisión de otro integrante** antes de los
incrementos que dependen del proveedor (4, 7 y 8).

**Plan de implementación (un commit por incremento):**

1. ✅ Pendientes de la spec 001 (§5.7)
2. ✅ Settings de producción y WhiteNoise (§5.2 y §5.3)
3. ✅ Corrección del `Dockerfile`; construir la imagen localmente y correr la
   suite completa con Python 3.12 (§5.4 y §7)
4. ✅ Configuración mínima de Celery, la tarea de diagnóstico y el script de
   arranque con API y worker juntos (§5.4 y §5.5). Revisa D.
5. ✅ Migración de pgvector (§5.6) y comando `asegurar_administrador` (§5.8)
6. ✅ Frontend mínimo (§6)
7. `render.yaml` y la creación de las cuentas y servicios en Render, Neon,
   CloudAMQP y Vercel, guiada paso a paso; la hace A en los paneles (§5.1)
8. Primera fusión de `develop` en `main`, verificación de los criterios en
   producción y documentación del despliegue en el README

**Sesión 2026-10-29, verificación en producción (Claude Code, rol A).** A hizo
las pruebas que necesitan sus credenciales; el agente revisó desde el
navegador el frontend, la documentación y los estilos del panel. Dos hallazgos:

- **`NUM_PROXIES` no era 1.** Con 1, la bitácora registraba una IP interna de
  Render (`10.x`), y el límite de intentos de login habría contado a todos los
  usuarios como uno solo. Con 2 registraba una IP de Cloudflare. Con **3**
  coincide con la IP pública real. Se subió de uno en uno a propósito: un
  valor mayor que el real haría tomar el primer valor de `X-Forwarded-For`, que
  cualquier cliente puede inventar.
- **Guardar una variable en el panel de Render vuelve a desplegar desde
  `main`.** Como `main` todavía tenía las rutas viejas del `Dockerfile` (§5.1),
  el despliegue falló. Se corrigieron las rutas en el panel, con los mismos
  valores de DouGMV/Proyecto-Inmobiliaria#30, hasta que ese cambio llegue a
  `main`.

Por completar durante la implementación: qué se generó con el agente, qué se
corrigió a mano y qué se descartó en cada incremento.
