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
| *por agregar* | AngelOvalle29 | C | Adquisiciones y agente de IA (`compras`, `construccion`, `ia`) |
| *por agregar* | NathalyR15 | D | Reportería, Power BI, auditoría y mensajería (`reportes`, `auditoria`) |

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
| Despliegue | Backend en Railway · Frontend en Vercel |
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
python manage.py seed_demo      # países, ciudades, monedas y tipos de cambio
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

El worker de Celery se configura en la spec 002; hasta entonces el contenedor
de RabbitMQ corre, pero ningún flujo lo usa todavía.

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
