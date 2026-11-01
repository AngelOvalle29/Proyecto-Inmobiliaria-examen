# Estado del bloque D · Nathaly

Inspección del 2026-10-31 sobre `develop` en `3113a76`, con `git fetch origin`
y lectura de issues/PRs de GitHub. Describe código versionado, no una prueba de
funcionamiento local ni de producción.

## Repositorio y documentación

- La copia local coincidía con `origin/develop`: 0 commits por delante y 0 por
  detrás; no había cambios locales antes de preparar estos documentos.
- `origin/main` estaba en `4cc4016`; comparación `main...develop`: 2 commits
  exclusivos de main y 74 de develop. Las ramas divergen: no basta con contar
  commits para afirmar qué está desplegado. El PR de release #53 sigue abierto.
- La spec 014 está en el PR #57, todavía abierto; por eso se proponen 015/016.
- README describe el alcance objetivo, no una lista de funcionalidades terminadas.
  `CLAUDE.md` y el roadmap conservan textos de arranque de fases ya realizadas.
- `docs/requisitos.md` sigue marcando toda la rúbrica como pendiente;
  `docs/reportes.md` enumera 18 candidatos para un mínimo de 15. El roadmap
  recortó correo a opcional y priorizó una ingesta real por RabbitMQ.

## Evidencia y siguiente entrega

| Área / issue | Lo que existe | Lo que falta / siguiente paso |
|---|---|---|
| Auditoría base | Modelo inmutable, servicio explícito, migración y admin de solo lectura | Consulta REST y pantalla aún son esqueletos; no confundir con ausencia de registros |
| Bitácora IA [#23](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/23) | Campos acordados en arquitectura, dependencia declarada por spec 005 | Aprobar spec 015; luego modelo/servicio e integración con C |
| Reportes [#24](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/24) | Catálogo funcional documentado, app vacía | Aprobar spec 016; infraestructura y R05/R16/R17, después completar al menos 15 |
| Mensajería [#25](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/25) | Celery configurado, tarea de diagnóstico y arranque del worker | Spec de ingesta con C; el diagnóstico no satisface el flujo de negocio |
| Power BI [#26](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/26) | Diseño del esquema `bi` en documentación | Spec, migración de vistas, usuario de solo lectura, tablero y `.pbix` |
| Evidencia personal [#27](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/27) | §11 de spec 001 describe generación y revisión de otros integrantes | Nathaly documenta qué leyó, entendió y corrigió; no se puede afirmar esa revisión por ella |

## Dependencias que hay que resolver

- **Reportes históricos:** R03 necesita tiempos por etapa; R06 antigüedad y
  corte histórico; R07 adquisición; esos datos no deben inferirse de
  `actualizado_en` como si fuera la fecha del evento. Acordar fórmula o reducir
  alcance explícitamente en una spec revisada.
- **Flujo de ingresos R12 / hechos de cobros:** `CuotaPago` conserva monto
  acumulado y fecha/tasa del último pago, no cada abono. No permite distribuir
  cobros parciales de meses distintos fielmente. Coordinar con B antes de
  definir el reporte y el grano de `bi.hechos_cobros`.
- **Compras/construcción:** sus modelos y servicios siguen como esqueletos en
  develop; R09, R13 y R15 dependen del bloque C.
- **Ingesta:** spec 005 propone Markdown y `indexar_documento(documento_id=...)`;
  documentos oficiales de spec 011 aceptan PDF/JPG/PNG. Acordar con C la fuente
  del primer flujo: no prometer extracción de esos archivos sin diseñarla.
  La spec debe contemplar publicación después del commit, versiones,
  idempotencia, reintentos y evidencia de inicio/fin en base de datos.
- **Power BI inicial:** proponer cuatro vistas sobre ventas ya existentes:
  `hechos_ventas`, `dim_tiempo`, `dim_propiedad` y `dim_agente`, con llaves
  concordantes y `monto_total_usd` ya guardado. Es una propuesta pendiente de
  aprobación. Usar credenciales de solo lectura y verificar permisos negativos.

## Orden de trabajo propuesto

1. Revisar y aprobar 015 con C para desbloquear el registro del agente.
2. Revisar y aprobar 016; implementar exportadores y tres reportes verificables.
3. Redactar la spec de ingesta con el contrato de C y el worker de A.
4. Acordar el conjunto de al menos 15 reportes y las fórmulas pendientes con B/C.
5. Especificar las cuatro vistas iniciales y crear un tablero conectado.

Los borradores se publicaron en `docs/015-016-bloque-d` mediante el commit
`f1e1a26` y el [PR #61](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/61).
Nathaly solicitó la revisión y ejecución del commit al agente. Eso describe
lo ocurrido; **no existe una excepción aprobada por el equipo** a
`docs/convenciones.md` §5. La política de commits queda para discusión conjunta,
sin modificarla mediante este PR.

La revisión solicita confirmar con Angel el contrato de la bitácora y completar
la revisión personal de Nathaly en §11. Ambos puntos siguen pendientes de las
respuestas correspondientes. Los permisos y la separación entre paginación y
exportación se ajustaron en la spec 016 y en `docs/reportes.md`. No se
implementó código y no se consideran aprobadas las specs.
