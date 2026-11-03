# Requisitos del proyecto

Transcripción estructurada del enunciado del curso, con el estado de cada punto.
**Este documento es la fuente de verdad del alcance.** Si una decisión técnica
choca con algo escrito aquí, gana lo escrito aquí.

---

## Rúbrica de evaluación

| Criterio | Puntos | Estado |
|---|---:|---|
| Sistema base: CRUD, arquitectura, código limpio y uso de GitHub | 5 | Hecho: una app de Django por dominio, con capas; specs 001 a 023 y revisión por PR |
| Agente de inteligencia artificial | 2 | Hecho: asistente público con RAG y citas (specs 005 y 018) |
| Flujo asíncrono con RabbitMQ o Kafka | 2 | Hecho: ingesta de documentos del asistente (spec 020); falta verificarla en producción |
| Logs y auditoría en base de datos | 2 | Hecho: bitácora del sistema y del agente (specs 001 y 015) |
| Reportería y Power BI | 2 | Hecho: 15 reportes con Excel y PDF, vistas `bi` y tablero `.pbix` (specs 016 y 021) |
| Despliegue en producción | 1 | Hecho: Render, Neon, CloudAMQP, Vercel y Supabase (spec 002) |
| Defensa oral del proyecto | 1 | Pendiente: ensayo del equipo |
| **Total** | **15** | |

Estado al 2026-11-03. Lo que quedó fuera del plan original, para responderlo en
la defensa: el modo interno del agente y las notificaciones por correo (la
rúbrica pide un solo flujo asíncrono).

---

## Requerimientos funcionales

### 1. Sistema base

- CRUD completo de **al menos 12 a 15 entidades núcleo** del dominio.
  - *Nuestro plan:* 25 entidades de negocio. Ver `docs/modelo-datos.md`.
- Persistencia en una o más bases de datos reales.
  - **Prohibido SQLite y similares.** Usamos PostgreSQL 16.
- Código limpio y control de versiones en GitHub, con proceso de ramas, pull
  requests e historial legible. **No se debe hacer a última hora.**
  - Ver `docs/convenciones.md`.
- Arquitectura expuesta como **API REST**.
  - **Limitado:** Node con JavaScript y FastAPI con Python. Usamos Django REST
    Framework.
- **Arquitectura lógica** a elección. Prohibido un solo archivo para todo.
  - *Nuestra elección:* arquitectura por capas con servicios y selectores,
    organizada por dominios. Ver `docs/arquitectura.md`.

### 2. Agente de inteligencia artificial

Integrado al sistema, por ejemplo capaz de responder a los usuarios sobre la
información pública del sistema.

*Proveedor:* Gemini Flash en su capa gratuita, detrás de una interfaz abstracta
(ver `docs/arquitectura.md`, sección 7).

*Nuestro plan:* dos modos.
- **Público:** consultas sobre propiedades disponibles, precios, ubicaciones y
  características. Solo accede a datos marcados como públicos.
- **Interno:** para empleados autenticados, consultas sobre cartera, pagos,
  avances de obra y morosidad, respetando los permisos del usuario.

### 3. RAG sobre documentación propia del negocio

Ingesta, recuperación y **citación de fuentes** sobre manuales, políticas y
catálogos.

*Nuestro plan:* indexar políticas comerciales de la agencia, manual de procesos,
requisitos legales de compraventa por país, plantillas de contratos y fichas
técnicas de propiedades. Toda respuesta cita documento y sección.

### 4. Desarrollo guiado por especificaciones

Evidencia del proceso, usando Claude Code, OpenCode, Codex o equivalentes, con
sus archivos respectivos (`CLAUDE.md`, `AGENTS.md`).

*Nuestro plan:* `CLAUDE.md` y `AGENTS.md` en la raíz, y una spec por
funcionalidad en `specs/`, enlazada desde su pull request. **La evidencia es el
historial de Git, así que debe construirse desde el día uno.**

### 5. Mensajería asíncrona

Al menos un flujo de negocio con RabbitMQ o Apache Kafka, **conectado a una
acción real del sistema**, no un ejemplo aislado.

*Nuestro plan:* dos flujos reales.
- **Ingesta de documentos.** Al subir un documento oficial se encola su
  procesamiento: extracción de texto, generación de embeddings e indexación en
  el RAG. Resuelve este requisito y el del RAG a la vez.
- **Notificaciones.** Al registrar un pago, aprobar una cotización o firmar un
  contrato se encola el envío de correo con el comprobante en PDF adjunto.

### 6. Logs y auditoría

Tablas que registren operaciones clave **del sistema base y del agente de IA**.

*Nuestro plan:* dos bitácoras separadas. Ver `docs/arquitectura.md`.

### 7. Reportería avanzada

Al menos **15 reportes** relevantes al dominio, con filtros y agregaciones
(totales, agrupamientos, rangos de fecha). **Cada reporte exportable a Excel
y a PDF.**

*Nuestro plan:* 15 reportes catalogados en `docs/reportes.md`.

### 8. Integración con Power BI

*Nuestro plan:* esquema `bi` en PostgreSQL con vistas en modelo estrella,
consumidas por Power BI. Ver `docs/reportes.md`.

### 9. Frontend funcional

*Nuestra elección:* React 19 + Vite + TypeScript, con TanStack Query y Table,
React Hook Form, shadcn/ui y Recharts. Detalle en `docs/frontend.md`.

### 10. Defensa oral

Individual. **Cada integrante debe poder explicar cualquier parte del sistema**,
no solo la que programó.

### 11. Manual técnico

Documento entregable al final del proyecto.

---

## Restricciones

- El dominio elegido debe ser un proyecto completo **no realizado en clase**.
- **Despliegue en producción en la nube.** Los sistemas no desplegados no serán
  revisados. Este es el riesgo más alto del proyecto: desplegar temprano, no al
  final. *Nuestra elección:* planes gratuitos; API y worker en Render,
  PostgreSQL en Neon, RabbitMQ en CloudAMQP y frontend en Vercel. Comparación
  de alternativas y justificación en `specs/002-despliegue.md`.
- Los commits apoyados con inteligencia artificial deben ser realizados
  únicamente por los estudiantes. **No se permite el vibecoding.**
- Los sistemas de inventario simple y punto de venta están bloqueados. Nuestro
  dominio no cae en esa categoría.
- El dominio debe ser distinto al de los demás equipos. **Confirmar con el
  catedrático que ningún otro equipo tomó agencia inmobiliaria.**

---

## Puntos a confirmar con el catedrático

1. Que el dominio de agencia inmobiliaria no esté tomado por otro equipo.
2. Fecha de entrega y fecha de la defensa oral.
3. Formato esperado del manual técnico.
4. **Si el frontend puede usar TypeScript.** La restricción del enunciado
   ("limitando el uso de Node con Javascript") aplica a la API, que será Django,
   pero conviene dejarlo confirmado por escrito antes de avanzar.
5. Si se requiere un informe de avance intermedio.
