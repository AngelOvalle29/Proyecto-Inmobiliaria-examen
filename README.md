# Sistema de Gestión Inmobiliaria

Sistema tipo ERP para una agencia inmobiliaria con operación en Latinoamérica.
Administra el ciclo de vida completo de propiedades: compra a proveedores,
construcción con constructoras, documentación legal, avalúos, cotizaciones,
venta a clientes y arrendamiento, con reportería exportable, agente de
inteligencia artificial y conexión a Power BI.

**Curso:** Programación Comercial
**Institución:** Universidad Mesoamericana, sede Quetzaltenango
**Facultad:** Ingeniería — Ingeniería en Sistemas, Informática y Ciencias de la Computación
**Ciclo:** 2026

---

## Equipo

| Integrante | GitHub | Rol | Responsable de |
|---|---|---|---|
| Douglas Gerardo Morales Velásquez | DouGMV | A | Base, arquitectura y autenticación (`core`, `usuarios`, `catalogo`); despliegue e integración continua; apoyo a los demás |
| Marco André Bolaños Rojas | Lilfacce | B | Flujo comercial (`crm`, `ventas`, `arrendamientos`) |
| Angel Glicerio Ovalle Fernandez | AngelOvalle29 | C | Adquisiciones y agente de IA (`compras`, `construccion`, `ia`) |
| Nathaly Saraí Reyes Cifuentes | NathalyR15 | D | Reportería, Power BI, auditoría y mensajería (`reportes`, `auditoria`) |

Cada quien agrega su nombre en esta tabla. El detalle del reparto está en
`docs/roadmap.md`.

---

## Alcance

El sistema cubre seis dominios de negocio:

- **Catálogo de propiedades.** Propiedades y unidades (apartamentos, locales),
  tipos, estados, amenidades, avalúos, documentos oficiales e historial completo
  de cada propiedad como línea de tiempo de eventos.
- **CRM.** Clientes, agentes de venta, cotizaciones y su seguimiento.
- **Ventas.** Contratos de venta, planes de pago y cuotas.
- **Arrendamientos.** Contratos de renta, cobros periódicos y ocupación.
- **Compras.** Proveedores y contratos de adquisición de propiedades.
- **Construcción.** Constructoras, proyectos, avances de obra y pagos.

Sobre esa base se montan las capas transversales: auditoría, reportería
exportable a Excel y PDF, agente de IA con RAG, mensajería asíncrona y
publicación de vistas analíticas para Power BI.

Detalle en `docs/modelo-datos.md` y `docs/requisitos.md`.

---

## Stack

| Capa | Tecnología |
|---|---|
| API | Python 3.12 · Django 5 · Django REST Framework |
| Base de datos | PostgreSQL 16 (con extensión pgvector) |
| Mensajería | RabbitMQ · Celery |
| Cache | Redis (fuera por ahora; se agrega con su spec si hace falta) |
| Reportes | openpyxl (Excel) · WeasyPrint (PDF) |
| Autenticación | JWT (SimpleJWT) |
| Frontend | React 19 · Vite · TypeScript · TanStack Query y Table · shadcn/ui |
| Infraestructura | Docker · Docker Compose |
| Despliegue | Planes gratuitos: API y worker en Render · PostgreSQL en Neon · RabbitMQ en CloudAMQP · Frontend en Vercel (por ahora, sitio estático en Render) |
| IA y RAG | Gemini Flash (capa gratuita) · pgvector |
| Correo | Gmail SMTP |
| BI | Power BI sobre vistas del esquema `bi` |

---

## Arranque rápido

Requisitos previos: Docker, Docker Compose y Python 3.12.

```bash
git clone https://github.com/DouGMV/Proyecto-Inmobiliaria.git
cd Proyecto-Inmobiliaria

cp .env.example .env            # cambiar SECRET_KEY por una clave aleatoria

docker compose up -d            # PostgreSQL con pgvector y RabbitMQ

cd backend
python -m venv .venv
source .venv/bin/activate       # en Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt

python manage.py migrate        # también crea los 5 roles y la tabla de caché
python manage.py createsuperuser   # pide correo y nombre completo
python manage.py seed_demo      # catálogos de core y datos de demo de cada app
python manage.py runserver
```

**Si ya tienes PostgreSQL instalado en tu máquina**, el puerto 5432 estará
ocupado y `docker compose up -d` fallará. Elige otro puerto en `.env` y úsalo
también en la cadena de conexión:

```bash
POSTGRES_PORT=5434
DATABASE_URL=postgresql://inmobiliaria:inmobiliaria@localhost:5434/inmobiliaria
```

Para generar una `SECRET_KEY` de desarrollo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Calidad, antes de cada commit (desde `backend/`):

```bash
ruff format . && ruff check . && pytest
```

El worker de Celery, en otra terminal y también desde `backend/`:

```bash
celery -A config worker --pool=solo -l info
```

`--pool=solo` es el mismo modo que en producción, y en Windows es obligatorio:
el modo por defecto de Celery no funciona ahí. Para comprobar que el worker
recibe tareas, `python manage.py encolar_diagnostico` y en su terminal debe
aparecer `Worker de Celery operativo`.

El frontend, a partir de la fase 2:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

| Servicio | URL local |
|---|---|
| Frontend | http://localhost:5173/ |
| API | http://localhost:8000/api/v1/ |
| Estado del servicio | http://localhost:8000/api/v1/health/ |
| Documentación de la API | http://localhost:8000/api/docs/ |
| Panel de administración | http://localhost:8000/admin/ |
| Panel de RabbitMQ | http://localhost:15672/ |

---

## Despliegue

Todo corre en planes gratuitos, sin tarjeta. Las razones de cada proveedor y el
detalle técnico están en `specs/002-despliegue.md`.

| Pieza | Dónde | Nota |
|---|---|---|
| API y worker de Celery | Render, servicio web `inmobiliaria-api` (Docker) | Un solo contenedor: Render no tiene workers gratuitos |
| Frontend | Render, sitio estático `inmobiliaria-web` | Temporal, mientras Vercel verifica la cuenta (spec 002, §6.1) |
| PostgreSQL 16 con pgvector | Neon | Conexión directa, `sslmode=require` |
| RabbitMQ | CloudAMQP, plan Little Lemur | URL `amqps://` |

| En producción | URL |
|---|---|
| Frontend | *se completa al verificar el despliegue* |
| API | *se completa al verificar el despliegue* |
| Documentación de la API | `<API>/api/docs/` |
| Panel de administración | `<API>/admin/` |

### Cómo se publica un cambio

1. El cambio llega a `develop` por pull request, como siempre.
2. El integrante A abre un pull request de `develop` a `main`; otro integrante
   lo aprueba y A lo fusiona (`docs/convenciones.md` §1.1, regla 9).
3. Render despliega solo los dos servicios desde `main`. La configuración está
   versionada en `render.yaml` (un *Blueprint*). Si se agrega un servicio
   nuevo a ese archivo y no aparece, en Render: **Blueprints → el proyecto →
   Sync**.
4. Si el contenedor nuevo no arranca, Render conserva la versión anterior en
   línea. Para volver atrás a propósito: **el servicio → Events → Rollback** en
   un despliegue anterior, y luego revertir el cambio en `main` con un pull
   request.

### Qué hace el contenedor al arrancar

`backend/scripts/iniciar.sh`, en este orden:

1. Aplica las migraciones.
2. Crea el administrador inicial con las variables `DJANGO_SUPERUSER_*`, solo si
   todavía no hay ningún superusuario.
3. Si `CARGAR_DATOS_DEMO` es `true`, corre `seed_demo`, que no duplica nada.
4. Levanta el worker de Celery en segundo plano; si se cae, se vuelve a levantar
   a los 5 segundos.
5. Encola la tarea de diagnóstico del worker.
6. Arranca gunicorn, que atiende la API.

### Variables de entorno

Se cargan en el panel de Render, **nunca en el repositorio**. La lista completa
con su explicación está al final de `.env.example`. Las secretas son
`SECRET_KEY` (al menos 50 caracteres, o el contenedor no arranca),
`DATABASE_URL`, `RABBITMQ_URL` y `DJANGO_SUPERUSER_PASSWORD`.
`CORS_ALLOWED_ORIGINS` es la URL del frontend, sin barra final.

El frontend solo necesita `VITE_API_URL`, la URL de la API terminada en
`/api/v1`. No es secreta: queda visible en el código que descarga el navegador.

### Lo que hay que saber del plan gratuito

- **La API se duerme** tras 15 minutos sin tráfico, y la primera petición
  después tarda alrededor de un minuto. El frontend lo avisa mientras espera.
  **Antes de una revisión o de la defensa, abrir el sistema un par de minutos
  antes.** No se mantiene despierta con un monitor externo: Neon agotaría sus
  horas de cómputo del mes (spec 002, §5.8).
- **No hay terminal.** Por eso el administrador y los datos de demostración los
  crea el script de arranque.
- **No hay disco persistente.** Lo que se escriba en el contenedor se pierde al
  reiniciar.

### Cómo revisar que todo funciona

| Qué | Cómo |
|---|---|
| API y base de datos | `<API>/api/v1/health/` responde `{"estado": "ok", "base_datos": "ok"}` (503 si la base no responde) |
| Worker y RabbitMQ | En Render, **Logs** del servicio de la API: tras cada arranque aparece `Worker de Celery operativo: tarea de diagnóstico recibida.` |
| Frontend y CORS | La página del frontend muestra el estado de la API sin errores en la consola del navegador |

### Problemas conocidos

| Síntoma | Causa y solución |
|---|---|
| `lstat ... backend/backend: no such file or directory` al construir | Con `rootDir`, Render resuelve `dockerfilePath` y `dockerContext` desde `backend/`, no desde la raíz. Deben ser `./Dockerfile` y `.` (spec 002, §5.1) |
| El contenedor sale con código 1 al arrancar | Falta una variable obligatoria, `SECRET_KEY` es corta o `DJANGO_SUPERUSER_PASSWORD` no pasa los validadores. El motivo está en los Logs |
| El frontend muestra un error de red al llamar a la API | `CORS_ALLOWED_ORIGINS` no tiene la URL exacta del frontend (con `https://` y sin barra final) |
| La primera carga tarda un minuto | Es la siesta del plan gratuito, no un error |

---

## Documentación

| Archivo | Contenido |
|---|---|
| `docs/requisitos.md` | Requisitos del curso y rúbrica de evaluación |
| `docs/arquitectura.md` | Capas, apps, reglas de dependencia y patrones |
| `docs/modelo-datos.md` | Entidades, relaciones y reglas de negocio |
| `docs/frontend.md` | Stack, estructura y reglas del frontend |
| `docs/reportes.md` | Catálogo de los 15 reportes y modelo para Power BI |
| `docs/convenciones.md` | Flujo de Git, ramas, commits y pull requests |
| `docs/roadmap.md` | Fases del proyecto y reparto de trabajo |
| `specs/` | Especificaciones funcionales, una por funcionalidad |
| `CLAUDE.md` / `AGENTS.md` | Reglas para agentes de IA |

---

## Cómo se trabaja aquí

Este proyecto se desarrolla **guiado por especificaciones**: ninguna
funcionalidad se implementa sin una spec aprobada en `specs/`. El flujo de
ramas, commits y pull requests está descrito en `docs/convenciones.md` y es de
cumplimiento obligatorio, porque el historial de Git forma parte de la
evaluación del curso.
