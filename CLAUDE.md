# CLAUDE.md

Instrucciones para agentes de IA que trabajen en este repositorio.
Lee este archivo completo antes de escribir cualquier línea de código.

---

## 1. Qué es este proyecto

Sistema tipo ERP para una **agencia inmobiliaria latinoamericana** que administra
edificios de apartamentos, terrenos, casas, hoteles, bodegas, restaurantes y
gasolineras en varios países. Registra el ciclo completo de cada propiedad:
compra a proveedores, construcción con constructoras, documentación legal,
avalúos, cotizaciones, venta a clientes y arrendamiento.

Es el **proyecto final del curso Programación Comercial** (Universidad
Mesoamericana, Quetzaltenango). Vale 15 puntos sobre el curso. Equipo de 4
personas. Hay defensa oral **individual**: cada integrante debe poder explicar
cualquier parte del sistema.

El detalle de requisitos y cómo se califica está en `docs/requisitos.md`.
**Si una decisión técnica entra en conflicto con la rúbrica, gana la rúbrica.**

---

## 2. Regla más importante

> **Nunca generes código que el estudiante no pueda explicar en la defensa oral.**

El enunciado prohíbe explícitamente el vibecoding. Esto significa, en la práctica:

- Prefiere código simple y explícito sobre código ingenioso.
- No introduzcas librerías, patrones o abstracciones que no estén en
  `docs/arquitectura.md` sin preguntar primero.
- Cuando generes algo no trivial, explica **por qué** en lenguaje natural,
  no solo **qué** hace.
- Si una tarea es ambigua, **pregunta antes de implementar**. No adivines
  reglas de negocio.
- Trabaja en incrementos pequeños y revisables. Nada de pull requests de
  3,000 líneas.

---

## 3. Stack

| Capa | Tecnología | Nota |
|---|---|---|
| Lenguaje | Python 3.12 | |
| Framework | Django 5.x + Django REST Framework | FastAPI está prohibido por el enunciado |
| Base de datos | PostgreSQL 16 | SQLite está prohibido, ni siquiera en desarrollo |
| Vectores (RAG) | pgvector sobre la misma PostgreSQL | |
| Mensajería | RabbitMQ + Celery | |
| Cache / resultados | Redis | Fuera por ahora: Celery usa RabbitMQ como broker y no hay backend de resultados. Ver `docs/arquitectura.md` §6 |
| Excel | openpyxl | |
| PDF | WeasyPrint | |
| Auth | djangorestframework-simplejwt | |
| Modelo de IA | Gemini Flash (capa gratuita) | Chat y embeddings, mismo proveedor |
| Correo | Gmail SMTP con contraseña de aplicación | ~500 envíos diarios |
| Frontend | React 19 + Vite + TypeScript | Ver `docs/frontend.md` |
| Contenedores | Docker + Docker Compose | |
| Despliegue backend | Railway | Ver `specs/002-despliegue.md` |
| Despliegue frontend | Vercel | Plan Hobby, gratuito |

No cambies ninguna de estas piezas sin consultarlo con el equipo.

---

## 4. Estructura del repositorio

```
Proyecto-Inmobiliaria/
├── CLAUDE.md                 # este archivo
├── AGENTS.md                 # mismas reglas, para otros agentes
├── README.md                 # arranque del proyecto
├── docker-compose.yml        # infraestructura local
├── .env.example              # variables del backend
├── docs/
│   ├── requisitos.md         # qué pide el curso y cómo se califica
│   ├── arquitectura.md       # capas, reglas de dependencia, convenciones de código
│   ├── modelo-datos.md       # entidades y relaciones
│   ├── frontend.md           # estructura y convenciones del frontend
│   ├── reportes.md           # catálogo de los 15 reportes
│   ├── convenciones.md       # git, ramas, commits, pull requests
│   └── roadmap.md            # fases y reparto de trabajo
├── specs/
│   ├── PLANTILLA.md          # formato obligatorio de cada especificación
│   ├── 001-fundacion.md      # esqueleto del proyecto
│   └── 002-despliegue.md     # Railway, Vercel e integración continua
├── .github/workflows/
│   └── ci.yml                # pruebas y calidad en cada pull request
├── backend/                  # proyecto Django (se crea en la fase 0)
│   └── Dockerfile            # imagen de producción
└── frontend/                 # proyecto React (se crea en la fase 2)
    └── .env.example          # variables del frontend
```

---

## 5. Flujo de trabajo obligatorio: especificación primero

Este proyecto se desarrolla **guiado por especificaciones**. El curso pide
evidencia de esto, así que el flujo no es negociable:

1. **Existe una spec.** Toda funcionalidad nueva empieza con un archivo en
   `specs/NNN-nombre.md` basado en `specs/PLANTILLA.md`.
2. **La spec se revisa** y la aprueba otro integrante del equipo.
3. **Se abre una rama** siguiendo `docs/convenciones.md`.
4. **Se implementa** contra la spec, no contra la intuición.
5. **Se abre un pull request** que enlaza a la spec.
6. **Otro integrante revisa** y aprueba.

Si te piden implementar algo y **no existe una spec**, tu primera respuesta
debe ser proponer la spec, no escribir código.

Las specs son documentos vivos: si durante la implementación se descubre que
algo estaba mal planteado, se actualiza la spec en el mismo pull request.

---

## 6. Reglas de arquitectura

El detalle completo está en `docs/arquitectura.md`. El resumen que debes tener
siempre presente:

**Capas, de afuera hacia adentro:**

```
views.py / serializers.py   →  HTTP: validar entrada, formatear salida
services.py                 →  escrituras: reglas de negocio, transacciones
selectors.py                →  lecturas: consultas, filtros, agregaciones
models.py                   →  datos: campos, constraints, validación propia
```

**Reglas duras:**

- Una vista **nunca** contiene reglas de negocio. Solo valida, llama a un
  servicio o selector, y devuelve.
- Una vista **nunca** hace `Model.objects.filter(...)` directamente. Eso vive
  en `selectors.py`.
- Toda escritura que toque más de una tabla va en `services.py` dentro de
  `transaction.atomic()`.
- Los modelos no llaman a servicios. La dependencia va en una sola dirección.
- Nada de lógica de negocio en señales de Django (`signals`). Son difíciles de
  rastrear y de defender oralmente.
- Prohibido `Model.objects.all()` sin paginar en un endpoint.

**Organización por dominio:** cada app de Django es un dominio del negocio
(`catalogo`, `crm`, `ventas`, `arrendamientos`, `compras`, `construccion`,
`reportes`, `ia`, `auditoria`, `usuarios`). Ver `docs/arquitectura.md`.

---

## 7. Convenciones de código

- **Idioma:** el dominio se nombra en español (`Propiedad`, `ContratoVenta`,
  `calcular_saldo_pendiente`). Las palabras clave de Python y los nombres de
  librerías quedan en inglés. No mezcles: no uses `PropertySale` ni
  `get_propiedad`.
- **Formato:** `ruff format` y `ruff check`. Correr antes de cada commit.
- **Tipos:** anotaciones de tipo en todas las funciones de `services.py` y
  `selectors.py`.
- **Docstrings:** obligatorios en servicios y selectores, explicando la regla
  de negocio, no la mecánica del código.
- **Migraciones:** una migración por pull request siempre que sea posible.
  Nunca editar una migración ya fusionada a `develop`.
- **Dinero:** siempre `DecimalField(max_digits=18, decimal_places=2)`. Nunca
  `FloatField`. Todo monto guarda su moneda.
- **Fechas:** siempre con zona horaria (`USE_TZ = True`). Guardar en UTC.
- **Borrado:** borrado lógico (`activo = BooleanField`) en entidades de
  negocio. No se borran contratos ni pagos físicamente.
- **Secretos:** jamás en el repositorio. Todo por variables de entorno vía
  `django-environ`. Si ves una credencial en el código, deténte y avisa.

---

## 8. Auditoría: regla transversal

Toda operación de escritura (crear, editar, borrar) sobre una entidad de
negocio **debe quedar registrada** en la tabla de auditoría, con usuario,
entidad, acción, valores anteriores y nuevos, IP y fecha.

El agente de IA tiene su propia bitácora: pregunta, herramientas invocadas,
documentos recuperados, respuesta, tokens y tiempo.

Si implementas un endpoint de escritura y no registra auditoría, **está
incompleto**. Ver `docs/arquitectura.md`, sección de auditoría.

---

## 9. Decisiones cerradas y abiertas

**Cerradas.** No las cuestiones ni propongas alternativas salvo que el equipo
lo pida:

- Backend en Django REST Framework con PostgreSQL.
- Frontend en React 19 + Vite + TypeScript. Detalle en `docs/frontend.md`.
- Despliegue del backend en **Railway**, del frontend en **Vercel**.
  Justificación en `specs/002-despliegue.md`.
- **Gemini Flash** para el agente y para los embeddings del RAG, en su capa
  gratuita. Nunca se llama al SDK de Gemini directamente desde un servicio:
  todo pasa por la interfaz de proveedor descrita en `docs/arquitectura.md`,
  sección 7.
- **Gmail SMTP** con contraseña de aplicación para las notificaciones.
- Todo corre en contenedores, para que cambiar de proveedor siga siendo
  posible.

**Abiertas.** No las resuelvas por tu cuenta; si una tarea depende de alguna,
pregunta:

- **Almacenamiento de documentos oficiales** en producción (volumen de Railway
  o almacenamiento de objetos externo).
- **Dominio propio.** Por ahora se usan los subdominios de Railway y Vercel.

---

## 10. Comandos

> Estos comandos aplican una vez creado el proyecto Django en la fase 0
> (ver `specs/001-fundacion.md`). Antes de eso, el repositorio solo tiene
> documentación.

```bash
# Levantar infraestructura (PostgreSQL con pgvector y RabbitMQ)
docker compose up -d

# Entorno de desarrollo
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

# Base de datos
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo          # datos de demostración

# Servidor
python manage.py runserver

# Worker de Celery (en otra terminal)
celery -A config worker -l info

# Calidad
ruff check . && ruff format --check .
pytest
pytest --cov=apps --cov-report=term-missing
```

Frontend (desde la fase 2):

```bash
cd frontend
npm install
npm run dev          # servidor de desarrollo en http://localhost:5173
npm run build        # compilación de producción
npm run lint
npm run typecheck
npm run gen:api      # regenera los tipos desde el esquema OpenAPI del backend
```

---

## 11. Cosas que NO debes hacer

- No uses SQLite, ni siquiera para correr pruebas.
- No crees endpoints fuera de `/api/v1/`.
- No metas lógica de negocio en `views.py`, `serializers.py` ni `admin.py`.
- No hagas commit directo a `main` ni a `develop`.
- No agregues dependencias sin justificarlas en el pull request.
- No generes datos de prueba con nombres de personas reales.
- No implementes funcionalidad que no esté en una spec aprobada.
- No borres ni reescribas specs anteriores: se actualizan, no se sustituyen.
- En el frontend, no hagas `fetch` suelto en los componentes: todo pasa por
  TanStack Query (ver `docs/frontend.md`).
- No escribas a mano los tipos de las respuestas de la API: se generan desde el
  esquema OpenAPI con `npm run gen:api`.
- No crees una pantalla por reporte: la pantalla de reportes es genérica y se
  alimenta del catálogo que expone la API.
- No importes el SDK de Gemini fuera de `apps/ia/proveedores/`. El resto del
  sistema solo conoce la interfaz abstracta.
- No subas datos personales reales a la API de Gemini: en la capa gratuita el
  contenido se usa para mejorar los productos de Google.
