# 015 · Bitácora del agente de IA

| Campo | Valor |
|---|---|
| **Número** | 015 |
| **Estado** | Implementada; el agente la usa desde #62 |
| **Autor** | Nathaly Saraí Reyes Cifuentes (rol D), con apoyo de Codex |
| **Revisor** | AngelOvalle29 (rol C), aprobación del PR #61 sobre `dc258e5` |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `auditoria` |
| **Rama** | `feature/015-bitacora-agente-ia`, desde `develop` con las specs fusionadas |
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
   C enviará los tokens de la respuesta del modelo, sin contar embeddings.
   Si no hay fragmentos y no se llama al modelo, enviará `0` y `0`.
   Si Gemini falla sin reportar métricas, enviará `None` en ambos contadores,
   según la confirmación de C en el PR #61. Un fallo sin métricas no se
   contabiliza como una consulta con consumo cero.
5. `exito=False` conserva un diagnóstico controlado, sin credenciales ni
   respuestas HTTP completas del proveedor. No se guarda una excepción cruda.
   Exige `error` no vacío; con `exito=True`, `error` queda vacío.
6. No se abre una transacción alrededor de la llamada de red. C registra el
   fallo fuera de cualquier transacción de negocio que se haya revertido.
   `registrar_consulta_agente` no abre un bloque `transaction.atomic()` propio:
   valida y hace una única inserción, confirmada por autocommit en el flujo
   público actual. Si el llamador abre una transacción, la inserción pertenece
   a ella y puede revertirse; el servicio no crea una transacción independiente.
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
| `documentos_recuperados` | JSONField, `default=list`; elementos con `documento_id`, `fragmento_id`, `documento` (título), `seccion` y `distancia` de coseno |
| `tokens_entrada`, `tokens_salida` | PositiveIntegerField, nulos si el dato es desconocido |
| `duracion_ms` | PositiveIntegerField |
| `exito` | BooleanField, obligatorio |
| `error` | TextField, vacío por defecto |
| `fecha` | DateTimeField, `auto_now_add=True` |

Orden `-fecha, -id`; índice por fecha. Contrato confirmado directamente por
Angel en el [comentario del PR #61](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/61#issuecomment-6552947911),
incluido el caso de fallo sin métricas.

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

Firma de `registrar_consulta_agente`, con argumentos solo por nombre:

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

**Contrato de integración confirmado por C en el PR #61:**

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
  "herramientas_invocadas": [],
  "documentos_recuperados": [{"fragmento_id": 12, "documento_id": 3, "documento": "Manual de procesos de venta", "seccion": "Compras con financiamiento", "distancia": 0.23}]
}
```

`distancia` es distancia de coseno, no similitud: menor significa más cercano.
Ambas listas pueden estar vacías. Cuando existan herramientas, sus elementos
tendrán `nombre` y `argumentos`; por ahora C enviará `[]`.

Según el mensaje de Angel compartido por Nathaly, llama
`responder_consulta_publica` en `apps/ia/services.py` exactamente una vez al
terminar cada pregunta, con éxito o fallo. Envía usuario `None`, modo `PUBLICO`,
pregunta de 3 a 500 caracteres y, si falla, respuesta vacía, `exito=False` y
error controlado; el usuario recibe 503. `ia` importa el servicio de `auditoria`,
sin dependencia inversa. Los tokens son los de la respuesta de Gemini; los
embeddings no se cuentan. Sin fragmentos ni llamada al modelo usa `0`/`0`.

Angel confirmó en el PR que ante un fallo sin métricas enviará `None` en
ambos contadores. También aceptó el manejo de transacciones de la regla 6:
una inserción sin `atomic()` propio. El punto de llamada está marcado en su
rama `feature/005-agente-ia-rag` y se conectará cuando esta implementación
esté en `develop`; la integración aún no está ejecutada ni probada.

## 7. Auditoría

La inserción es la evidencia de la consulta; no genera otra entrada en
`LogAuditoria` por cada log. La auditoría de documentos de IA sigue en la spec
005 y usa `registrar_auditoria`.

## 8. Criterios de aceptación

- [x] Se crea la tabla mediante una migración nueva sin editar la 0001.
- [x] Se guardan consultas públicas, autenticadas, sin información y fallidas.
- [x] Se distingue consumo desconocido de consumo cero.
- [x] Actualizar o borrar por el modelo falla; admin no permite altas ni cambios.
- [x] Contadores negativos y modos inválidos son rechazados.
- [x] C confirma en el PR el contrato, incluido el caso de fallo sin métricas.
- [ ] Se verifica el mismo contrato en la spec 005 y la integración al implementar.
- [x] Pasan ruff, comprobación de migraciones y pruebas contra PostgreSQL.

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

Se utilizó Codex para revisar arquitectura §5, la app `auditoria`, la spec 005
y el issue #23, y preparar el borrador. Nathaly revisó el propósito de esta
etapa y explicó que primero se define lo que se hará, antes de implementar.

A partir de la revisión del PR #61 se precisaron la validación de Django y el
contrato del servicio. Nathaly aportó el mensaje de Angel para ajustar el JSON,
el alcance del conteo de tokens y el punto de llamada desde IA; se documentó
también la respuesta sobre transacciones. La entrega contiene especificación,
sin implementación ni pruebas de aplicación. La revisión técnica del equipo
y los acuerdos restantes se registran en el PR.

Angel confirmó directamente el contrato y los tokens desconocidos en el PR
#61 y registró su aprobación sobre `dc258e5`. Esta actualización incorpora esa
confirmación; no acredita implementación ni pruebas de integración.

### Implementación de auditoría (2026-10-31)

Con apoyo de Codex se implementaron `ModoAgente`, `LogAgenteIA`, el servicio
`registrar_consulta_agente`, la migración `0002_log_agente_ia`, el admin de solo
lectura y las pruebas. No se agregó ninguna dependencia ni se modificó `ia`.

La validación del servicio rechaza contadores negativos, booleanos usados como
números, modos inválidos, JSON fuera del contrato y resultados incoherentes.
El modelo fuerza INSERT para que incluso otra instancia con el mismo ID no
pueda sobrescribir un log; esta protección no sustituye las restricciones ya
documentadas sobre operaciones directas de QuerySet o SQL.

Para explicar el flujo: el servicio valida tipos, construye el registro,
ejecuta `full_clean()` y lo inserta. No llama a Gemini ni abre `atomic()`: la
transacción pertenece al llamador. Los fallos se registran después de revertir
cualquier transacción de negocio fallida. El admin permite consultar evidencia,
sin crearla o modificarla manualmente.

Verificación con Python 3.12 y PostgreSQL 16 + pgvector en contenedores aislados:
ruff y comprobación de migraciones correctos; `manage.py check` sin problemas;
43 pruebas de auditoría correctas y suite completa con **557 pruebas correctas**
en 58.16 segundos. La conexión desde `responder_consulta_publica` se hará con C
cuando este servicio esté fusionado; no se presenta como integración ya probada.
