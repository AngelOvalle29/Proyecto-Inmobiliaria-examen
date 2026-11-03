# Guía de defensa del bloque D

Esta guía sirve para practicar. Leerla no demuestra que Nathaly ya explicó el
código: ese repaso oral queda pendiente. Intenta responder sin mirar y después
abre el archivo indicado para comprobar tu explicación.

## Explicación de un minuto

«Mi bloque reúne la auditoría, la capa genérica de reportes y el tablero
comercial. Una sola pantalla permite elegir entre quince reportes, aplicar
filtros y descargar Excel o PDF. El backend comprueba permisos y obtiene los
datos desde selectores. R12 reúne cobros efectivos de ventas y rentas, usando
la fecha y la tasa histórica de cada pago. Power BI consulta cuatro vistas de
solo lectura y presenta ventas por mes, país y tipo de propiedad».

## Cómo llega una consulta a la pantalla

1. `frontend/src/paginas/reportes/Reportes.tsx` presenta el catálogo recibido
   del API. Cada definición indica columnas, filtros y formatos.
2. Los hooks de `frontend/src/api/reportes/consultas.ts` hacen las peticiones
   mediante el cliente común y TanStack Query.
3. `backend/apps/reportes/views.py` recibe HTTP; los serializers validan los
   filtros. La vista no calcula cobros ni escribe pagos.
4. `services.py` comprueba el rol y organiza la consulta o la descarga.
5. Los selectores consultan PostgreSQL. La pantalla recibe 25 filas por
   página, con los totales de todo el filtro.
6. `exportadores.py` transforma el mismo contrato `Reporte` en Excel o PDF.
   Los archivos incluyen todo el filtro; existe un límite de 5,000 filas.

**¿Por qué no hay una pantalla por reporte?** Porque columnas y filtros son
metadatos. Agregar un reporte reutiliza la pantalla, los permisos y los
exportadores, en vez de repetirlos quince veces.

## Qué calcula R12

`backend/apps/reportes/selectors_ingresos.py` reúne cuatro orígenes con
`UNION ALL`:

| Origen | Fecha e importe |
|---|---|
| CONTADO | Total de venta y tasa guardada al firmar |
| ENGANCHE | Enganche positivo de venta financiada, al firmar |
| CUOTA | Cada abono de su evento de auditoría, con fecha y tasa propias |
| RENTA | Pago marcado PAGADO y su importe recibido, que ya incluye recargo |

Las ventas anuladas quedan fuera. Un contrato financiado no vuelve a contar
todo su precio como cobrado: solo el enganche y los abonos efectivos.

**Ejemplo de tasa histórica:** un abono de 100 con tasa 0.10 y otro de 200
con tasa 0.20 suman 300 en moneda original y 50 USD. Multiplicar los 300 por
la tasa más reciente daría 60 USD y alteraría la historia. No sumamos montos
de monedas diferentes: conservamos el total por moneda y consolidamos USD.

La tasa puede tener seis decimales: `0.000243` no debe mostrarse como `0.00`.
La pantalla, Excel y PDF usan el formato de cada columna; los importes
monetarios siguen teniendo dos decimales.

## Qué sucede si faltan datos

Antes del reporte, `verificar_integridad_cobros` concilia la suma de los
abonos de la bitácora con `monto_pagado` de la cuota. También comprueba fecha,
importe y tasa. Si falta evidencia, responde **409 DATOS_INCOMPLETOS** en
JSON, Excel y PDF; no inventa un cobro ni presenta un total aparentemente
completo. Un filtro de mes no oculta el problema: la fecha de un evento
ausente es desconocida. La validación respeta el país, moneda y origen
aplicables.

El SQL es fijo y los filtros se envían como parámetros. `pg_input_is_valid`
de PostgreSQL 16 comprueba datos JSON antes de convertirlos, evitando un
error 500 por una fecha o número inválido. Los filtros no se concatenan al
SQL. El reporte lee; los servicios de ventas y arrendamientos registran los
pagos y su auditoría.

## Permisos y auditoría

R12 está permitido para ADMINISTRADOR, GERENTE y CONTABILIDAD. AGENTE y
CONSULTA no lo ven en el catálogo y reciben 403 si solicitan directamente
su JSON o sus archivos. Ocultar una opción en React no basta: el backend
repite la comprobación.

La bitácora del sistema guarda quién cambió qué, cuándo y con qué valores.
La del agente registra su interacción y ejecución. Los registros sirven
para rastrear hechos; no deben editarse para hacer cuadrar un reporte.
En R12 se usa la evidencia histórica del abono, no el saldo acumulado como
si fuera un único pago reciente.

## Cómo explicar Power BI

El modelo tiene una tabla de hechos (`bi hechos_ventas`) y tres dimensiones:
tiempo, geografía y propiedad. Las dimensiones filtran los hechos mediante
tres relaciones de uno a muchos, en una sola dirección. La clave de bien
distingue propiedad de unidad.

- **Ventas USD:** suma de `neto_usd`, con la conversión guardada al firmar.
- **Contratos:** número de filas de hechos de ventas.
- **Ticket promedio USD:** ventas USD divididas entre contratos con `DIVIDE`.

Los filtros de año, país y ciudad modifican las tarjetas y los gráficos.
La conexión usa un lector con permisos limitados, configurado de forma
privada. Las contraseñas no forman parte del código. El PBIX es el informe
que se abre en Desktop; el PBIP y sus carpetas permiten revisar el modelo y
los visuales como archivos de texto. No se deben versionar los cachés.

**¿Por qué Ventas USD y R12 pueden dar distinto?** El tablero mide ventas
contratadas al firmar; R12 mide dinero efectivamente cobrado en sus fechas.
Una venta financiada puede aparecer completa en el tablero mientras sus
abonos llegan a R12 en varios meses.

**¿Cómo se comprueban las cifras?** Se ejecuta
`docs/powerbi/conciliacion.sql` con el lector y se compara con las medidas
sin abreviar. Una tarjeta que dice «422.69 mil» no sirve para conciliar
centavos. Esa comprobación en producción sigue pendiente de revisión.

## Preguntas para practicar

1. Explica por qué una descarga contiene más filas que la página visible.
2. ¿Por qué no se suman GTQ y COP directamente?
3. ¿Qué ocurre si falta el evento de uno de los abonos?
4. ¿Por qué una renta no vuelve a sumar su recargo en R12?
5. ¿Qué evita que un agente obtenga R12 escribiendo su URL?
6. ¿Qué diferencia hay entre ingreso cobrado y venta contratada?
7. ¿Por qué el modelo de Power BI tiene dimensiones y hechos?
8. ¿Qué verifican las pruebas automáticas y qué debes comprobar en Desktop?

El registro del recorrido local está en
[evidencia-navegador-021.md](reportes/evidencia-navegador-021.md). Las pruebas
automáticas y las capturas no sustituyen tu explicación oral ni la revisión
del equipo.
