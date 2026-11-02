# Manual técnico

Sistema de gestión para una agencia inmobiliaria latinoamericana. Proyecto final
del curso Programación Comercial, Universidad Mesoamericana, Quetzaltenango.

> **Borrador.** La estructura es una propuesta para todo el equipo. Cada
> integrante completa su sección. Las marcadas *Pendiente* no se han escrito.

---

## 1. Descripción general

El sistema registra el ciclo de cada propiedad: compra, construcción,
documentación, avalúos, cotizaciones, venta y arrendamiento. Incluye un agente
de IA con recuperación de documentos, mensajería asíncrona, reportes exportables
y bitácoras de auditoría.

*Pendiente: el equipo completa el resumen de funcionalidades.*

## 2. Arquitectura

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Base de datos | PostgreSQL 16 con pgvector |
| Mensajería | RabbitMQ y Celery |
| Frontend | React 19, Vite y TypeScript |
| Despliegue | Render, Neon, CloudAMQP y Vercel |

Cada dominio es una app de Django, con las mismas capas:

```
views.py / serializers.py   HTTP: valida la entrada y formatea la salida
services.py                 escrituras: reglas de negocio y transacciones
selectors.py                lecturas: consultas y agregaciones
models.py                   datos: campos y constraints
```

El detalle está en `docs/arquitectura.md`, y las entidades en
`docs/modelo-datos.md`.

### 2.1 Cómo se conectan las piezas en producción

```
Navegador ──► Vercel (React)          proyecto-inmobiliaria-chi.vercel.app
    │
    └── HTTPS + JWT ──► Render: un contenedor   inmobiliaria-api-x8gr.onrender.com
                         ├─ gunicorn (API de Django)
                         └─ worker de Celery ◄── colas celery y documentos
                              │       │
             PostgreSQL ◄─────┘       └────► RabbitMQ
             Neon, con pgvector              CloudAMQP
                              │
             Supabase Storage (documentos oficiales, privado)
             Gemini (agente y embeddings, solo desde apps/ia/proveedores/)
```

La API y el worker comparten un contenedor para caber en el plan gratuito de
Render. El detalle y las alternativas descartadas están en
`specs/002-despliegue.md`; la operación, en la §12.

## 3. Instalación

```bash
docker compose up -d                 # PostgreSQL con pgvector y RabbitMQ
cd backend
python -m venv .venv
.venv\Scripts\activate               # Windows; en Linux: source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

En otra terminal, el worker. Con `-Q` consume las dos colas: sin ella, la
indexación de los documentos del agente se queda esperando (§8).

```bash
celery -A config worker -Q celery,documentos -l info
```

Y el frontend:

```bash
cd frontend
npm install
npm run dev
```

**Variables de entorno:**
- **Backend:** se copian de `.env.example` a `.env`, en la raíz.
- **Frontend:** se copian de `frontend/.env.example` a `frontend/.env`; basta
  `VITE_API_URL=http://localhost:8000/api/v1`.

Ningún secreto va en el repositorio. Las de producción están en la §12.

**Pruebas:** `pytest`, desde `backend/`. En Windows fallan las pruebas que
generan PDF, porque WeasyPrint necesita librerías GTK; en la imagen de Docker
pasan.

## 4. Catálogo, avalúos y documentos (rol A)

### 4.1 Entidades

| Entidad | Qué es |
|---|---|
| `TipoPropiedad` | Siete tipos de la migración (casa, terreno, apartamentos…). `requiere_unidades` dice si se vende por unidades |
| `Propiedad` | El bien: tipo, ciudad, áreas, precio de lista con su moneda, estado y `es_publica` |
| `Unidad` | Un apartamento o local de una propiedad que requiere unidades |
| `Avaluo` | Una valuación con fecha, valor, moneda, perito y metodología |
| `DocumentoOficial` | Escritura, licencia, plano, certificación, avalúo, contrato u otro, con su archivo |

Reglas completas: `specs/003-catalogo-propiedades.md` y
`specs/011-avaluos-documentos.md`. Pantallas: `specs/014-pantallas-catalogo.md`.

### 4.2 Reglas que más se preguntan

- **El código `PROP-00001` lo pone el sistema** y no cambia.
- **Un edificio no se vende ni se arrienda entero:** se venden sus unidades.
  Por eso los reportes cuentan como bien la unidad, no el edificio.
- **El estado solo cambia por `cambiar_estado_propiedad` o
  `cambiar_estado_unidad`.** Esa función bloquea la fila (`select_for_update`) y
  acepta `estado_requerido`: si otro proceso cambió el bien mientras tanto,
  responde 409 `PROPIEDAD_NO_DISPONIBLE`. Ventas, arrendamientos, compras y
  construcción la usan, así dos contratos no toman el mismo bien.
- **Estados:** `EN_NEGOCIACION` (el inicial), `ADQUIRIDA`, `EN_CONSTRUCCION`,
  `DISPONIBLE`, `RESERVADA`, `VENDIDA`, `ARRENDADA` y `BAJA`.
- **Nada se borra:** desactivar marca `activo` en falso. Una propiedad con
  unidades activas no se desactiva (409).
- **Los avalúos no se editan:** el historial es la plusvalía. Uno equivocado se
  desactiva y se registra otro.
- **Documentos:**
  - solo PDF, JPG o PNG de hasta 10 MB, revisados por su contenido y no solo
    por la extensión;
  - se guardan con un nombre generado (`documentos/PROP-00001/<uuid>.pdf`);
  - en producción van a un bucket privado de Supabase, y se descargan con una
    URL firmada que vence a los 5 minutos;
  - un documento que respalda un avalúo activo no se desactiva (409).

### 4.3 Permisos

Escriben `ADMINISTRADOR` y `GERENTE`; los tipos de propiedad, solo
`ADMINISTRADOR`. Todos los roles autenticados leen y descargan.

### 4.4 API y pantallas

| Recurso | Ruta |
|---|---|
| Tipos de propiedad | `/api/v1/tipos-propiedad/` |
| Propiedades | `/api/v1/propiedades/` (filtros por tipo, ciudad, país, estado, precio y `?buscar=`) |
| Cambiar estado | `/api/v1/propiedades/{id}/cambiar-estado/` y `/api/v1/unidades/{id}/cambiar-estado/` |
| Unidades | `/api/v1/propiedades/{id}/unidades/` (`?buscar=` por código) |
| Avalúos | `/api/v1/propiedades/{id}/avaluos/` |
| Documentos | `/api/v1/propiedades/{id}/documentos/` (multipart) y `/api/v1/documentos/{id}/descarga/` |

En el frontend, la **ficha de la propiedad** (`/catalogo/propiedades/{id}`)
reúne todo en pestañas: Datos (con el último avalúo), Unidades, Avalúos y
Documentos. Los vencidos se ven en rojo y los que vencen en 30 días, en ámbar.
La pestaña va en la URL (`?pestana=documentos`), así se puede compartir.

## 5. CRM, ventas y arrendamientos (rol B)

### 5.1 Entidades

| App | Entidades |
|---|---|
| `crm` | `Cliente`, `Agente`, `Cotizacion` |
| `ventas` | `ContratoVenta`, `CuotaPago` |
| `arrendamientos` | `ContratoArrendamiento`, `PagoRenta` |

Reglas completas: `specs/004-crm-clientes-agentes.md`,
`specs/007-cotizaciones-ventas.md` y `specs/008-arrendamientos.md`. Pantallas:
`specs/012-pantallas-bloque-b.md`.

### 5.2 Flujo de una venta

```
BORRADOR → ENVIADA → APROBADA → contrato VIGENTE → LIQUIDADO
                  ↘ RECHAZADA
```

| Paso | Servicio | Efecto en el bien |
|---|---|---|
| Aprobar cotización | `aprobar_cotizacion` | De `DISPONIBLE` a `RESERVADA` |
| Rechazar una aprobada | `rechazar_cotizacion` | De `RESERVADA` a `DISPONIBLE` |
| Firmar contrato | `firmar_contrato` | A `VENDIDA` |
| Anular contrato sin pagos | `anular_contrato` | De `VENDIDA` a `DISPONIBLE` |

- Un contrato se firma desde una cotización aprobada o sin ella.
- De contado, nace `LIQUIDADO` y sin cuotas.
- Financiado, genera cuotas fijas por sistema francés:
  `cuota = P · i / (1 − (1 + i)^−n)`. La última ajusta los centavos.
- Un pago puede ser parcial. Al pagar la última cuota, el contrato pasa a
  `LIQUIDADO`.

### 5.3 Flujo de un arrendamiento

| Acción | Servicio | Efecto |
|---|---|---|
| Firmar | `firmar_arrendamiento` | Genera todos los pagos; el bien pasa a `ARRENDADA` |
| Cobrar | `registrar_pago_renta` | Pago completo, con recargo si pasó la gracia |
| Renovar | `renovar_arrendamiento` | Contrato nuevo; el anterior queda `RENOVADO` |
| Rescindir | `rescindir_arrendamiento` | Cancela los pagos posteriores; el bien queda `DISPONIBLE` |
| Finalizar | `finalizar_arrendamiento` | Pasa a `VENCIDO`; el bien queda `DISPONIBLE` |

### 5.4 Permisos

| Rol | Clientes y cotizaciones | Firmar | Registrar pagos | Anular, rescindir o finalizar |
|---|---|---|---|---|
| `ADMINISTRADOR`, `GERENTE` | Todos | Sí | Sí | Sí |
| `AGENTE` | Su cartera | En su cartera | No | No |
| `CONTABILIDAD` | Lectura | No | Sí | No |
| `CONSULTA` | Lectura | No | No | No |

La cartera se aplica en `listar_clientes_visibles`. Un agente que pide algo ajeno
recibe 404, no 403, para no confirmar que existe.

### 5.5 Decisiones de diseño

- **La mora y el vencimiento se calculan.** No se guardan, para que nunca queden
  desactualizados.
- **Cada contrato y pago guarda su tasa al dólar.** Así un reporte no recalcula
  el pasado.
- **La comisión se guarda al firmar.** Con cotización, es del agente que cotizó.
- **Los contratos no se borran.** Anular es un estado.
- **Toda escritura se audita** con `registrar_auditoria`, dentro de la misma
  transacción.
- **`select_for_update`** protege los pagos simultáneos: el segundo espera y lee
  el saldo que dejó el primero.

### 5.6 API

| Recurso | Ruta |
|---|---|
| Clientes | `/api/v1/clientes/` |
| Agentes | `/api/v1/agentes/` |
| Cotizaciones | `/api/v1/cotizaciones/` |
| Contratos de venta | `/api/v1/contratos-venta/` |
| Contratos de arrendamiento | `/api/v1/contratos-arrendamiento/` |

La documentación completa de cada endpoint está en `/api/docs/`.

### 5.7 Datos de demostración

`seed_demo` carga agentes, clientes, contratos y cotizaciones ficticios, con
fechas relativas a hoy, para que siempre haya cuotas pagadas, parciales y en
mora. Las unidades `A-103` y `A-203` quedan libres para mostrar una venta en
vivo. Los comandos no duplican datos.

## 6. Compras y construcción

*Pendiente: rol C.*

## 7. Agente de IA y RAG

*Pendiente: rol C.*

## 8. Mensajería (rol A, spec 020)

El flujo con RabbitMQ es **la ingesta de los documentos del agente**: subir o
reemplazar un documento encola su indexación. La API responde enseguida, y el
worker trocea el texto, pide los vectores a Gemini e indexa.

```
Gerente sube un .md ──► API: guarda el documento PENDIENTE
                         └─ al confirmar la transacción (on_commit)
                              └─► RabbitMQ, cola "documentos"
                                   └─► worker: ia.indexar_documento
                                        ├─ trocea, pide vectores, guarda fragmentos → INDEXADO
                                        └─ si Gemini falla: reintenta a 1, 2 y 4 minutos → ERROR
```

**Decisiones que se defienden:**
- **`transaction.on_commit`:** se encola solo si la transacción se confirma. El
  worker nunca busca un documento que todavía no existe, y si algo falla no
  queda un mensaje huérfano.
- **El estado vive en el documento** (`PENDIENTE`, `INDEXADO`, `ERROR`), no en
  un backend de resultados. Así no hace falta Redis, que se dejó fuera.
- **`acks_late`:** el mensaje se confirma al terminar. Si Render reinicia el
  worker a mitad de una tarea, RabbitMQ lo entrega de nuevo. Repetir es seguro,
  porque indexar reemplaza los fragmentos.
- **Reindexar vale en cualquier estado**, para que ningún documento quede
  atascado.
- **La tarea es una cáscara:** recibe el id y llama a `indexar_documento`; la
  lógica vive en el servicio.

**Dónde se ve:** la pantalla *Documentos del asistente*
(`/asistente/documentos`, administración y gerencia). Sube un `.md` y el estado
pasa de Pendiente a Indexado; mientras hay pendientes recientes, la lista se
actualiza cada 5 segundos. En el log de Render aparece `ia.indexar_documento`
recibida en la cola `documentos`.

**Cuota:** CloudAMQP gratuito da 1 millón de mensajes al mes; cada subida es un
mensaje. El worker corre sin eventos de monitoreo, que serían mensajes extra.

Las notificaciones por correo (cola `notificaciones`) quedaron fuera de esta
entrega.

## 9. Auditoría

*Pendiente: rol D.*

## 10. Reportes

Capa genérica: *pendiente, rol D.*

### 10.1 Reportes comerciales (rol B)

| Código | Reporte | Contenido |
|---|---|---|
| R01 | Ventas por período | Contratos no anulados; totales por moneda, y por mes y país |
| R02 | Desempeño por agente | Cotizaciones, conversión, ventas y comisión |
| R03 | Embudo de cotizaciones | Conteos por estado y tasas |
| R04 | Ranking de clientes | Ordenado por venta en dólares, con saldos actuales |
| R10 | Estado de cuenta | Cuotas y rentas, con exigible, pagado y saldo |
| R11 | Morosidad | Deuda vencida por tramo y moneda |

Todos respetan la cartera, en el detalle y en los totales. Las reglas están en
`specs/021-reportes-restantes-power-bi.md`.

### 10.2 Reportes de catálogo, compras y obra (rol A)

| Código | Reporte | Contenido | Quién lo ve |
|---|---|---|---|
| R06 | Propiedades por estado | Cada bien, desde cuándo está en su estado (según la bitácora) y cuántos días lleva | Todos |
| R08 | Evolución de avalúos | Cada avalúo con el anterior comparable (misma propiedad y moneda) y su variación | Todos |
| R14 | Ocupación de arrendamientos | Bienes, arrendados y disponibles por propiedad; ocupación ponderada; renta vigente por moneda | Todos |
| R13 | Compras por proveedor | Compras completadas, con sus componentes de costo por proveedor, mes y moneda, y en USD | Administración, gerencia y contabilidad |
| R15 | Avance y presupuesto de obra | Presupuesto, programado, pagado, comprometido, disponible, saldo y atraso de cada proyecto | Administración, gerencia y contabilidad |

- **Sin dato es sin dato:** si un bien no tiene historia en la bitácora, R06
  deja la fecha vacía. No usa la última edición, que no dice cuándo entró al
  estado.
- **R14 pondera:** 2 arrendados de 5 bienes es 40 %, no el promedio de los
  porcentajes de cada propiedad.
- **R15 da los mismos números que el detalle del proyecto:** usa la misma
  regla de comprometido. Las sumas de pagos van en subconsultas: un `JOIN`
  contaría el presupuesto una vez por cada pago.

## 11. Power BI

### 11.1 Vistas del esquema `bi` (rol A)

La migración `reportes/0001_vistas_bi` crea cuatro vistas en modelo estrella:
`dim_tiempo`, `dim_geografia`, `dim_propiedad` y `hechos_ventas`. Son vistas,
no tablas: no copian datos.

Power BI se conecta con el rol `powerbi_reader`, que solo puede leer esas
vistas. Se crea con `docs/powerbi/crear_lector.sql`, a mano en Neon, y la
contraseña nunca va al repositorio. Las relaciones y la conexión están en
`docs/powerbi/README.md`.

### 11.2 Tablero

*Pendiente: rol D.*

## 12. Despliegue (rol A, spec 002)

### 12.1 Servicios

| Pieza | Servicio, plan gratuito | Dirección |
|---|---|---|
| API y worker | Render, un contenedor Docker | `inmobiliaria-api-x8gr.onrender.com` |
| Frontend | Vercel | `proyecto-inmobiliaria-chi.vercel.app` |
| PostgreSQL 16 con pgvector | Neon | La de `DATABASE_URL` |
| RabbitMQ | CloudAMQP | La de `RABBITMQ_URL` |
| Documentos oficiales | Supabase Storage, bucket privado | Las variables `STORAGE_*` |
| Agente de IA | Gemini, capa gratuita | `IA_API_KEY` |

### 12.2 Cómo se publica una versión

1. Todo entra a `develop` por pull request.
2. Un pull request de `develop` a `main` es el release. Al fusionarlo, Render
   construye la imagen desde `backend/Dockerfile` y Vercel compila el frontend,
   los dos solos.
3. Render solo da la versión por buena cuando `/api/v1/health/` responde.

Al arrancar, `backend/scripts/iniciar.sh` hace, en orden:
1. Aplica las migraciones.
2. Crea el administrador inicial si no existe (`asegurar_administrador`).
3. Carga la demo (`seed_demo`) si `CARGAR_DATOS_DEMO=true`. Es idempotente:
   correrla en cada arranque no duplica nada.
4. Levanta el worker de Celery con `-Q celery,documentos`, dentro de un ciclo
   que lo reinicia si se cae.
5. Encola una tarea de diagnóstico: si el log dice "tarea de diagnóstico
   recibida", la API publica en RabbitMQ y el worker consume.
6. Arranca gunicorn, con un solo proceso por los 512 MB del plan.

### 12.3 Variables de producción

Se cargan en el panel de Render. `render.yaml` las declara, pero las secretas
van con `sync: false`, sin valor.

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | La llave de Django |
| `DATABASE_URL` | Neon |
| `RABBITMQ_URL` | CloudAMQP |
| `CORS_ALLOWED_ORIGINS` | La dirección de Vercel: solo el frontend puede llamar a la API |
| `DJANGO_SUPERUSER_EMAIL`, `_NOMBRE_COMPLETO`, `_PASSWORD` | El administrador inicial |
| `STORAGE_BACKEND=s3` y `STORAGE_*` | Supabase Storage |
| `IA_API_KEY` | Gemini. Sin ella, el agente responde 503 y el resto funciona |
| `NUM_PROXIES=3` | Cloudflare, el borde de Render y un proxy interno: así la auditoría guarda la IP real del cliente. Medido en producción |
| `CARGAR_DATOS_DEMO=true` | La demo en cada arranque |

En Vercel van `VITE_API_URL` (`https://…onrender.com/api/v1`) y
`VITE_ENTORNO=produccion`, como variables normales y no secretas: Vercel no
acepta como secreta una variable que empieza con `VITE_`, y de todos modos el
navegador la ve.
`frontend/vercel.json` manda toda ruta a `index.html`, para que recargar
`/catalogo/propiedades` no dé 404.

### 12.4 Lo que impone el plan gratuito

- **Render se duerme** a los 15 minutos sin tráfico, y la primera petición
  tarda alrededor de un minuto. Antes de una demostración, abra la app un par
  de minutos antes. Si la API duerme, el worker también, pero las tareas
  esperan en RabbitMQ y se ejecutan al despertar.
- **Neon se duerme** a los 5 minutos y despierta en menos de un segundo.
- **No hay límite de gasto que configurar:** si se agota una cuota, el
  servicio se detiene, no cobra.

### 12.5 Problemas que ya pasaron

- **Finales de línea:** un script con CRLF no corre en Linux. El
  `.gitattributes` fuerza LF en todo el repositorio.
- **Los PDF necesitan Pango y Cairo:** el `Dockerfile` los instala. En Windows
  faltan, y por eso las pruebas de PDF fallan ahí y pasan en Docker.
- **Un token de un usuario que ya no existe** daba 500 al renovar la sesión;
  ahora responde 401 y el frontend cierra la sesión (#73).

## 13. Uso de agentes de IA

*Pendiente: el equipo acuerda cómo declararlo. Cada spec tiene su §11.*
