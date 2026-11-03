# Guía del sistema: cómo se hizo y cómo funciona

Este documento es para estudiar el sistema de punta a punta. No reemplaza al
manual técnico (`docs/manual-tecnico.md`), que describe cada módulo con sus
reglas: aquí se explica **cómo encajan las piezas** y **por qué se hicieron
así**, siguiendo el recorrido de una petición real.

Si solo tiene diez minutos, lea §2 (el mapa), §4 (una petición de punta a
punta) y §13 (las decisiones que más se preguntan).

---

## 1. Qué es el sistema

Un ERP para una agencia inmobiliaria que opera en varios países de
Latinoamérica. Registra el ciclo completo de una propiedad:

```
compra a un proveedor → obra con una constructora → avalúos y documentos
      → cotización → venta en cuotas o arrendamiento mensual
```

Además tiene un asistente con IA para visitantes, 15 reportes exportables, un
tablero de Power BI y dos bitácoras de auditoría.

---

## 2. El mapa: qué corre dónde

```
             Navegador
                 │
                 ▼
   ┌──────────────────────────┐
   │ Vercel: frontend React   │   HTML y JavaScript estáticos
   └──────────────────────────┘
                 │ HTTPS + JWT  (/api/v1/...)
                 ▼
   ┌──────────────────────────────────────────────┐
   │ Render: un solo contenedor                    │
   │   gunicorn → Django REST Framework (la API)   │
   │   celery worker (en segundo plano)            │
   └──────────────────────────────────────────────┘
      │              │               │              │
      ▼              ▼               ▼              ▼
  Neon:          CloudAMQP:      Supabase:       Gemini:
  PostgreSQL 16  RabbitMQ        Storage (S3)    chat y
  + pgvector     (la cola)       archivos        embeddings
      ▲
      │ solo lectura, usuario powerbi_reader, esquema bi
  Power BI Desktop
```

| Pieza | Para qué | Por qué esa |
|---|---|---|
| Django + DRF | La API REST | El enunciado prohíbe FastAPI y Node con JavaScript |
| PostgreSQL (Neon) | Todos los datos | SQLite está prohibido; Neon tiene plan gratuito con pgvector |
| pgvector | Los vectores del RAG | Viven en la misma base: no hay otra base que administrar |
| RabbitMQ (CloudAMQP) + Celery | La cola de la ingesta de documentos | La rúbrica pide un flujo asíncrono real |
| Supabase Storage | Documentos e imágenes | API compatible con S3 y 1 GB gratis |
| Gemini Flash | Respuestas y embeddings | Capa gratuita, un solo proveedor para las dos cosas |
| React + Vite + TypeScript | La interfaz | Tipos generados desde la API: si el backend cambia, el frontend no compila |

**Todo es gratuito.** El precio: Render y Neon "se duermen" sin tráfico, y la
primera petición tarda unos 50 segundos.

---

## 3. Cómo se construyó

### 3.1 Primero la spec, después el código

Ninguna funcionalidad empezó por el código. El orden fue siempre:

1. **Una spec** en `specs/NNN-nombre.md`, con la plantilla `specs/PLANTILLA.md`:
   problema, alcance, reglas de negocio numeradas, modelo, API, auditoría,
   criterios de aceptación y pruebas.
2. **Otro integrante la aprueba** en un pull request.
3. **Se implementa en una rama** (`feature/NNN-…`), por incrementos.
4. **Un pull request** que enlaza la spec, con lo que se verificó.
5. **Otro integrante revisa** y se fusiona a `develop`. A `main` se llega solo
   con un PR de *release*, y `main` es lo que se despliega.

Si al implementar algo resultó distinto de lo planeado, la spec se actualizó
en el mismo PR. El §11 de cada spec cuenta qué hizo el agente de IA y qué
decidió el integrante.

### 3.2 Las specs, en orden

| Spec | Qué resolvió |
|---|---|
| 001 | Fundación: estructura, capas, usuarios y roles, JWT, errores uniformes, auditoría |
| 002 | Despliegue en Render, Neon, CloudAMQP y Vercel |
| 003 | Catálogo: tipos, propiedades, unidades y estados |
| 004 | CRM: clientes, agentes y la regla de cartera |
| 005 | El agente de IA: proveedor, RAG y citas |
| 006 | Proveedores y constructoras |
| 007 | Cotizaciones y ventas en cuotas |
| 008 | Arrendamientos y pagos de renta |
| 010 | La base del frontend: rutas, sesión, menú por rol, tabla y formulario genéricos |
| 011 | Avalúos y documentos oficiales en Supabase |
| 012 | Pantallas de CRM, ventas y arrendamientos |
| 013 | Listado de usuarios para crear agentes |
| 014 | Pantallas del catálogo |
| 015 | La bitácora del agente de IA |
| 016 | La capa genérica de reportes y los exportadores |
| 017 | Contratos de compra, proyectos de construcción y pagos |
| 018 | Pantallas de compras, construcción y el asistente público |
| 019 | Imágenes de las propiedades |
| 020 | La ingesta asíncrona por RabbitMQ |
| 021 | Los reportes restantes y Power BI |
| 022 | El diseño editorial |
| 023 | El tablero de Inicio y el menú plegable |

### 3.3 El reparto

| Rol | Bloque |
|---|---|
| A (Douglas) | Fundación, despliegue, catálogo, avalúos, documentos, imágenes, mensajería |
| B (Marco) | CRM, cotizaciones, ventas, arrendamientos y sus pantallas; diseño |
| C (Angel) | Compras, construcción y el agente de IA |
| D (Nathaly) | Auditoría del agente, reportes y Power BI |

Cualquiera puede ser preguntado por cualquier bloque en la defensa.

---

## 4. Una petición de punta a punta: registrar el pago de una cuota

La mejor manera de entender la arquitectura es seguir una petición. Una
contadora registra Q 57,216.18 de la cuota 1 del contrato CV-00004.

### 4.1 En el navegador

1. La pantalla `DetalleContratoVenta` muestra las cuotas. Al pulsar *Registrar
   pago* se abre `DialogoPagarCuota`, un formulario de `FormularioDatos`
   validado con **Zod** (monto positivo, fecha obligatoria).
2. Al enviar, la mutación de **TanStack Query** llama a
   `clienteApi.post('/cuotas/{id}/pagos/', datos)`. `clienteApi`
   (`frontend/src/api/cliente.ts`) es un axios que **agrega el token JWT** a
   cada petición.
3. Si el token de acceso venció (dura 30 minutos), el interceptor de respuesta
   pide uno nuevo con el de refresco (7 días) y **repite la petición sola**. Si
   el de refresco también venció, cierra la sesión.

### 4.2 En la API, capa por capa

```
urls.py         cuotas/<pk>/pagos/  →  PagarCuotaView
views.py        TieneRol: ¿el rol está en REGISTRAN_PAGOS?   (si no: 403)
serializers.py  ¿el cuerpo tiene la forma correcta?          (si no: 400)
services.py     registrar_pago_cuota(...)  ← aquí están las reglas
models.py       CuotaPago, ContratoVenta: campos y constraints
```

**La vista no decide nada del negocio.** Solo valida la forma, llama al
servicio con el usuario y la IP, y devuelve lo que el servicio entrega.

**El servicio** (`backend/apps/ventas/services.py`, `registrar_pago_cuota`)
hace, dentro de `@transaction.atomic`:

1. **Bloquea** el contrato y la cuota con `select_for_update()`, siempre en ese
   orden. Si dos personas pagan la misma cuota a la vez, la segunda espera y ve
   el saldo que dejó la primera.
2. **Revisa las reglas:** el contrato debe estar VIGENTE, la fecha entre la
   firma y hoy, y el monto no puede pasar del saldo. Si algo falla, **lanza una
   excepción de dominio** (`ContratoNoVigente`, `PagoExcedeSaldo`…), no arma
   una respuesta HTTP.
3. **Busca la tasa al dólar** de la fecha del pago y la guarda en la cuota.
4. Actualiza la cuota: PARCIAL o PAGADA.
5. **Registra la auditoría** con `registrar_auditoria`: quién, qué entidad,
   valores antes y después, el monto, la tasa y la IP.
6. Si era la última cuota, pasa el contrato a LIQUIDADO y lo audita también.

Si cualquier paso falla, `transaction.atomic` deshace **todo**: no puede quedar
una cuota pagada sin su registro de auditoría.

### 4.3 La respuesta de error

Toda excepción de dominio hereda de `ErrorDominio`
(`backend/apps/core/exceptions.py`), que trae su `codigo` y su `estado_http`.
El manejador global (`apps/core/manejador_errores.py`) la convierte siempre en
el mismo formato:

```json
{"error": {"codigo": "PAGO_EXCEDE_SALDO", "mensaje": "…", "detalles": {…}}}
```

El frontend lee ese formato con `leerErrorApi` y muestra el mensaje arriba del
formulario. Por eso **todas las pantallas muestran los errores igual**.

### 4.4 De vuelta en el navegador

La mutación termina e **invalida** las consultas del contrato: TanStack Query
las vuelve a pedir y la tabla de cuotas se actualiza sin recargar la página.

---

## 5. Las capas y sus reglas

| Capa | Archivo | Puede | No puede |
|---|---|---|---|
| HTTP | `views.py`, `serializers.py` | Validar forma, elegir servicio o selector, responder | Reglas de negocio; `Model.objects.filter` |
| Escritura | `services.py` | Reglas, transacciones, bloqueos, auditoría | Saber de HTTP |
| Lectura | `selectors.py` | Consultas, filtros, agregaciones | Escribir |
| Datos | `models.py` | Campos, constraints de base | Llamar servicios |

**Por qué así:** cada regla vive en un solo lugar. La regla "un agente solo ve
su cartera" está en `listar_clientes_visibles` (`apps/crm/selectors.py`), y la
usan la lista, el detalle, los reportes y el tablero. Si estuviera en cada
vista, bastaría olvidarla en una para filtrar datos ajenos.

**Una app por dominio:** `catalogo`, `crm`, `ventas`, `arrendamientos`,
`compras`, `construccion`, `reportes`, `ia`, `auditoria`, `usuarios` y `core`
(países, ciudades, monedas, tipos de cambio y lo común). Una app lee a otra
**solo por sus selectores y servicios**, nunca tocando sus modelos.

**Sin señales de Django:** una señal ejecuta código "a escondidas" al guardar
un modelo. Todo efecto secundario se llama explícitamente desde el servicio,
así se puede seguir leyendo el código de arriba abajo.

---

## 6. Usuarios, roles y permisos

**Cinco roles:** ADMINISTRADOR, GERENTE, AGENTE, CONTABILIDAD y CONSULTA. Cada
usuario tiene exactamente uno.

**Quién puede hacer qué** lo dice cada vista con `TieneRol`
(`apps/usuarios/permissions.py`):

```python
permission_classes = [TieneRol]
roles_por_metodo = {"POST": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]}
```

- Un **GET** que la vista no declara queda abierto a cualquier usuario con
  sesión: leer no cambia nada.
- Una **escritura** que la vista no declara se **rechaza**. Olvidar declararla
  deja la puerta cerrada, no abierta.
- Sin sesión, 401; con sesión pero sin el rol, 403.

**Qué registros ve cada uno** no lo decide el permiso sino el selector: un
AGENTE solo encuentra a sus clientes. Uno ajeno responde 404, como si no
existiera.

**En el frontend** el menú (`frontend/src/menu.ts`) declara qué roles ven cada
pantalla y qué roles escriben. Ocultar un botón es comodidad: **la seguridad
está en la API**, que vuelve a revisar el rol.

**Autenticación:** JWT con `djangorestframework-simplejwt`. El inicio de
sesión tiene límite de 30 intentos por minuto. Cada inicio de sesión queda en
la auditoría.

---

## 7. Reglas transversales

### 7.1 Auditoría

Toda escritura sobre una entidad de negocio llama a `registrar_auditoria`
(`apps/auditoria/services.py`): usuario, entidad, id, acción (CREAR,
ACTUALIZAR, ELIMINAR), valores anteriores y nuevos, IP y fecha. La tabla solo
admite inserciones: nadie edita la historia.

El agente tiene **su propia bitácora**, `LogAgenteIA`, con la pregunta, los
fragmentos recuperados y su distancia, la respuesta, los tokens y el tiempo.

### 7.2 Nada se borra

Las entidades de negocio tienen `activo`. "Eliminar" lo pone en falso y lo
audita como ELIMINAR. Contratos y pagos ni siquiera se desactivan: se
**anulan** con un motivo.

### 7.3 Dinero y monedas

- Siempre `DecimalField(max_digits=18, decimal_places=2)`. Nunca `float`: un
  float no representa 0.10 exacto, y los centavos se pierden al sumar.
- Cada monto guarda **su moneda** (GTQ, USD, MXN, COP…).
- Cada contrato y cada pago guarda **la tasa al dólar del día** y el monto
  convertido. Así un reporte de 2025 en dólares da lo mismo hoy que mañana,
  aunque la tasa cambie.
- Los reportes **no suman monedas distintas**: totalizan por moneda y, aparte,
  en dólares con la tasa guardada.

### 7.4 Dos personas a la vez

Tres herramientas evitan que dos peticiones simultáneas rompan una regla:

| Herramienta | Ejemplo |
|---|---|
| `select_for_update()` | Dos pagos de la misma cuota: el segundo espera al primero |
| `estado_requerido` | Aprobar una cotización exige que la unidad siga DISPONIBLE *después* de bloquearla |
| `UniqueConstraint` con condición | Una sola portada activa por propiedad; un solo contrato no anulado por propiedad |

El constraint es la última defensa: aunque el código fallara, la base de datos
rechaza el dato inválido.

---

## 8. Los bloques del negocio, en una línea cada uno

| Bloque | Lo esencial |
|---|---|
| Catálogo | Una propiedad pasa por `EN_NEGOCIACION → ADQUIRIDA → EN_CONSTRUCCION → DISPONIBLE → RESERVADA → VENDIDA/ARRENDADA`. Un edificio no se vende: se venden sus unidades. El estado solo cambia por `cambiar_estado_propiedad` o `cambiar_estado_unidad` |
| Documentos e imágenes | El tipo se comprueba por los primeros bytes del archivo, no por la extensión. Se guardan con nombre generado en un bucket privado y se ven con una URL firmada de 5 minutos |
| CRM | Clientes con su agente asignado. La cartera filtra todo lo que ve un agente |
| Ventas | Aprobar una cotización reserva el bien; firmar genera el contrato y sus cuotas (contado o financiado con enganche, plazo y tasa) |
| Arrendamientos | Un pago de renta por mes; la mora se calcula con la fecha, no es un estado |
| Compras | Completar un contrato de compra pasa la propiedad a ADQUIRIDA |
| Construcción | Iniciar la obra la pasa a EN_CONSTRUCCION y finalizarla a DISPONIBLE. Lo programado más lo pagado nunca supera el presupuesto |

El detalle de cada regla, con su número, está en la spec del bloque y en el
manual técnico.

---

## 9. El asistente con IA (RAG)

**RAG** significa *Retrieval-Augmented Generation*: antes de preguntarle al
modelo, se **buscan** los pedazos de documento que tratan del tema y se le
entregan junto con la pregunta. El modelo responde con esos pedazos, no con lo
que "sabe".

### 9.1 Preparar los documentos (indexar)

1. Un administrador sube un `.md` en *Documentos del asistente*.
2. `troceo.py` lo parte por sus encabezados `##`, en trozos de hasta 1,500
   caracteres. Cada trozo recuerda su documento y su sección.
3. Gemini convierte cada trozo en un **vector de 768 números** (un
   *embedding*) que representa su significado. Textos parecidos dan vectores
   cercanos.
4. Los trozos y sus vectores se guardan en `FragmentoRAG`, con un índice
   **HNSW** de pgvector para buscar rápido por distancia coseno.

### 9.2 Responder una pregunta

```
pregunta ─► su vector ─► los 5 trozos más cercanos con distancia ≤ 0.42
                                 │
            ┌──── ninguno ───────┴────── alguno ─────┐
            ▼                                        ▼
  "No encontré información"            trozos numerados + instrucciones
  (no se llama al modelo)                     ─► Gemini ─► respuesta con [1], [2]
```

- **Sin trozos cercanos, no se llama al modelo.** No gasta cuota ni le da
  ocasión de inventar.
- **Las instrucciones** (`apps/ia/instrucciones.py`) le exigen responder solo
  con los trozos, citar cada dato con su número y no cambiar de tema aunque se
  lo pidan.
- **Las citas:** la API devuelve solo los trozos que el modelo citó, con
  documento, sección y extracto. La pantalla convierte cada `[n]` en un
  enlace a su cita.
- **Límite:** 10 preguntas por minuto por visitante; al pasarse, 429 con los
  segundos de espera.

### 9.3 El proveedor intercambiable

El SDK de Gemini **solo se importa en `apps/ia/proveedores/gemini.py`**. El
resto del sistema conoce la interfaz de `proveedores/base.py`, y `fabrica.py`
elige la implementación. Cambiar a otro proveedor es escribir otra clase, sin
tocar los servicios. Sin llave configurada, el asistente responde 503 y el
resto del sistema sigue funcionando.

---

## 10. La mensajería asíncrona (RabbitMQ + Celery)

**El problema:** indexar un documento pide un embedding por trozo y puede
tardar decenas de segundos. Si se hiciera dentro de la petición, el navegador
esperaría todo ese tiempo y un error de Gemini haría fallar la subida.

**La solución:** la subida solo guarda el documento como PENDIENTE y deja un
mensaje en la cola. Un *worker* lo procesa aparte.

```
POST /documentos-agente/      (dentro de la transacción)
   │  guarda DocumentoRAG en PENDIENTE
   │  transaction.on_commit(encolar)   ← solo si la transacción se confirma
   ▼
RabbitMQ, cola "documentos"
   ▼
worker de Celery: ia.indexar_documento
   │  trocea, pide embeddings, guarda fragmentos
   ▼
INDEXADO   (o ERROR, con el motivo, después de 3 reintentos)
```

Los detalles que importan:

| Detalle | Por qué |
|---|---|
| `transaction.on_commit` | Si la transacción se deshace, no queda un mensaje apuntando a un documento que no existe |
| `acks_late=True` | El mensaje se confirma al **terminar** la tarea: si el worker se cae a la mitad, RabbitMQ lo entrega de nuevo |
| Hasta 3 reintentos con espera creciente | Un error pasajero de Gemini (429, 503) se resuelve solo |
| El estado vive en `DocumentoRAG.estado_indexacion` | No hay *result backend*: la pantalla lee el estado de la base y se actualiza sola mientras haya pendientes |
| La tarea es delgada | Solo llama al servicio `indexar_documento`; la lógica se puede probar sin cola |

---

## 11. Reportes y Power BI

### 11.1 Los 15 reportes

Una sola capa genérica (`apps/reportes/`) los sirve a todos:

- **`catalogo.py`** declara cada reporte: código (R01…), título, roles que lo
  ven, columnas con su formato y filtros.
- **Un selector por reporte** con dos funciones: `resumir` (totales y grupos
  de **todo** el filtro, calculados en PostgreSQL) y `seleccionar` (solo las
  filas de la página, con `LIMIT/OFFSET`).
- **`exportadores.py`** convierte cualquier reporte a Excel (openpyxl) o PDF
  (WeasyPrint). Un reporte nuevo no toca los exportadores.
- **Una sola pantalla** en el frontend se arma con el catálogo que entrega la
  API: no hay una pantalla por reporte.

**Por qué el resumen y la página van aparte:** los totales deben ser de todo el
filtro, no de las 25 filas que se ven. Una exportación de más de 5,000 filas se
rechaza antes de cargar los datos y pide acotar el filtro.

### 11.2 Power BI

- La migración `reportes/0001_vistas_bi` crea el esquema **`bi`** con cuatro
  vistas en **modelo estrella**: `hechos_ventas` (los hechos) y
  `dim_propiedad`, `dim_geografia` y `dim_tiempo` (las dimensiones).
- Power BI se conecta con **`powerbi_reader`**, un usuario que solo puede leer
  el esquema `bi`: si intenta leer una tabla del sistema, la base responde
  *permission denied*.
- El tablero está en `docs/powerbi/inmobiliaria.pbix`, con su fuente editable.

---

## 12. El frontend

```
frontend/src/
  api/          un hook por consulta y mutación, por dominio; tipos.generados.ts
  componentes/  ui/ (botón, tarjeta…) y comunes/ (TablaDatos, FormularioDatos…)
  paginas/      una carpeta por dominio
  sesion/       tokens y estado de la sesión
  menu.ts       entradas del menú y roles por pantalla
```

| Idea | Cómo se aplica |
|---|---|
| Nada de `fetch` suelto | Toda llamada pasa por TanStack Query, que guarda en caché, reintenta e invalida |
| Tipos generados, no escritos | `npm run gen:api` los genera desde el esquema OpenAPI; si un campo cambia en el backend, el frontend deja de compilar hasta adaptarse |
| Componentes genéricos | `TablaDatos` (paginación, acciones por fila, confirmación) y `FormularioDatos` (campos declarados + Zod) sirven a todas las pantallas |
| Rutas protegidas | `RutaProtegida` manda a iniciar sesión; el asistente es la única pantalla pública |
| Diseño | Tokens de color con nombre en español en `index.css` (spec 022) |

---

## 13. Las decisiones que más se preguntan

**¿Por qué servicios y selectores, y no la lógica en las vistas o los modelos?**
Para que cada regla viva en un solo lugar, se pueda probar sin HTTP y la vista
quede tan delgada que no haya dónde esconder una regla.

**¿Por qué `select_for_update` si ya se revisan las reglas?**
Porque revisar y escribir son dos pasos: entre uno y otro, otra petición puede
cambiar el dato. El bloqueo hace que la segunda espere.

**¿Por qué guardar la tasa de cambio en cada pago?**
Porque la tasa cambia. Si se recalculara con la de hoy, los reportes del pasado
cambiarían cada día.

**¿Por qué el asistente no inventa?**
Porque no se le llama si no hay trozos cercanos, las instrucciones le prohíben
salirse de ellos y cada dato debe llevar su cita.

**¿Por qué `on_commit` al encolar?**
Para no publicar un mensaje sobre un documento cuya transacción después se
deshizo.

**¿Por qué una sola base y no una base vectorial aparte?**
pgvector guarda los vectores en la misma PostgreSQL: una base, un respaldo, una
conexión, y las consultas pueden unir fragmentos con documentos.

**¿Por qué no hay modo interno del agente ni notificaciones por correo?**
Estaban en el plan original. La rúbrica pide un agente con RAG y un flujo
asíncrono real; se priorizó lo que se evalúa y se dejó constancia en
`docs/requisitos.md`.

**¿Por qué no corre GitHub Actions?**
La cuenta no ejecuta workflows (bloqueo de cuenta, issue #14). Las pruebas se
corrieron en cada PR y su resultado quedó en la descripción.

**¿Qué hizo la IA y qué hizo el equipo?**
El §11 de cada spec lo registra por sesión, y el §13 del manual lo resume. La
IA propuso, redactó y programó por incrementos; el integrante eligió el
alcance, revisó y decidió qué fusionar.

---

## 14. Cómo comprobar que funciona

| Qué | Cómo |
|---|---|
| Pruebas del backend | `pytest` (más de 1,100). Las de PDF necesitan Pango y Cairo: en Windows fallan, en la imagen Docker pasan |
| Estilo | `ruff check .` y `ruff format --check .` |
| Migraciones al día | `python manage.py makemigrations --check --dry-run` |
| Frontend | `npm run lint`, `npm run typecheck`, `npm run build` |
| Salud en producción | `GET /api/v1/health/` responde `{"estado":"ok","base_datos":"ok"}` |

**Cómo arranca producción** (`backend/scripts/iniciar.sh`): aplica las
migraciones, asegura el administrador inicial, carga la demo si
`CARGAR_DATOS_DEMO` lo pide, levanta el worker de Celery en segundo plano y,
al final, gunicorn con la API.

---

## 15. Dónde buscar cada cosa

| Busca… | Está en… |
|---|---|
| Qué pide el curso | `docs/requisitos.md` |
| Las reglas de un bloque | `specs/NNN-…md`, §3 |
| Cómo funciona un módulo | `docs/manual-tecnico.md` |
| Las entidades | `docs/modelo-datos.md` |
| Las capas y convenciones | `docs/arquitectura.md` y `CLAUDE.md` |
| Un endpoint | `backend/apps/<dominio>/urls.py` y `views.py` |
| Una regla de negocio | `backend/apps/<dominio>/services.py` |
| Una consulta | `backend/apps/<dominio>/selectors.py` |
| Una pantalla | `frontend/src/paginas/<dominio>/` |
| El despliegue | `specs/002-despliegue.md`, `render.yaml`, `backend/scripts/iniciar.sh` |
