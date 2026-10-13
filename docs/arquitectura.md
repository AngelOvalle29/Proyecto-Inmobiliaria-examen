# Arquitectura

## 1. Decisión de arquitectura

**Arquitectura por capas con servicios y selectores, organizada por dominios.**

Django por defecto empuja a concentrar la lógica en las vistas y los modelos.
El enunciado del curso exige una arquitectura lógica explícita y prohíbe
concentrar todo en un solo lugar, así que adoptamos una separación estricta:

```
┌─────────────────────────────────────────────────┐
│  Presentación   views.py · serializers.py       │  HTTP
│                 urls.py · permissions.py        │
├─────────────────────────────────────────────────┤
│  Aplicación     services.py   (escrituras)      │  reglas de negocio
│                 selectors.py  (lecturas)        │
├─────────────────────────────────────────────────┤
│  Dominio        models.py                       │  datos e invariantes
│                 enums.py · exceptions.py        │
├─────────────────────────────────────────────────┤
│  Infraestructura  tasks.py · integraciones      │  Celery, correo, IA
└─────────────────────────────────────────────────┘
```

**Regla de dependencia:** las capas de arriba conocen a las de abajo. Nunca al
revés. Un modelo jamás importa un servicio.

---

## 2. Responsabilidad de cada archivo

| Archivo | Hace | No hace |
|---|---|---|
| `views.py` | Recibe la petición, delega, devuelve la respuesta | Reglas de negocio, consultas a modelos |
| `serializers.py` | Valida formato de entrada y arma la salida | Reglas de negocio, acceso a base de datos |
| `filters.py` | Traduce los parámetros de un listado (`?pais=`) a filtros sobre la consulta del selector (django-filter) | Decidir qué registros son visibles: eso es del selector |
| `services.py` | Reglas de negocio de escritura, transacciones, auditoría | Hablar HTTP, conocer `request` |
| `selectors.py` | Consultas, filtros, agregaciones, optimización | Escribir en la base de datos |
| `models.py` | Campos, relaciones, constraints, validación propia | Llamar servicios, enviar correos |
| `tasks.py` | Tareas Celery. Son cáscaras delgadas que llaman servicios | Contener reglas de negocio |

**Ejemplo de la separación:**

```python
# selectors.py — solo lee
def listar_propiedades_disponibles(
    *, pais_id: int | None = None, precio_max: Decimal | None = None
) -> QuerySet[Propiedad]:
    """Propiedades en venta sin contrato activo, para el catálogo público."""
    qs = Propiedad.objects.filter(activo=True, estado=EstadoPropiedad.DISPONIBLE)
    if pais_id:
        qs = qs.filter(ciudad__pais_id=pais_id)
    if precio_max:
        qs = qs.filter(precio_lista__lte=precio_max)
    return qs.select_related("ciudad__pais", "tipo").order_by("-fecha_registro")


# services.py — escribe, con transacción y auditoría
@transaction.atomic
def registrar_venta(
    *, propiedad: Propiedad, cliente: Cliente, agente: Agente,
    monto: Decimal, moneda: Moneda, usuario: Usuario,
) -> ContratoVenta:
    """
    Registra la venta de una propiedad.

    Regla: una propiedad solo puede venderse si está DISPONIBLE y no tiene
    un contrato de arrendamiento vigente. Al venderse pasa a VENDIDA y se
    agrega el evento correspondiente a su historial.
    """
    if propiedad.estado != EstadoPropiedad.DISPONIBLE:
        raise PropiedadNoDisponible(propiedad.codigo)
    ...
```

---

## 3. Apps por dominio

Cada app de Django es un dominio del negocio. Dentro de cada una se repite la
misma estructura de archivos.

```
backend/
├── config/                    # settings, urls raíz, celery, wsgi/asgi
│   └── settings/              # base.py, dev.py, prod.py
├── apps/
│   ├── core/                  # países, ciudades, monedas, tipos de cambio,
│   │                          # modelos base y utilidades compartidas
│   ├── usuarios/              # usuario, roles, permisos, autenticación JWT
│   ├── catalogo/              # propiedades, unidades, tipos, amenidades,
│   │                          # avalúos, documentos oficiales, historial
│   ├── crm/                   # clientes, agentes, cotizaciones
│   ├── ventas/                # contratos de venta, planes y cuotas de pago
│   ├── arrendamientos/        # contratos de renta y cobros
│   ├── compras/               # proveedores y contratos de adquisición
│   ├── construccion/          # constructoras, proyectos, avances, pagos
│   ├── reportes/              # los 15 reportes y sus exportadores
│   ├── ia/                    # agente, herramientas y RAG
│   └── auditoria/             # bitácoras del sistema y del agente
└── requirements/              # base.txt, dev.txt, prod.txt
```

Estructura interna de una app:

```
apps/ventas/
├── __init__.py
├── apps.py
├── models.py
├── enums.py
├── exceptions.py
├── serializers.py
├── filters.py          # solo si la app tiene listados con filtros
├── services.py
├── selectors.py
├── views.py
├── urls.py
├── permissions.py
├── tasks.py
├── admin.py
├── migrations/
└── tests/
    ├── test_services.py
    ├── test_selectors.py
    └── test_api.py
```

**Comunicación entre apps:** una app llama a los **servicios y selectores** de
otra, nunca a sus modelos directamente.

Hay tres apps **transversales** que cualquier app puede importar: `core`,
`usuarios` y `auditoria`. Entre ellas, la dependencia es fija:

```
core       → no importa ninguna app
auditoria  → no importa ninguna app (referencia al usuario con
             settings.AUTH_USER_MODEL)
usuarios   → core, auditoria
```

Ningún modelo concreto de `core` hereda de `ModeloBase`: si lo hiciera, `core`
dependería de `usuarios` en las migraciones y se formaría un ciclo, porque
`Usuario` apunta a `core.Pais`. Justificación en `specs/001-fundacion.md` §10.

---

## 4. API REST

- Todo bajo `/api/v1/`.
- Nombres de recurso en plural y en español: `/api/v1/propiedades/`,
  `/api/v1/contratos-venta/`.
- Verbos HTTP estándar. Acciones que no son CRUD van como subrecurso:
  `POST /api/v1/cotizaciones/{id}/aprobar/`.
- Paginación obligatoria en todo listado. Página por defecto: 25 elementos.
- Filtros con `django-filter`. Búsqueda y ordenamiento vía parámetros.
- Documentación automática con `drf-spectacular` en `/api/docs/`.
- Autenticación JWT. Tokens de acceso de 30 minutos y de refresco de 7 días.

**Formato de error uniforme:**

```json
{
  "error": {
    "codigo": "PROPIEDAD_NO_DISPONIBLE",
    "mensaje": "La propiedad PROP-00123 no está disponible para venta.",
    "detalles": { "propiedad": "PROP-00123", "estado_actual": "ARRENDADA" }
  }
}
```

Las excepciones de dominio viven en `exceptions.py` de cada app y un manejador
global las traduce a este formato.

---

## 5. Auditoría

Dos bitácoras separadas, ambas en PostgreSQL.

### `auditoria_log_sistema`

| Campo | Descripción |
|---|---|
| `id` | Identificador |
| `usuario` | FK a usuario, nulo si la acción es del sistema o un login fallido |
| `entidad` | Nombre de la tabla afectada |
| `entidad_id` | Identificador del registro, nulo si no hay registro asociado |
| `accion` | CREAR, ACTUALIZAR, ELIMINAR, APROBAR, ANULAR, INICIAR_SESION, LOGIN_FALLIDO |
| `valores_anteriores` | JSONB |
| `valores_nuevos` | JSONB |
| `ip` | Dirección de origen |
| `user_agent` | Cliente usado |
| `fecha` | Fecha y hora con zona horaria |

**Implementación:** una función `registrar_auditoria(...)` en
`apps/auditoria/services.py`, invocada explícitamente desde cada servicio de
escritura, dentro de la misma transacción.

Se hace explícito y no con señales de Django a propósito: es rastreable, se lee
en el código y se puede defender oralmente.

### `auditoria_log_agente`

| Campo | Descripción |
|---|---|
| `id` | Identificador |
| `usuario` | Quién preguntó, nulo si es el agente público |
| `modo` | PUBLICO o INTERNO |
| `pregunta` | Texto de la consulta |
| `herramientas_invocadas` | JSONB con nombre y argumentos de cada llamada |
| `documentos_recuperados` | JSONB con los fragmentos del RAG y su puntaje |
| `respuesta` | Texto devuelto |
| `tokens_entrada` / `tokens_salida` | Conteo |
| `duracion_ms` | Tiempo total |
| `exito` | Booleano |
| `error` | Mensaje si falló |
| `fecha` | Fecha y hora con zona horaria |

---

## 6. Mensajería asíncrona

RabbitMQ como broker, Celery como worker.

**Redis queda fuera por ahora.** Celery usa RabbitMQ como broker y, mientras no
se necesite consultar el resultado de las tareas, el backend de resultados
sobra. Un servicio menos que desplegar, mantener y pagar. Si más adelante hace
falta cache, se agrega con su propia spec.

**Colas:**

| Cola | Flujo |
|---|---|
| `documentos` | Procesar documento subido: extraer texto, trocear, generar embeddings, indexar |
| `notificaciones` | Enviar correos de pagos, cotizaciones y contratos, con PDF adjunto |
| `reportes` | Generar reportes pesados y notificar al usuario cuando estén listos |

**Reglas:**
- La tarea de Celery es una cáscara delgada: recibe identificadores, llama a un
  servicio y maneja reintentos. La lógica vive en el servicio.
- Nunca se pasan objetos de Django como argumento, solo identificadores.
- Reintentos con retroceso exponencial, máximo 3 intentos.
- Toda tarea registra inicio y fin en la bitácora.

---

## 7. Agente de IA y RAG

```
Usuario → Endpoint del agente → Orquestador
                                   ├─ Herramientas sobre selectores (datos vivos)
                                   └─ Recuperador RAG (documentos)
                                           ↓
                                   Modelo de lenguaje
                                           ↓
                              Respuesta + citas + bitácora
```

- **Herramientas:** funciones que envuelven selectores existentes
  (`buscar_propiedades`, `consultar_disponibilidad`, `obtener_ficha_propiedad`).
  El agente nunca escribe SQL ni accede a modelos directamente.
- **Permisos:** el modo público solo accede a herramientas marcadas como
  públicas. El modo interno respeta los permisos del usuario autenticado.
- **RAG:** documentos troceados en fragmentos con solapamiento, embeddings
  almacenados en pgvector, búsqueda por similitud de coseno. La respuesta
  **siempre** cita documento y sección.
- Si no hay información suficiente, el agente lo dice. No inventa.

### Interfaz del proveedor de IA

**Proveedor elegido: Gemini Flash**, en su capa gratuita, que cubre tanto el
modelo conversacional como el de embeddings.

Pero el SDK de Gemini **solo puede importarse dentro de
`apps/ia/proveedores/`**. El resto del sistema conoce únicamente esta interfaz
abstracta:

```python
# apps/ia/proveedores/base.py
class ProveedorIA(ABC):
    @abstractmethod
    def generar_respuesta(
        self, *, mensajes: list[Mensaje], herramientas: list[Herramienta] | None = None
    ) -> RespuestaIA:
        """Respuesta del modelo, con las llamadas a herramientas que solicite."""

    @abstractmethod
    def generar_embedding(self, *, texto: str) -> list[float]:
        """Vector del texto, para indexar o para consultar el RAG."""

    @abstractmethod
    def generar_embeddings_lote(self, *, textos: list[str]) -> list[list[float]]:
        """Versión por lotes, para la ingesta de documentos."""
```

`apps/ia/proveedores/gemini.py` implementa esta interfaz y una fábrica la
instancia según la variable `IA_PROVEEDOR`. Cambiar de proveedor es un archivo
nuevo y una variable de entorno, nunca una reescritura.

**Advertencia sobre la capa gratuita:** el contenido enviado se usa para
mejorar los productos de Google. Para este proyecto, con datos de demostración,
no es un problema, pero **no se envían datos personales reales** y conviene
tenerlo documentado para la defensa.

**Dimensión de los embeddings:** se fija en `IA_DIMENSION_EMBEDDINGS` y debe
coincidir con la del campo `vector` en `FragmentoRAG`. Cambiar de modelo de
embeddings obliga a reindexar todo; no es una decisión reversible sin costo.

---

## 8. Reportería

```
selectors.py  →  servicio del reporte  →  exportador (Excel | PDF)
```

Cada reporte es una función en `apps/reportes/` que recibe filtros tipados y
devuelve una estructura de datos. Los exportadores son genéricos: reciben esa
estructura y producen el archivo. **Un reporte nuevo no debe requerir tocar los
exportadores.** Detalle en `docs/reportes.md`.

---

## 9. Seguridad

- Contraseñas con los validadores de Django, mínimo 10 caracteres.
- Roles: administrador, gerente, agente de ventas, contabilidad, consulta.
- Permisos por objeto donde aplique: un agente solo ve su cartera.
- Límite de peticiones en los endpoints del agente de IA y de autenticación.
- Documentos oficiales en almacenamiento de objetos, con URLs firmadas y
  temporales. Nunca servidos directamente desde el sistema de archivos.
- CORS restringido al dominio del frontend.
- Variables de entorno para todo secreto. `DEBUG = False` en producción.

---

## 10. Pruebas

Prioridad, de mayor a menor:

1. **Servicios.** Es donde viven las reglas de negocio. Cobertura mínima 70 %.
2. **Selectores.** Que los filtros y agregaciones den los números correctos.
3. **API.** Un caso feliz y uno de error por endpoint crítico.

`pytest` con `pytest-django` y `factory-boy`. Las pruebas corren contra
PostgreSQL, no contra SQLite.
