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
| Bitácora IA [#23](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/23) | Spec 015 aprobada y contrato confirmado con C | Implementar modelo/servicio y después conectar IA |
| Reportes [#24](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/24) | Spec 016 aprobada; app aún sin implementación | Infraestructura y R05/R16/R17, después completar al menos 15 |
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

1. Resolver con A el bloqueo de la previsualización de Vercel y fusionar el PR
   #61 siguiendo las convenciones; actualizar `develop` y crear la rama de 015.
2. Implementar y probar 015; después 016 con exportadores y tres reportes.
3. Redactar la spec de ingesta con el contrato de C y el worker de A.
4. Acordar el conjunto de al menos 15 reportes y las fórmulas pendientes con B/C.
5. Especificar las cuatro vistas iniciales y crear un tablero conectado.

Los borradores se publicaron en `docs/015-016-bloque-d` mediante el commit
`f1e1a26` y el [PR #61](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/61).
Nathaly solicitó la revisión y ejecución del commit al agente. Eso describe
lo ocurrido; **no existe una excepción aprobada por el equipo** a
`docs/convenciones.md` §5. La política de commits queda para discusión conjunta,
sin modificarla mediante este PR.

Angel confirmó directamente el contrato en el PR #61: `None` ante fallo sin
métricas, `0`/`0` si no se llamó al modelo, y una inserción sin `atomic()`
propio. También aprobó el PR sobre `dc258e5`. La integración desde su rama
`feature/005-agente-ia-rag` se conectará cuando la implementación esté en
`develop`. Las secciones 11 recogen la participación de Nathaly y el apoyo de
Codex de forma resumida. Los permisos y la separación entre paginación y
exportación se ajustaron en la spec 016 y en `docs/reportes.md`. No se
implementó código. El PR tiene aprobación de Angel y sigue pendiente de fusión
en el momento de esta actualización.

## Cierre de la sesión de especificaciones

- Los cambios de este bloque son solo documentación: no están implementados
  `LogAgenteIA`, los tres reportes ni sus exportadores.
- La rama estaba limpia y sincronizada con su remoto al iniciar la revisión
  de cierre; `origin/develop` seguía en `3113a76` después de `git fetch`.
- PR #61 abierto, sin conflictos de fusión y con aprobación de Angel sobre
  `dc258e5`. Los commits posteriores documentan la confirmación y actualizan
  el estado; la aprobación no se presenta como una nueva revisión de esos commits.
- La comprobación `Vercel` informa `Deployment was blocked`; no es evidencia
  de un error de código. A debe revisar el bloqueo de previsualización antes
  de la fusión; no se omiten comprobaciones ni se cambia el plan de Vercel.
- IA está en el PR #62 y proveedores/constructoras en el #63, abiertos: esas
  implementaciones todavía no forman parte de `develop`.
- Los issues #23–#27 siguen abiertos. No se cierran por aprobar specs: aún
  faltan implementación, pruebas, integración y evidencia para la defensa.

Para la próxima sesión: retomar 015 en `feature/015-bitacora-agente-ia`, desde
`develop` actualizado después de fusionar las specs, y verificar el contrato
con la rama de IA. El entorno y las pruebas de aplicación se comprobarán al
implementar; en esta sesión solo se revisó documentación y estado de GitHub.
