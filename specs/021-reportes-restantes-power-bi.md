# 021 · Completar quince reportes e integrar Power BI

| Campo | Valor |
|---|---|
| **Número** | 021, propuesto; coordinar antes de abrir el PR |
| **Estado** | Borrador para revisión del equipo; no autoriza implementación |
| **Autor** | Propuesta para Nathaly Saraí Reyes Cifuentes (rol D), con apoyo de Codex |
| **Revisor** | Por asignar: A para catálogo/BI, B para comercial y C para compras/construcción |
| **Fecha** | 2026-11-01 |
| **Apps afectadas** | `reportes`; lecturas de `catalogo`, `crm`, `ventas`, `arrendamientos`, `compras`, `construccion`, `core` y `auditoria` |
| **Rama** | Propuesta: `feature/021-reportes-restantes-power-bi`, desde `develop` con la 016 integrada |
| **Pull request** | [#78](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/78); avance de [#24](https://github.com/DouGMV/Proyecto-Inmobiliaria/issues/24) |

## 1. Problema

La spec 016 implementa localmente R05, R16 y R17. Falta integrar ese código,
completar al menos quince reportes exportables y entregar evidencia real de
Power BI. Una capa genérica o un script de vistas por sí solos no cumplen la
rúbrica: se necesitan resultados verificables y un archivo `.pbix` funcional.

Esta propuesta reutiliza la pantalla y exportadores de la 016. No cambia la
responsabilidad de mensajería: Douglas propuso asumirla en la spec 020; el
equipo debe confirmar ese reparto. No se modifica la ingesta del agente aquí.

## 2. Alcance

**Incluye:** doce reportes adicionales, permisos de cartera, vistas analíticas,
conexión de Power BI, cuatro vistas y un tablero comercial, datos ficticios
para demostración y explicación para defensa. Los quince propuestos son R01,
R02, R03, R04, R05, R06, R08, R10, R11, R12, R13, R14, R15, R16 y R17.

La selección y las precisiones de métricas de §3 son propuestas: requieren
aprobación. R07, R09 y R18 conservan su lugar en `docs/reportes.md`; se proponen
para otro incremento. No se borran del catálogo de diseño.

Se adopta para esta propuesta revisada el alcance de BI sugerido por A:
`bi.dim_tiempo`, `bi.dim_geografia`, `bi.dim_propiedad` y `bi.hechos_ventas`.
El tablero de portafolio y las otras dimensiones/hechos de §4 quedan como
ampliaciones. Se mantienen los quince reportes Excel/PDF y sus reglas, aunque
el reporte no tenga una vista BI en este incremento. El reparto de §10 es la
propuesta de coordinación de A; no se promete trabajo ni plazos por los demás.

**No incluye:** generación pesada con Celery, publicación pública de tableros,
licencias o servicios de pago, cambios a los ciclos comerciales, una pantalla
por reporte ni reconstrucción histórica ficticia. Un corte histórico que no
pueda justificarse con datos se rechaza; no se presenta el estado actual como
si fuera el de otra fecha.

**Dependencias:** integrar la 016. R13/R15 y sus vistas requieren los modelos,
migraciones y datos de la 017 integrados; no se crean copias locales de esos
modelos. La 017 ya fue aprobada en el PR #64; su implementación está en #75
(contratos de compra y proyectos) y #76 (pagos y cierre como Implementada).
Ambos PR de implementación siguen abiertos al comprobar esta revisión del
2026-11-01. Una vez fusionados, R13/R15 y sus vistas dejan de tener pendiente
esa dependencia de integración. No se cuentan R13/R15 como terminados antes
de implementarlos y verificarlos sobre esos modelos reales.

## 3. Reglas de negocio

### Reglas compartidas

1. Se conserva el contrato de la 016: JSON de 25 filas, orden estable con ID,
   totales de todo el filtro, Excel/PDF con el mismo conjunto y rechazo de
   exportaciones con más de 5,000 filas antes de materializar detalles.
2. Filtros tipados y estrictos. Fechas inclusivas en Guatemala. `fecha_corte`
   por defecto es hoy; los reportes de saldos y estado actual de este incremento
   solo aceptan hoy. Un corte distinto devuelve 400 `VALIDACION` con explicación.
   Las fechas de transacciones sí permiten intervalos históricos.
3. Importes exactos con `Decimal`; totales separados por moneda original.
   Los montos USD históricos usan la tasa guardada en cada transacción. No se
   aplica la tasa del último pago a todos los abonos anteriores ni se cambia
   el pasado con la tasa de hoy. Una tasa faltante no se sustituye por 1.
4. No se unen a la vez cuotas, rentas y cotizaciones para sumar: se agregan
   por separado antes de relacionarlas, evitando multiplicación de filas.
5. Anulados y cancelados no aportan ventas, compras, cobros ni deuda. Los
   contratos terminados pueden conservar deuda exigible; no se descartan
   automáticamente sus pagos pendientes. Esto sigue las specs 007/008 y la
   corrección ya fusionada en el PR #70. Para saldos de cuotas en R04/R10/R11
   se filtra `contrato__estado=VIGENTE` en SQL: las cuotas de un contrato
   anulado pueden seguir en `PENDIENTE` y no constituyen deuda exigible.
6. R01/R02/R03/R04/R10/R11: administración, gerencia y contabilidad consultan
   el conjunto; agente solo su cartera, siguiendo los selectores de origen.
   La cartera se determina por el cliente, reutilizando
   `listar_contratos_visibles` y los selectores de clientes/cotizaciones,
   también en agregaciones. R02 añade una restricción: un agente ve solo su
   propia fila, sin mostrar números de otros agentes tras reasignar clientes.
   A propuesta de B, `CONSULTA` puede leer R01–R04, R10 y R11, coherente con
   su acceso a contratos y clientes; pendiente de aprobación global de la spec.
7. R06/R08/R14: todos los roles autenticados, con las restricciones de lectura
   que ya imponga catálogo. R12/R13/R15: administración, gerencia y contabilidad.
   R05/R16/R17 mantienen sus permisos aprobados. Un agente no puede ampliar
   su cartera enviando otro `agente` o `cliente`, ni inferirla en los totales.

### Contrato de los doce reportes nuevos

Los slugs de esta tabla son los identificadores de API. Cada fila necesita
detalle, filtros y agregación; no cuenta como reporte una tarjeta de conteo.

| Código y slug | Grano y columnas principales | Filtros | Agregaciones |
|---|---|---|---|
| R01 `ventas-por-periodo` | Contrato: código, firma, cliente, agente, bien, país, ciudad, modalidad, moneda, neto, bruto/descuento documentados y comisión | Firma desde/hasta, país, ciudad, agente, tipo, modalidad, moneda | Cantidad, neto y comisión por mes/país/moneda; bruto y descuento solo de la población con evidencia |
| R02 `desempeno-agentes` | Agente: cotizaciones emitidas/aprobadas, contratos vinculados, ventas sin cotización, conversión, monto vendido y comisión | Emisión desde/hasta, país, agente | Conteos y montos por agente/moneda; conversión ponderada global |
| R03 `embudo-cotizaciones` | Cotización: código, emisión, cliente, agente, estado actual, vencida, total, moneda y contrato vinculado | Emisión desde/hasta, agente, país, estado, moneda, monto mínimo/máximo | Conteos por estado, tasas de la cohorte y tiempos por etapa desde auditoría; sin sumar porcentajes |
| R04 `ranking-clientes` | Cliente: código/nombre comercial, contratos de venta, arrendamientos vigentes, vendido USD y saldos por moneda | Firma de venta desde/hasta, país del cliente, tipo de cliente | Ranking por vendido USD descendente y cliente ID; conteos y saldos de la población |
| R06 `propiedades-por-estado` | Bien `(origen,id)`: código, propiedad, tipo, ciudad, estado actual, fecha de entrada conocida y días en estado | País, ciudad, tipo, estado, corte hoy | Conteos por estado/tipo; antigüedad media solo de fechas conocidas y cantidad sin historia |
| R08 `evolucion-avaluos` | Avalúo: propiedad, fecha, perito, valor, moneda, anterior comparable y variación | Propiedad, país, fechas, moneda | Cantidad, primera/última valuación por propiedad/moneda y variación comparable |
| R10 `estado-cuenta-clientes` | Obligación `(origen,id)`: cliente, contrato, número/período, vencimiento, moneda, exigible, pagado, saldo y mora actual | Cliente, vencimiento desde/hasta, estado, agente, moneda, corte hoy | Exigible/pagado/saldo por cliente/origen/moneda |
| R11 `morosidad` | Obligación vencida: cliente, contrato, origen, vencimiento, días de atraso, tramo, moneda y saldo | País del bien, agente, moneda, saldo mínimo/máximo, corte hoy | Conteo y saldo por tramo 1–30, 31–60, 61–90 y más de 90 días |
| R12 `flujo-ingresos` | Cobro identificado: origen, ID fuente, contrato, fecha efectiva, moneda, recibido, tasa y USD | Pago desde/hasta, país del bien, origen, moneda | Cobros por mes/origen/moneda y consolidado USD; conciliación por fuente |
| R13 `compras-proveedores` | Contrato de compra completado: proveedor, propiedad, fecha, moneda, monto, gastos, impuestos, costo total y USD | Compra desde/hasta, proveedor, país de la propiedad, moneda | Cantidad y componentes del costo por proveedor/mes/moneda; costo USD |
| R14 `ocupacion-arrendamientos` | Propiedad: ciudad, tipo, bienes elegibles, arrendados, disponibles, otros estados, ocupación e ingreso recurrente por moneda | País, ciudad, tipo, corte hoy | Ocupación ponderada global y por ciudad; ingreso recurrente por moneda |
| R15 `avance-presupuesto-obra` | Proyecto: constructora, propiedad, fechas, estado, moneda, presupuesto, programado, pagado, total comprometido, disponible, saldo por pagar, avance físico y financiero | Constructora, estado, país, inicio desde/hasta, moneda, corte hoy | Presupuesto/programado/pagado/comprometido/disponible/saldo por constructora y moneda; pagos realizados USD y desviación de fechas |

### Precisiones de cálculo que se someten a revisión

8. R01: neto es `monto_total`; comisión es la guardada. Con cotización,
   bruto/precio y descuento salen de ella. Sin cotización, esos dos datos son
   desconocidos: no se inventa descuento cero. Se informa la cobertura.
9. R02/R03 agrupan por `fecha_emision` en el intervalo. R02 no cuenta como
   emitidas las cotizaciones en `BORRADOR`; R03 sí las muestra como primera
   etapa. Conversión a contrato = cotizaciones de la cohorte con contrato no
   anulado / total de la cohorte del reporte × 100. Denominador cero produce
   `null`. Las ventas directas se muestran aparte y no inflan esa conversión.
   R02 distingue ventas por fecha de firma de las conversiones de la cohorte.
10. R03 calcula tiempos por etapa desde los registros de creación, envío,
    aprobación y rechazo en auditoría, ordenados por `(fecha,id)`. El tiempo
    de una etapa cerrada es la diferencia entre entrada y siguiente transición;
    la media incluye solo duraciones documentadas, con su conteo de cobertura.
    La etapa abierta se informa aparte y no se mezcla en la media de cerradas.
    Sin eventos suficientes se informa «sin historial», nunca duración cero.
    Si se acuerda recortar esta métrica por plazo, se registra expresamente
    antes de considerar completo R03.
11. R04: el ranking usa ventas USD, no mezcla precio de venta con renta
    mensual. Saldos y arrendamientos son actuales y se etiquetan así; el
    intervalo filtra ventas. Esta precisión del «monto total transado» del
    catálogo fue aceptada por B en su revisión del PR #78. Sus saldos de renta
    incluyen solo obligaciones vencidas, conforme a la regla 14.
12. R06/R14 reutilizan la regla propiedad/unidad de R05: un edificio no se
    suma además de sus unidades activas. R06 obtiene la última transición
    documentada al estado actual; creación solo sirve si registra ese estado.
    Sin evidencia, fecha y antigüedad son `null`, no `actualizado_en`.
13. R08 calcula el avalúo anterior por propiedad y moneda con orden `(fecha,id)`
    antes de filtrar el período mostrado. Variación = `(nuevo/anterior - 1) ×
    100`; sin anterior o con anterior cero, `null`. No compara monedas distintas.
14. R04/R10/R11: saldo de cuota = total − pagado, solo para contrato `VIGENTE`;
    en R04/R10 se incluyen todas sus cuotas, también las futuras, porque la
    deuda fue firmada. Para rentas el saldo incluye solo las pendientes con
    `fecha_vencimiento < hoy`, por su monto programado sin recargo hipotético;
    no incluye los meses futuros ni el que vence hoy. Rentas pagadas/canceladas
    no tienen saldo. R11 incluye solo obligaciones vencidas. Mora empieza el
    día posterior al vencimiento, también en rentas:
    la gracia afecta el recargo al cobrar, no la clasificación, según spec 008.
    No se suman enganche ni precio total otra vez a la deuda de cuotas.
15. R12: cada abono de cuota se obtiene del log inmutable del pago, que guarda
    `pago`, `fecha` y `tasa_a_usd` (spec 007), con ID del log como identidad.
    No se usa `monto_pagado` con `fecha_ultimo_pago`. Cada renta pagada aporta
    una fila por `monto_pagado`, que ya incluye el recargo: no se suma de nuevo.
    B confirmó incluir contado liquidado y enganche como cobrados en
    `fecha_firma`, con la tasa guardada del contrato y orígenes separados.
    El enganche de un contrato anulado no cuenta como cobro; tampoco sus cuotas.
    Depósitos de garantía no son ingreso. Si falta un log requerido o su tasa,
    el resultado no puede aparentar estar completo: 409 `DATOS_INCOMPLETOS`,
    diagnóstico sin datos sensibles y conciliación con los acumulados.
16. R13 incluye `COMPLETADO`; `EN_PROCESO` no se presenta como adquisición
    realizada. Su filtro de país se aplica al país de la propiedad adquirida,
    no al del proveedor. R15 suma cada pago `PAGADO` una vez; anulado aporta
    cero. Usa las definiciones del detalle de proyecto de la 017:
    `total_comprometido = programado + pagado` y
    `disponible = presupuesto − total_comprometido`, reutilizando el selector
    `total_comprometido` de construcción. Saldo por pagar = presupuesto −
    pagado; se etiqueta por separado y no se confunde con disponible.
    Solo los pagos `PAGADO` tienen `tasa_a_usd` y `monto_usd`, guardados al
    pagar. El programado permanece en la moneda del proyecto y no se consolida
    en USD ni se convierte con la tasa del presupuesto. Comprometido y
    disponible también se presentan en la moneda del proyecto; el total USD
    de pagos realizados suma exclusivamente los `monto_usd` de pagos `PAGADO`.
    Avance financiero = pagado/presupuesto × 100 en moneda del proyecto;
    no es el avance físico. Desviación = fin
    real − fin estimada, o máximo(0, hoy − fin estimada) si sigue activo;
    cancelados no se califican como obra atrasada.
17. R14: denominador son todos los bienes activos elegibles del filtro;
    numerador son los de estado `ARRENDADA`. Disponible significa
    `DISPONIBLE`, no total menos arrendados. Denominador cero da `null`.
    Ingreso recurrente suma rentas de contratos que cubren hoy y no estén
    rescindidos a esa fecha; una renovación futura no duplica el contrato
    anterior. Un contrato `RENOVADO` se excluye si su `renovacion` está
    `RESCINDIDO`, incluso si sus fechas todavía cubren hoy: en ese caso el
    bien puede estar `DISPONIBLE`. B acepta renovados con esta exclusión.

## 4. Modelo de datos

No se agregan tablas de negocio. Una migración reversible de `reportes`
crea el esquema `bi` y vistas SQL explícitas; la reversión elimina solo las
vistas de este incremento. No modifica tablas de otras apps.
La migración depende de la última migración de cada app cuyas tablas lee:
se determina sobre `develop` integrado, sin inventar números de migraciones.
Quien cambie posteriormente el tipo de una columna o elimine una columna
usada por `bi` debe eliminar y recrear las vistas afectadas dentro de la misma
migración, con `RunSQL` y su reversa. La eliminación se hace en orden inverso
de dependencias y la recreación en orden directo; no se usa `CASCADE` para
borrar objetos ajenos. Se verifican tanto avance como reversión.

**Cuatro vistas de esta entrega:**

| Vista | Grano / clave |
|---|---|
| `bi.dim_tiempo` | Día / `fecha_id` entero AAAAMMDD |
| `bi.dim_geografia` | Ciudad / `ciudad_id`, país y región |
| `bi.dim_propiedad` | Bien / clave compuesta de origen y ID, propiedad padre y tipo |
| `bi.hechos_ventas` | Contrato no anulado / contrato ID, fecha firma, bien, ciudad, moneda, neto y USD |

`hechos_ventas.fecha_id` referencia `dim_tiempo`; su clave de bien referencia
`dim_propiedad` y su ciudad referencia `dim_geografia`. El tablero compara
ventas por mes, país, ciudad y tipo de propiedad, con monto USD y cantidad de
contratos. No necesita nombres de clientes ni una dimensión adicional de agente.

**Ampliaciones fuera de esta entrega:** se conservan las definiciones revisadas
por B/C para un incremento posterior, sin incluirlas en la migración actual.

| Vista futura | Grano / clave |
|---|---|
| `bi.dim_cliente` | Cliente / ID, código, tipo y país; sin documento, NIT, correo, teléfono ni dirección |
| `bi.dim_agente` | Agente / ID y código; sin credenciales ni correo |
| `bi.dim_constructora` | Constructora / ID y código |
| `bi.dim_proveedor` | Proveedor / ID y código; sin NIT ni correo |
| `bi.hechos_cobros` | Cobro / `(origen,id_fuente)`, fecha efectiva, contrato, moneda, recibido y USD; regla 15 |
| `bi.hechos_arrendamientos` | Mes de contrato / `(contrato_id,fecha_id)`; renta programada y USD, sin llamarla cobro; excluye pagos `CANCELADO` |
| `bi.hechos_compras` | Contrato completado / compra ID, fecha compra, bien, `proveedor_id` hacia `bi.dim_proveedor`, costo y USD |
| `bi.hechos_construccion` | Pago pagado / pago ID, fecha pago, proyecto, constructora, moneda, monto y USD |

Cada hecho tiene `fecha_id` y claves de sus dimensiones. Se incluirán
comprobaciones de claves únicas, importes y fechas. La migración actual crea
únicamente las cuatro vistas de esta entrega, sin vistas auxiliares que
amplíen el alcance. No se relacionan hechos
entre sí mediante uniones que dupliquen importes. `dim_tiempo` cubre todas las
fechas expuestas por hechos, incluso meses programados futuros.

En la ampliación, `bi.hechos_construccion` incluye exclusivamente pagos `PAGADO`, con su tasa y
`monto_usd` guardados al pagar. Los pagos `PROGRAMADO` no entran en este hecho
de pagos realizados ni se convierten a USD; R15 conserva sus importes en la
moneda del proyecto para comprometido y disponible.

La renta programada usa la tasa guardada del contrato; el cobro usa la del
pago. Se redondea cada hecho USD a centavos antes de sumar. Los montos
originales siempre conservan moneda. Estado y geografía actuales se indican
como actuales, sin afirmar dimensiones históricas que no están guardadas.

El rol PostgreSQL `powerbi_reader` se prepara fuera de Git mediante un script
documentado: solo conexión, `USAGE` en `bi` y `SELECT` sobre las cuatro vistas
de esta entrega, sin permisos de escritura ni lectura directa de tablas. No se
versiona su contraseña ni se amplían privilegios por defecto a objetos futuros.
La cuenta se prueba de verdad: una consulta de tabla operativa debe fallar.

Power BI Desktop usará Import para esta entrega. Se guardará
`docs/powerbi/inmobiliaria.pbix` con datos ficticios, relaciones de dimensión a
hechos, medidas y una página comercial (ventas mensuales, país, ciudad y tipo).
No se afirma actualización
programada en la nube sin configurarla y demostrarla. DirectQuery y los
tableros de portafolio/financiero/construcción quedan como ampliación.

La conexión de Power BI Desktop a Neon debe probarse antes de dar por cerrada
la integración, con SSL requerido y el rol de lectura creado en la consola de
Neon, fuera de Git. Se verifica despertar de la base, actualización y permisos.
La configuración de SSL del conector debe corresponder a la conexión segura
requerida por Neon; no se desactiva la validación para hacerla funcionar.
No se publica la cadena de conexión ni la contraseña en issues, PR, capturas
o el repositorio. La coordinación de acceso con A se hace por un medio privado.
Sin esa prueba real, el criterio de conexión permanece pendiente.

## 5. API

Se reutilizan las rutas y respuesta de la 016; los doce slugs están en §3.

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/api/v1/reportes/` | Catálogo paginado filtrado por rol |
| GET | `/api/v1/reportes/{slug}/` | JSON y agregados, con cartera |
| GET | `/api/v1/reportes/{slug}/excel/` | Mismos permisos y filtros |
| GET | `/api/v1/reportes/{slug}/pdf/` | Mismos permisos y filtros |

Ejemplo: `GET /api/v1/reportes/ventas-por-periodo/?fecha_desde=2026-10-01&fecha_hasta=2026-10-31&moneda=GTQ`.
La respuesta mantiene `titulo`, `subtitulo`, `generado_en`, `generado_por`,
`columnas`, `filas: {count,next,previous,results}`, `totales` y `agrupamientos`.
Cobertura desconocida se representa con `null` y conteos de cobertura,
no con números ficticios. La plantilla debe mostrar esos nulos como «Sin dato».

Errores: 400 `VALIDACION` y `REPORTE_DEMASIADO_GRANDE`; 401 sin JWT;
403 por rol; 404 para slug/página inexistentes o recurso ajeno conforme a los
selectores de origen; 409 `DATOS_INCOMPLETOS` para cobros sin evidencia necesaria.
No se exponen detalles de clientes ajenos en errores o agrupamientos.

## 6. Servicios y selectores

Extender los metadatos de `catalogo.py`, las dataclasses de filtros y los
serializadores de la 016. Añadir selectores explícitos por dominio, con tipos,
sin un motor dinámico de SQL ni nuevos paquetes.

```python
def resumir_reporte(*, slug: str, filtros: FiltrosReporte, usuario: AbstractBaseUser) -> ResumenReporte: ...
def seleccionar_filas_reporte(*, slug: str, filtros: FiltrosReporte, usuario: AbstractBaseUser, offset: int, limite: int) -> list[dict]: ...
def seleccionar_cobros(*, filtros: FiltrosCobros, usuario: AbstractBaseUser) -> QuerySet: ...
def verificar_integridad_cobros(*, filtros: FiltrosCobros, usuario: AbstractBaseUser) -> None: ...
```

El usuario se propaga a resumen y detalle: no basta con ocultar filas si los
totales siguen incluyendo otras carteras. Las firmas actuales de la 016 se
adaptan con sus pruebas, conservando sus permisos. Los exportadores reciben
`Reporte` y siguen sin consultar modelos. Los selectores aplican permisos antes
de contar, agregar y paginar. BI se valida con SQL de conciliación por fuente.
R15 reutiliza `total_comprometido` de los selectores de construcción de la 017
para coincidir con el detalle del proyecto, sin duplicar su regla de cálculo.

En el frontend el catálogo autorizado seguirá paginado: al superar 25 reportes
no se ocultarán silenciosamente las páginas siguientes. Para los quince de
esta entrega cabe una página; no se implementan doce pantallas nuevas.

## 7. Auditoría

Solo lecturas operativas; no se insertan ni alteran logs al generar reportes.
R12 lee únicamente eventos de pago con contrato definido por la spec 007;
no exporta JSON completos, IP, user-agent ni preguntas del agente.
La creación de vistas se evidencia en la migración, no en bitácoras falsas
atribuidas a un usuario de negocio.

## 8. Criterios de aceptación

- [ ] El equipo aprueba selección de quince, permisos y precisiones 8–17.
- [ ] La 016 está integrada y sus tres reportes siguen pasando las pruebas.
- [ ] Cada uno de los doce nuevos tiene detalle, filtros, agregados y ambas descargas.
- [ ] Catálogo, JSON, totales, Excel y PDF respetan la misma cartera.
- [ ] Los totales no cambian al pasar de página y coinciden en JSON/XLSX/PDF.
- [ ] No se suman monedas distintas ni se multiplican filas por relaciones.
- [ ] Los datos desconocidos se distinguen del cero y tienen cobertura explícita.
- [ ] Los dos abonos de una cuota en meses/tasas distintos caen en sus meses correctos.
- [ ] R13/R15 funcionan con los modelos y migraciones reales de la 017.
- [ ] R04/R10 no suman rentas futuras ni cuotas de contratos anulados; R11 solo muestra deuda vencida.
- [ ] R02 respeta la cartera por cliente, muestra al agente solo su fila y excluye borradores de emitidas.
- [ ] R14 excluye el contrato renovado cuya renovación fue rescindida, aunque sus fechas cubran hoy.
- [ ] R12 usa renta recibida con recargo una sola vez, y contado/enganche con tasa y fecha de firma.
- [ ] R13 filtra por país de la propiedad, aunque el proveedor sea de otro país.
- [ ] R15 coincide con el detalle de proyecto en comprometido y disponible; solo pagos `PAGADO` aportan USD.
- [ ] Vistas BI concilian claves, conteos y montos con los selectores de origen.
- [ ] `powerbi_reader` lee las vistas, pero no tablas operativas ni escribe.
- [ ] La migración crea solo las cuatro vistas, depende de las apps leídas y se puede revertir; cambios de columnas usados por BI recrean las vistas.
- [ ] Power BI Desktop conecta realmente a Neon con SSL y `powerbi_reader`.
- [ ] El `.pbix` se abre, actualiza desde PostgreSQL y filtra el tablero comercial.
- [ ] Hay capturas con datos ficticios y pasos de actualización sin contraseñas.
- [ ] Se prueban los quince reportes desde `/reportes`, incluidas sus 30 descargas.
- [ ] Pasan ruff, formato, migraciones, pytest, OpenAPI, lint, typecheck y build.
- [ ] Nathaly explica un reporte de principio a fin y las medidas del tablero.

## 9. Pruebas

| Nivel | Casos |
|---|---|
| Selectores | 0/1/muchas filas, rangos inclusivos, dos monedas, edificios/unidades, varias cuotas por contrato, cartera ajena |
| Métricas | Cohorte y venta directa, anterior de avalúo fuera del filtro, nulos, mora 0/1/30/31/60/61/90/91 días, renta rescindida pendiente |
| Cobros | Dos abonos en meses y tasas diferentes; contado, enganche y renta con recargo; log incompleto; conciliación sin duplicación |
| Comercial | Cliente reasignado y fila propia de R02; borradores distintos en R02/R03; tiempos documentados por transición; contrato de doce meses sin deuda de rentas futuras; cuotas anuladas excluidas; renovación rescindida antes de comenzar; contado/enganche por firma y renta sin duplicar recargo |
| Servicios/API | Matriz de cinco roles, filtros inválidos, páginas, totales completos, rechazo de 5,001 filas antes de cargar detalle |
| Exportación | Columnas y totales equivalentes, tipos XLSX, fórmulas literales, PDF multipágina, cobertura desconocida |
| Migración/SQL | Aplicar/revertir las cuatro vistas, dependencias de migraciones, cambio de columna con recreación reversible, unicidad de grano, claves a dimensiones, permisos reales y conciliación de ventas |
| Compras/construcción | Proveedor y propiedad de países distintos; comprometido/disponible iguales al detalle de la 017; programados sin tasa ni USD excluidos del total USD; pagados con su tasa histórica; dimensión de proveedor sin NIT/correo |
| Manual | Quince consultas, treinta descargas, filtros y errores visibles; conectar a Neon con SSL y rol de lectura; abrir/actualizar `.pbix`, segmentadores y cifras conciliadas |

## 10. Decisiones y alternativas descartadas

La infraestructura de la 016 se conserva para concentrar el trabajo en
consultas y reglas. Las precisiones anteriores no se consideran decisiones
de negocio aprobadas por estar escritas aquí: B valida comercial, A catálogo/BI
y C compras/construcción. No se implementan métricas ambiguas antes de resolverlas.

Se detectó que los abonos detallados sí están en la bitácora de ventas, aunque
la cuota solo conserve acumulado y último pago. Leer esos eventos evita crear
una segunda contabilidad y evita asignar todo el dinero al último mes.
B confirmó contado/enganche por fecha de firma y tasa del contrato; la
implementación comprobará la cobertura de logs indicada en regla 15.

Se propone Import para obtener una evidencia verificable en Desktop dentro
del alcance académico; no se promete un servicio publicado ni refresco en nube.
No se ofrece el `.pbix` como terminado hasta abrirlo y actualizarlo realmente.

Orden propuesto, sin comprometer fechas por otros integrantes:

1. Cerrar prueba manual, explicación y PR de la 016.
2. Revisar y aprobar esta spec, en particular las decisiones de §3.
3. Coordinar el reparto por dominio sobre la misma capa genérica:

   | Responsable propuesto por A | Reportes / tarea |
   |---|---|
   | B, Marco | R01, R02, R03, R04, R10, R11 |
   | C, Angel | R13, R15, sobre la implementación de la 017 |
   | A, Douglas | R06, R08, R14 |
   | D, Nathaly | R12, las cuatro vistas y Power BI; revisión del contrato de la 016 en todos los reportes |

4. Cada responsable entrega selectores, metadatos y pruebas de su bloque;
   coordinar cambios en catálogo/serializadores/servicios para evitar conflictos.
5. D concilia los quince reportes, sus treinta descargas y el tablero comercial.
   Probar la conexión segura a Neon temprano, antes de terminar el diseño visual.

Se adopta el recorte de BI propuesto por A, sin simplificar por ahora R12 ni
sus abonos históricos: asignar el acumulado al último mes daría resultados
incorrectos. Los tiempos por etapa de R03 permanecen como en la regla 10;
si B acuerda recortarlos por plazo, debe registrarse antes de cerrar su bloque.
No se considera que una simplificación esté aprobada por mencionarla como opción.

Son doce reportes adicionales propuestos, no doce terminados ni una promesa
confirmada para el lunes 2 de noviembre. Si el equipo divide implementación,
asignar reportes por selector y coordinar catálogo, permisos y migración.

## 11. Trabajo con agentes de IA

El 2026-11-01 Codex inspeccionó el trabajo local de la 016, los modelos y las
reglas de ventas/arrendamientos, los eventos de abonos, la rúbrica y la spec
017 en GitHub. Consultó las specs y PR abiertos: 018, 019 y 020 ya están
ocupados. Propuso 021, pendiente de coordinación.

La estudiante solicitó preparar una spec para revisión del equipo. Este
archivo es esa propuesta, sin implementación nueva, aprobación, commit ni
garantía de plazo. Se explicitan las métricas que no deben inferirse de campos
insuficientes. La validación de la 016 se registra en su documento propio.

### Ajustes a la revisión del integrante C

Nathaly trasladó cinco observaciones de Angel sobre R13, R15 y sus hechos BI.
Se añadió `bi.dim_proveedor`, se precisó el país de la propiedad para R13,
se alinearon comprometido y disponible con el selector de construcción y
se limitó el USD a pagos realizados. Se corrigió además el estado de la 017:
aprobada en #64, con implementación en #75/#76 todavía pendiente de fusión
al consultar GitHub en esta sesión. Los criterios y casos de prueba reflejan
los ajustes. No se da por aprobada la parte de C hasta que Angel registre su
aprobación sobre la revisión actualizada del PR #78.

### Ajustes a la revisión del integrante B

Durante la actualización llegó la revisión formal de Marco en el PR #78,
todavía como comentario sin aprobación. Se incorporaron la exclusión del
renovado cuya renovación se rescindió, saldos de rentas solo vencidas,
cartera por cliente y fila propia de R02, y cuotas únicamente de contratos
vigentes para los saldos. Se registraron sus validaciones sobre contado,
enganche, cohortes, tiempos desde auditoría y ranking. Se precisó que el
recargo ya está incluido en `monto_pagado` y que BI excluye rentas canceladas.
Se incluyó su propuesta de acceso para `CONSULTA`, pendiente de aprobación
global, y se añadieron los criterios/casos de prueba correspondientes.
Marco indicó que amplía la demo comercial en otro PR; esa mejora debe
coordinarse para demostrar R02/R03 con varios estados y agentes.

### Ajustes a la revisión del integrante A

Douglas pidió reducir BI al alcance del roadmap y repartir reportes por dueño
de datos. La propuesta revisada adopta cuatro vistas y un tablero comercial,
mantiene los quince reportes y registra el reparto en §10. Las vistas futuras
conservan las definiciones revisadas por B/C, pero ya no son criterios de esta
entrega. Se añadieron dependencias y recreación reversible de vistas ante
cambios de columnas, y prueba temprana de conexión segura a Neon con un rol
de lectura sin publicar credenciales. La revisión de A sigue pendiente de
aprobación formal sobre esta actualización; no se asume por su comentario.
