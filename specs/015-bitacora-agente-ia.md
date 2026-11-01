# 015 · Bitácora del agente de IA

| Campo | Valor |
|---|---|
| **Número** | 015 |
| **Estado** | Borrador |
| **Autor** | Nathaly Saraí Reyes Cifuentes (rol D), con apoyo de Codex |
| **Revisor** | Por asignar; coordinar el contrato con AngelOvalle29 (rol C) |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `auditoria` |
| **Rama** | Documentación: `docs/015-016-bloque-d`; implementación propuesta: `feature/015-bitacora-agente-ia` |
| **Pull request** | [#61](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/61); issue [#23](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/23) |

## 1. Problema

El sistema registra operaciones comerciales, pero aún no puede guardar qué
preguntó un usuario al agente, qué fuentes utilizó ni si falló. El rol C
necesita un servicio estable para registrar cada consulta (spec 005, §2 y §6).

## 2. Alcance

**Incluye:** modelo `LogAgenteIA`, enumeración de modo, servicio de inserción,
una migración, consulta de solo lectura en Django admin y pruebas.

**No incluye:** modificar la respuesta del agente ni llamar a Gemini (rol C,
spec 005); endpoints y pantalla de consulta de bitácoras (spec posterior).
El registro efectivo desde IA se integra con C cuando su servicio exista.

## 3. Reglas de negocio

1. Cada consulta terminada registra pregunta, respuesta, fuentes, herramientas,
   tokens, duración y resultado. También se registran fallos del proveedor.
2. `usuario` puede ser nulo para consultas públicas. `modo` acepta `PUBLICO`
   o `INTERNO`; guardar este último no habilita el modo interno del agente.
3. Los registros son de solo inserción, como `LogAuditoria`: se impiden
   `save()` sobre un registro existente y `delete()`. Ningún código usa
   `QuerySet.update()` ni `QuerySet.delete()` sobre la tabla. Esto no pretende
   impedir cambios de un administrador con acceso SQL directo.
4. Tokens y duración no pueden ser negativos. Las listas vacías son válidas
   cuando no se invocaron herramientas o no se recuperaron documentos.
   Propuesta a acordar con C: tokens nulos cuando el proveedor no los informa;
   cero solo cuando se conoce que no hubo consumo.
5. `exito=False` conserva un diagnóstico controlado, sin credenciales ni
   respuestas HTTP completas del proveedor. No se guarda una excepción cruda.
   Propuesta: exige `error` no vacío; con `exito=True`, `error` queda vacío.
6. No se abre una transacción alrededor de la llamada de red. C registra el
   fallo fuera de cualquier transacción de negocio que se haya revertido.
7. `auditoria` no importa otras apps: usuario mediante `AUTH_USER_MODEL` y
   anotación `AbstractBaseUser`, fuentes y herramientas como JSON.

## 4. Modelo de datos

`LogAgenteIA(models.Model)`, tabla `auditoria_log_agente`; no hereda
`ModeloBase`, porque los registros no se editan ni se desactivan.

| Campo | Tipo y regla |
|---|---|
| `id` | PK automática |
| `usuario` | FK a `settings.AUTH_USER_MODEL`, nula, `PROTECT` |
| `modo` | CharField(10), choices `PUBLICO`, `INTERNO` |
| `pregunta`, `respuesta` | TextField; respuesta vacía permitida ante fallo |
| `herramientas_invocadas` | JSONField, `default=list`; elementos con `nombre` y `argumentos` |
| `documentos_recuperados` | JSONField, `default=list`; elementos con `documento_id`, `fragmento_id`, `seccion` y `distancia` de coseno |
| `tokens_entrada`, `tokens_salida` | PositiveIntegerField, nulos si el dato es desconocido |
| `duracion_ms` | PositiveIntegerField |
| `exito` | BooleanField, obligatorio |
| `error` | TextField, vacío por defecto |
| `fecha` | DateTimeField, `auto_now_add=True` |

Orden `-fecha, -id`; índice por fecha. La forma del JSON y la disponibilidad
del consumo de tokens quedan pendientes de confirmación con C antes de aprobar.

## 5. API

Sin endpoints nuevos: el productor llama al servicio Python. No se expone
una API pública para insertar o consultar preguntas y respuestas.

Contrato de ejemplo: consulta pública sin fuentes suficientes → usuario nulo,
modo `PUBLICO`, respuesta indicando falta de información, lista de fuentes
vacía y `exito=True`. Un fallo del proveedor usa `exito=False`.

Errores de entrada del servicio: `django.core.exceptions.ValidationError` si
modo, listas o contadores son inválidos. No se usa la excepción de DRF porque
el servicio no depende de HTTP. Esta spec no publica endpoints.

## 6. Servicios y selectores

Firma propuesta de `registrar_consulta_agente`, con argumentos solo por nombre:

| Argumento | Tipo |
|---|---|
| `usuario` | `AbstractBaseUser` o `None` |
| `modo` | `str` validado contra la enumeración |
| `pregunta`, `respuesta` | `str` |
| `herramientas_invocadas`, `documentos_recuperados` | `list[dict]` |
| `tokens_entrada`, `tokens_salida` | `int` o `None` |
| `duracion_ms` | `int` |
| `exito` | `bool` |
| `error` | `str`, por defecto vacío |

Devuelve `LogAgenteIA`. Valida y realiza una inserción; no llama al proveedor.
La validación se ejecuta explícitamente: `objects.create()` no llama a
`full_clean()` automáticamente. Se rechazan booleanos como contadores, aunque
Python los considere enteros.
No requiere selector público en este incremento.

**Contrato propuesto a C, pendiente de confirmación en el PR #61:**

```python
def registrar_consulta_agente(
    *,
    usuario: AbstractBaseUser | None,
    modo: str,
    pregunta: str,
    respuesta: str,
    herramientas_invocadas: list[dict],
    documentos_recuperados: list[dict],
    tokens_entrada: int | None,
    tokens_salida: int | None,
    duracion_ms: int,
    exito: bool,
    error: str = "",
) -> LogAgenteIA: ...
```

Ejemplo de las listas JSON con datos ficticios:

```json
{
  "herramientas_invocadas": [{"nombre": "buscar_propiedades", "argumentos": {"pais_id": 1}}],
  "documentos_recuperados": [{"documento_id": 1, "fragmento_id": 2, "seccion": "Requisitos", "distancia": 0.24}]
}
```

`distancia` es distancia de coseno, no similitud: menor significa más cercano.
Ambas listas pueden estar vacías. Tokens `None` significa consumo desconocido;
`0` solo se usa si se conoce que no hubo consumo. Angel debe confirmar firma,
claves JSON y manejo de tokens en el PR; hasta entonces no se da por resuelta
la coordinación ni por aprobada esta spec.

## 7. Auditoría

La inserción es la evidencia de la consulta; no genera otra entrada en
`LogAuditoria` por cada log. La auditoría de documentos de IA sigue en la spec
005 y usa `registrar_auditoria`.

## 8. Criterios de aceptación

- [ ] Se crea la tabla mediante una migración nueva sin editar la 0001.
- [ ] Se guardan consultas públicas, autenticadas, sin información y fallidas.
- [ ] Se distingue consumo desconocido de consumo cero.
- [ ] Actualizar o borrar por el modelo falla; admin no permite altas ni cambios.
- [ ] Contadores negativos y modos inválidos son rechazados.
- [ ] C confirma la firma y el formato JSON para integrarlos en la spec 005.
- [ ] Pasan ruff, comprobación de migraciones y pruebas contra PostgreSQL.

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Modelo | Inmutabilidad, fecha automática, FK protegida y contadores |
| Servicio | Todos los campos, usuario nulo, listas independientes y validación |
| Admin | Sin permisos de alta, edición ni borrado |
| Integración con C, posterior | Una consulta y un fallo producen exactamente un log cada uno |

## 10. Decisiones y alternativas descartadas

- Se replica el patrón explícito de `LogAuditoria` para poder explicarlo y no
  introducir señales ni nuevas dependencias.
- Fuentes como JSON evitan que `auditoria` dependa de los modelos de `ia`.
- La integración se entrega en coordinación con C: crear la tabla por sí solo
  no demuestra que las consultas reales estén auditadas.

## 11. Trabajo con agentes de IA

Sesión 2026-10-31: Codex inspeccionó el modelo y servicio de auditoría, la spec
005 y el issue #23, y redactó este borrador. No se implementó código ni se
afirma aprobación, ejecución de pruebas o revisión personal de la estudiante.
La revisión personal de Nathaly sigue pendiente de confirmación. El resumen
para su revisión es: la bitácora solo admite inserciones; guardar fuentes como
JSON evita depender de modelos de IA; tokens nulos no significan cero consumo.
Este resumen fue redactado por Codex y no acredita que la estudiante ya lo
haya leído o pueda explicarlo.

Revisión técnica posterior de Codex, solicitada por Nathaly: se aclaró la
validación explícita antes de insertar y la coherencia entre `exito` y `error`.
Nathaly autorizó al agente a ejecutar el commit de documentación; esto no
equivale a la aprobación de otro integrante ni acredita su revisión personal.

Tras la revisión del PR #61, Nathaly pidió resolver los comentarios con apoyo
de Codex. Se explicitó la excepción de Django y el contrato propuesto a C.
No se afirma que el equipo haya aprobado una excepción sobre commits.
