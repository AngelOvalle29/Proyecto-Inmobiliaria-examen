# Plan de trabajo

## Principio rector

**Desplegar temprano, desplegar siempre.** El enunciado es explícito: los
sistemas no desplegados no serán revisados. El despliegue no es la última fase,
es la primera. Al final de la fase 1 debe existir un endpoint vivo en la nube,
aunque solo devuelva una lista de países.

El segundo riesgo más alto es el historial de Git: se evalúa el proceso, así que
el trabajo debe distribuirse en el tiempo desde ya.

---

## Reparto por responsable

Cada integrante es dueño de un bloque vertical: modelo, servicios, API,
frontend y pruebas de sus apps. Así cada quien puede defender su parte y el
trabajo no se bloquea entre sí.

| Responsable | Apps | Componente de la rúbrica |
|---|---|---|
| **A** | `core`, `usuarios`, `catalogo` | Sistema base, arquitectura, autenticación |
| **B** | `crm`, `ventas`, `arrendamientos` | Sistema base, flujo comercial |
| **C** | `compras`, `construccion`, `ia` | Agente de IA y RAG |
| **D** | `reportes`, `auditoria`, infraestructura | Reportería, Power BI, RabbitMQ, despliegue |

**Responsabilidades compartidas:**
- El integrante **A** define los modelos base y las convenciones de código en la
  fase 0; el resto construye sobre eso.
- El integrante **D** monta el despliegue y la canalización de integración
  continua en la fase 1, y es quien mantiene el entorno de producción.
- Todos revisan pull requests de todos.

> Asignar los nombres reales a A, B, C y D en la primera reunión, y reflejarlo
> en el README.

---

## Fases

### Fase 0 · Fundación

Objetivo: que los cuatro puedan programar sin pisarse.

- Repositorio en GitHub con ramas protegidas
- Estructura del proyecto Django con las apps vacías
- `docker-compose.yml` con PostgreSQL, RabbitMQ y Redis
- Modelo base abstracto con campos de rastro
- Entidades de `core`: país, ciudad, moneda, tipo de cambio
- Autenticación JWT y roles
- Configuración de `ruff`, `pytest` y `drf-spectacular`
- `.env.example` y archivos de requisitos

Spec: `specs/001-fundacion.md`

### Fase 1 · Despliegue mínimo

Objetivo: tener producción funcionando cuando todavía no duele arreglarla.

- Backend desplegado en Railway: API, worker, PostgreSQL y RabbitMQ
- Frontend desplegado en Vercel (al inicio, una página en blanco basta)
- Variables de entorno y secretos configurados en ambos proveedores
- Límite de gasto configurado en Railway
- Integración continua con GitHub Actions, obligatoria para fusionar
- Despliegue automático al fusionar a `main`
- Endpoint de salud (`/api/v1/health/`) respondiendo públicamente

Spec: `specs/002-despliegue.md`

### Fase 2 · Catálogo y CRM

- CRUD de propiedades, unidades, tipos, amenidades
- Avalúos y documentos oficiales (carga de archivos)
- Historial de eventos de propiedad
- CRUD de clientes y agentes
- Cotizaciones con detalle y cambios de estado
- Auditoría funcionando en todo lo anterior

### Fase 3 · Operación comercial

- Contratos de venta, planes de pago y cuotas
- Contratos de arrendamiento y pagos de renta
- Proveedores y contratos de compra
- Constructoras, proyectos, avances y pagos
- Reglas de negocio y cambios de estado de propiedades

### Fase 4 · Mensajería asíncrona

- RabbitMQ y Celery integrados
- Flujo de ingesta de documentos: subir, extraer texto, trocear, generar
  embeddings, indexar
- Flujo de notificaciones por correo con PDF adjunto
- Reintentos, manejo de errores y registro en bitácora

### Fase 5 · Agente de IA y RAG

- pgvector y modelo de embeddings
- Carga de la base documental: políticas, manuales, requisitos legales
- Recuperación por similitud con citación de fuentes
- Herramientas del agente sobre los selectores existentes
- Modo público y modo interno con permisos
- Bitácora completa del agente
- Interfaz de conversación en el frontend

### Fase 6 · Reportería y Power BI

- Capa genérica de reportes y sus exportadores
- Los 15 reportes del catálogo
- Exportación a Excel y PDF de cada uno
- Esquema `bi` con vistas en modelo estrella
- Usuario de solo lectura para Power BI
- Tableros en Power BI y archivo `.pbix` versionado

### Fase 7 · Frontend completo

Avanza en paralelo desde la fase 2, se cierra aquí.

- Autenticación y control de acceso por rol
- Pantallas de catálogo, CRM, ventas, arrendamientos y construcción
- Visor de reportes con filtros y botones de descarga
- Interfaz del agente de IA
- Consulta de bitácoras de auditoría

### Fase 8 · Cierre

- Manual técnico
- Datos de demostración realistas y abundantes
- Pruebas de extremo a extremo de los flujos principales
- Ensayo de la defensa oral con defensa cruzada
- Revisión final contra la rúbrica de `docs/requisitos.md`

---

## Dependencias entre fases

```
Fase 0 ──┬── Fase 1 (despliegue)
         │
         └── Fase 2 ──┬── Fase 3
                      │
                      ├── Fase 4 ── Fase 5
                      │
                      └── Fase 6
                      
Fase 7 avanza en paralelo desde la fase 2
```

La fase 5 depende de la 4 porque la ingesta de documentos para el RAG usa la
cola. La fase 6 necesita datos reales de las fases 2 y 3 para que los reportes
tengan sentido.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El despliegue falla cerca de la entrega | Desplegar en la fase 1, mantenerlo vivo |
| La factura de Railway se dispara | Límite de gasto configurado desde el primer día |
| Historial de Git concentrado al final | Commits distribuidos, reunión semanal |
| El RAG consume más tiempo del previsto | Empezar con pocos documentos y ampliar |
| Límites de la capa gratuita de Gemini | Cache de respuestas, límite de peticiones por usuario, revisar los límites en AI Studio antes de la defensa |
| Un integrante se atrasa y bloquea al resto | Bloques verticales independientes, revisión cruzada |
| Reportes dejados para el final | La capa genérica se construye con los primeros 3 reportes, el resto es repetitivo |
| Nadie puede explicar el módulo ajeno | Defensa cruzada antes de la entrega |

---

## Antes de empezar

1. Confirmar con el catedrático que el dominio no está tomado.
2. Confirmar fechas de entrega y de defensa.
3. Confirmar con el catedrático que el frontend puede usar TypeScript. La
   restricción del enunciado aplica a la API, pero conviene dejarlo por escrito.
4. Asignar nombres reales a A, B, C y D.
5. Crear el repositorio y configurar la protección de ramas, con la
   integración continua como verificación obligatoria.
6. Crear las cuentas de Railway y Vercel, y acordar quién paga y cómo se
   reparte el costo (alrededor de $15 a $20 al mes entre cuatro).
7. Obtener la llave de la API de Gemini en Google AI Studio y confirmar ahí los
   identificadores exactos de los modelos y la dimensión de los embeddings.
8. Crear una cuenta de Gmail para el proyecto, activar la verificación en dos
   pasos y generar una contraseña de aplicación para el SMTP.
