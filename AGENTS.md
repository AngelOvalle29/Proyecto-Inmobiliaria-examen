# AGENTS.md

Instrucciones para cualquier agente de IA que trabaje en este repositorio
(Codex, OpenCode, Cursor, Gemini CLI, Aider u otro).

`CLAUDE.md` contiene estas mismas reglas. **Si editas uno, edita el otro en el
mismo commit.** Un pull request que modifique solo uno de los dos no se aprueba.

---

## Contexto

Sistema tipo ERP para una agencia inmobiliaria latinoamericana que administra
edificios de apartamentos, terrenos, casas, hoteles, bodegas, restaurantes y
gasolineras en varios países. Cubre el ciclo completo de cada propiedad: compra,
construcción, documentación legal, avalúos, cotización, venta y arrendamiento.

Proyecto final del curso Programación Comercial, Universidad Mesoamericana
Quetzaltenango. Equipo de 4 personas. Hay defensa oral individual.

Requisitos y rúbrica: `docs/requisitos.md`. **Ante un conflicto entre una
decisión técnica y la rúbrica, gana la rúbrica.**

---

## Regla número uno

**No generes código que el estudiante no pueda explicar oralmente.** El
enunciado del curso prohíbe el vibecoding de manera explícita.

- Código simple y explícito antes que código ingenioso.
- Sin librerías ni patrones fuera de `docs/arquitectura.md` sin preguntar.
- Explica el porqué de cada decisión no trivial.
- Ante ambigüedad, pregunta. No inventes reglas de negocio.
- Incrementos pequeños y revisables.

---

## Stack

**Backend:** Python 3.12 · Django 5 + Django REST Framework · PostgreSQL 16 ·
pgvector · RabbitMQ + Celery · openpyxl (Excel) · WeasyPrint (PDF) ·
SimpleJWT · Docker Compose.

**Frontend:** React 19 + Vite + TypeScript · TanStack Query · TanStack Table ·
React Hook Form + Zod · shadcn/ui + Tailwind · Recharts. Ver `docs/frontend.md`.

**Despliegue (planes gratuitos):** API y worker en Render, PostgreSQL con
pgvector en Neon, RabbitMQ en CloudAMQP y frontend en Vercel.
Ver `specs/002-despliegue.md`.

**Servicios externos:** Gemini Flash (capa gratuita) para el agente y los
embeddings · Gmail SMTP con contraseña de aplicación para las notificaciones.

Prohibido por el enunciado del curso: SQLite (y similares), FastAPI, Node con
JavaScript para la API.

> **Qué se usa de verdad.** Esta tabla es el plan. Gmail SMTP no tiene código
> que envíe correo, Redis no se usa y Recharts no está instalado. El estado real
> de cada pieza, con su motivo, está en `docs/guia-del-sistema.md` §16.


---

## Flujo obligatorio: especificación primero

1. Toda funcionalidad empieza con una spec en `specs/NNN-nombre.md`, basada en
   `specs/PLANTILLA.md`.
2. Otro integrante la revisa y aprueba.
3. Se crea la rama (ver `docs/convenciones.md`).
4. Se implementa contra la spec.
5. Se abre el pull request enlazando la spec.
6. Otro integrante revisa y aprueba.

Si te piden código y no existe una spec, tu primera entrega es la spec.

---

## Arquitectura

```
views.py / serializers.py   →  HTTP: validar entrada, formatear salida
services.py                 →  escrituras: reglas de negocio, transacciones
selectors.py                →  lecturas: consultas, filtros, agregaciones
models.py                   →  datos: campos, constraints, validación propia
```

- Las vistas no contienen reglas de negocio ni consultan modelos directamente.
- Las escrituras multitabla van en servicios, dentro de `transaction.atomic()`.
- Los modelos no llaman a servicios.
- Sin lógica de negocio en señales de Django.
- Sin listados sin paginar.

Cada app de Django es un dominio: `catalogo`, `crm`, `ventas`,
`arrendamientos`, `compras`, `construccion`, `reportes`, `ia`, `auditoria`,
`usuarios`. Detalle en `docs/arquitectura.md`.

---

## Convenciones de código

- Dominio nombrado en español (`Propiedad`, `ContratoVenta`,
  `calcular_saldo_pendiente`). Sin mezclar idiomas.
- `ruff format` y `ruff check` antes de cada commit.
- Anotaciones de tipo en servicios y selectores.
- Dinero: `DecimalField(max_digits=18, decimal_places=2)` con su moneda. Nunca
  `FloatField`.
- Fechas con zona horaria, almacenadas en UTC.
- Borrado lógico en entidades de negocio. Contratos y pagos no se borran.
- Secretos solo por variables de entorno. Ninguna credencial en el repositorio.
- Una migración por pull request. No se editan migraciones ya fusionadas.

---

## Auditoría

Toda escritura sobre una entidad de negocio registra: usuario, entidad, acción,
valores anteriores y nuevos, IP y fecha. El agente de IA registra además:
pregunta, herramientas invocadas, documentos recuperados, respuesta, tokens y
tiempo. Un endpoint de escritura sin auditoría está incompleto.

---

## Decisiones cerradas

Django REST Framework · PostgreSQL · React + Vite + TypeScript · Render, Neon
y CloudAMQP gratuitos para el backend · Vercel para el frontend · Gemini Flash para IA y embeddings ·
Gmail SMTP para correo · Supabase Storage para documentos · todo en contenedores. No propongas alternativas salvo
que el equipo lo pida.

## Decisiones abiertas (no las cierres por tu cuenta)

Dominio propio.

---

## Comandos

Disponibles una vez completada la fase 0 (`specs/001-fundacion.md`).

```bash
docker compose up -d                  # PostgreSQL con pgvector y RabbitMQ
cd backend && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
celery -A config worker -l info       # en otra terminal
ruff check . && ruff format --check .
pytest --cov=apps

cd frontend && npm install            # frontend, desde la fase 2
npm run dev
npm run lint && npm run typecheck
npm run gen:api                       # tipos desde el esquema OpenAPI
```

---

## Prohibido

SQLite · endpoints fuera de `/api/v1/` · lógica de negocio en vistas,
serializadores o admin · commits directos a `main` o `develop` · dependencias
sin justificar · datos de prueba con personas reales · código sin spec
aprobada · borrar o reescribir specs anteriores.

En el frontend: `fetch` suelto en componentes (todo pasa por TanStack Query) ·
tipos de la API escritos a mano (se generan con `npm run gen:api`) · una
pantalla por reporte (la pantalla de reportes es genérica).

En la IA: importar el SDK de Gemini fuera de `apps/ia/proveedores/` · enviar
datos personales reales a la API (en la capa gratuita el contenido se usa para
mejorar los productos de Google).
