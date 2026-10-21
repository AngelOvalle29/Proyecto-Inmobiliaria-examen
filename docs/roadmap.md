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

| Rol | Responsable | Apps y áreas | Componente de la rúbrica |
|---|---|---|---|
| **A** | DouGMV | `core`, `usuarios`, `catalogo`; despliegue e integración continua | Sistema base, arquitectura, autenticación, despliegue |
| **B** | Lilfacce | `crm`, `ventas`, `arrendamientos` | Sistema base, flujo comercial |
| **C** | AngelOvalle29 | `compras`, `construccion`, `ia` | Agente de IA y RAG |
| **D** | NathalyR15 | `reportes`, `auditoria`; mensajería (RabbitMQ y Celery) | Reportería, Power BI, RabbitMQ |

Asignado el 2026-10-14. Los nombres están como usuarios de GitHub; cada
integrante agrega su nombre real en el README.

**Responsabilidades compartidas:**
- El integrante **A** define los modelos base y las convenciones de código en la
  fase 0; el resto construye sobre eso.
- El integrante **A** monta el despliegue y la integración continua (spec 002)
  y mantiene el entorno de producción. Se movió del rol D al A al asignar los
  roles. Cualquier integrante puede colaborar en el despliegue con pull
  requests; A es quien los aprueba.
- El integrante **A** además apoya a los demás en sus apps cuando haga falta,
  siguiendo la regla de `docs/convenciones.md` §4: el cambio se marca en el
  pull request y lo aprueba el dueño de esa app.
- El integrante **D** es dueño de `auditoria`, que se creó con la spec 001: su
  primer paso es leer esa app y su sección de la spec.
- Todos revisan pull requests de todos.

---

## Plan de trabajo por integrante

Acordado el 2026-10-21, con la fase 0 terminada (spec 001). Cada integrante
implementa el bloque vertical de sus apps: modelo, servicios, API, pantallas y
pruebas. Se descartó un reparto en el que A implementaba la mayor parte
(propuesto y cerrado en el PR #5).

**El dato que ordena el plan:** `Propiedad` (`catalogo`, de A) es necesaria
para cotizaciones, ventas, arrendamientos, compras y construcción. El catálogo
es el camino crítico. Cada integrante tiene una parte que no depende de nadie y
que se empieza de inmediato.

### Todos, al empezar

1. Preparar el entorno local con el README y leer la spec 001 y su código: en
   la defensa individual cualquiera puede ser preguntado por la base.
2. Escribir la spec de su bloque con `specs/PLANTILLA.md` y que la apruebe otro
   integrante antes de programar.
3. Todo cambio va en una rama y con pull request, con mensajes según
   `docs/convenciones.md`. Nunca editar `develop` directamente desde la web.
4. Completar su parte de la §11 de la spec 001: qué revisó y qué entendió.

### A · Douglas

1. Destrabar la integración continua (GitHub Actions no se ha ejecutado nunca)
   y activar la protección de `main` y `develop` (requiere GitHub Pro, gratuito
   con el Student Developer Pack).
2. **Spec 002:** despliegue en Railway y Vercel. Incluye cerrar los pendientes de
   la spec 001 (estado en la cabecera y búsqueda sin mayúsculas en
   `obtener_id_usuario_por_email`).
3. **Spec 003, catálogo**, empezando por `TipoPropiedad`, `Propiedad` y `Unidad`
   en un primer PR, porque desbloquean a B y a C. Avalúos, amenidades,
   documentos oficiales e historial van en un PR posterior.
4. Base del frontend: login, menú y cliente de la API. Los demás construyen sus
   pantallas sobre ella.
5. Resto del catálogo y sus pantallas; apoyo a quien se atrase.

*A resolver en la spec 003:* `DocumentoOficial` (`catalogo`) apunta a
`ContratoVenta` (`ventas`) y a `ContratoCompra` (`compras`), que a su vez
apuntan a `Propiedad`: se forma un ciclo entre apps, como el que se resolvió en
la spec 001. Se acuerda con B y C antes de escribir la spec.

### B · Marco

1. **Spec de CRM**, empezando por `Cliente` y `Agente`, que no dependen del
   catálogo.
2. Cotizaciones y su detalle, cuando `Propiedad` esté en `develop`.
3. **Spec de ventas:** contratos, planes de pago y cuotas.
4. **Spec de arrendamientos**, siguiendo el patrón de ventas.
5. Pantallas de su bloque, sobre la base del frontend.

*A incluir en ventas y arrendamientos* (observaciones de B en el PR #1): cada
transacción guarda la tasa de cambio aplicada, y una conversión entre dos
monedas que no son el dólar necesita su propio registro de tipo de cambio.

### C · Angel

1. **Spec del agente de IA y el RAG.** No depende del catálogo y es el bloque de
   mayor riesgo (2 puntos): interfaz `ProveedorIA` e implementación de Gemini
   (`docs/arquitectura.md` §7), `DocumentoRAG` y `FragmentoRAG` con pgvector,
   búsqueda por similitud con citación. Primero: obtener la llave de Gemini y
   confirmar la dimensión de los embeddings.
2. **Spec de compras y construcción**, empezando por `Proveedor` y
   `Constructora`, que no dependen del catálogo.
3. Contratos de compra, proyectos, avances y pagos, cuando `Propiedad` esté en
   `develop`.
4. Herramientas del agente sobre los selectores de las demás apps, conforme
   existan, y los modos público e interno.
5. Pantallas de su bloque.

### D · Nathaly

1. Leer a fondo la app `auditoria`, que ya es suya.
2. Confirmar con el catedrático los puntos pendientes de `docs/requisitos.md`:
   fechas de entrega y defensa, dominio no tomado, TypeScript en el frontend y
   formato del manual técnico.
3. Bitácora del agente (`LogAgenteIA`) en `auditoria`, coordinada con C.
4. **Spec de la capa genérica de reportes** con exportadores a Excel y PDF. Se
   empieza con los datos que ya existen (tipos de cambio, catálogos).
5. **Spec de mensajería:** configuración de Celery y los flujos de
   notificaciones e ingesta de documentos. La ingesta alimenta el RAG de C y se
   acuerda con C; el worker en Railway lo configura A en la spec 002.
6. Los 15 reportes, conforme cada bloque tenga datos.
7. Power BI y el esquema `bi`, cuando haya tablas con datos.

### Riesgo de este reparto

Los bloques no tienen el mismo tamaño: los de C (IA, compras y construcción) y
D (15 reportes, Power BI, mensajería y auditoría) son mayores que el de B. Se
revisa en la reunión semanal, con las fechas reales del catedrático, y se
mueven piezas a tiempo en lugar de descubrirlo en la última semana.

---

## Fases

### Fase 0 · Fundación

Objetivo: que los cuatro puedan programar sin pisarse.

- Repositorio en GitHub con ramas protegidas
- Estructura del proyecto Django con las apps vacías
- `docker-compose.yml` con PostgreSQL (con pgvector) y RabbitMQ. Redis queda
  fuera por ahora (ver `docs/arquitectura.md` §6)
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
