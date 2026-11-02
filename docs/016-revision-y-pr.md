# Spec 016 · Recorrido manual, explicación y preparación del PR

Esta guía acompaña la implementación local; no certifica que la prueba manual
ni la revisión del estudiante ya ocurrieron. La propuesta de spec 021 para los
reportes restantes y Power BI se presenta en un PR de documentación separado
y requiere revisión independiente antes de implementar.

## Recorrido en el navegador

Usar PostgreSQL de desarrollo con datos ficticios, backend con las dependencias
de `requirements/dev.txt` y frontend apuntando a esa API mediante
`VITE_API_URL=http://localhost:8000/api/v1`. Autorizar el origen local
`http://localhost:5173` en `CORS_ALLOWED_ORIGINS`. No usar producción para crear
casos de prueba. En Windows el backend en Docker evita instalar Pango a mano.

1. Ingresar con una cuenta administradora y abrir `/reportes`.
2. Elegir R05: deben aparecer país, ciudad, tipo, moneda, precio y área.
   Aplicar una moneda y comprobar filas y totales. Escribir otro filtro sin
   aplicarlo y descargar: el archivo debe seguir usando el filtro aplicado.
3. Aplicar precio sin moneda: comprobar error legible y corregirlo. Aplicar
   un rango sin resultados: tabla vacía y totales coherentes, sin fallo.
4. Si hay más de 25 resultados, pasar a página 2: los totales no cambian.
   Cambiar filtros y aplicarlos: debe volver a página 1. La descarga incluye
   todo el filtro, no únicamente las filas de esa página.
5. Pulsar **Limpiar**: se vacían filtros y vuelve a página 1. Elegir R16:
   no deben quedar filtros de R05. Probar anticipación 0, 30 y 365; 366 debe
   mostrar error. Revisar un vencimiento de hoy y uno ya vencido.
6. Elegir R17, filtrar fechas y acción. Confirmar que incluye el día final
   completo y no muestra IP ni JSON de valores anteriores/nuevos.
7. Descargar Excel y PDF de cada uno de los tres reportes: seis archivos.
   Abrirlos, comparar filtros y totales con la pantalla. Revisar encabezados,
   fechas, números, saltos de página y que el navegador no guarde JSON de error
   con extensión de archivo.
8. Repetir con un rol distinto de administrador: R05/R16 disponibles y R17
   ausente. Pedir directamente R17 y sus descargas debe responder 403.

| Comprobación manual | Estado | Evidencia |
|---|---|---|
| Pantalla, filtros, paginación, limpiar y errores | Pendiente | Registrar navegador, fecha y resultado |
| Seis descargas desde sesión autenticada | Pendiente | Nombres y resultados al abrir archivos |
| Roles desde navegador | Pendiente | Cuenta ficticia/rol y resultado, sin contraseña |
| Revisión del código por Nathaly | Pendiente | Explicar flujo y responder los tres casos siguientes |

El control de aplicaciones y navegador no estuvo disponible en la sesión del
2026-11-01: el servicio nativo devolvió `native pipe is unavailable` y el
servicio de navegador `browser access host is unavailable`. No se marca este
recorrido como aprobado con base en compilación o pruebas de API.

## Cómo explicar el código

Una consulta recorre estas capas:

```text
Reportes.tsx → hooks de consultas.ts → vista HTTP → serializer de filtros
            → servicio de permisos/paginación → selectores PostgreSQL
            → Reporte → JSON o exportador Excel/PDF
```

- `catalogo.py` define qué se puede elegir: slug, columnas, filtros y roles.
  La pantalla se construye con esos metadatos.
- `serializers.py` comprueba los parámetros antes de consultar. Por ejemplo,
  rechaza un rango de precios sin moneda, para evitar comparar monedas distintas.
- `selectors.py` obtiene las filas y los resúmenes. El resumen usa todas las
  coincidencias; el detalle JSON usa `LIMIT 25/OFFSET`. En inventario, una
  propiedad y una unidad pueden tener el mismo ID: su identidad es `(origen,id)`.
- `services.py` comprueba el permiso y decide cuánto detalle pedir. Para JSON
  pide una página; para un archivo primero verifica que el conteo no supere
  5,000. `construir_reporte` organiza datos que ya recibió, sin hacer consultas.
- `exportadores.py` recibe el mismo objeto `Reporte` para ambos formatos.
  openpyxl conserva tipos de celdas; WeasyPrint renderiza la plantilla común.
- `consultas.ts` pasa por el cliente autenticado y TanStack Query. En la
  pantalla, `borrador` es lo escrito y `filtros` es lo aplicado: por eso una
  descarga conserva el último filtro aplicado aunque el formulario haya cambiado.

Antes del commit, explicar con palabras propias:

1. Hay 60 filas y estoy en página 2. ¿Cuántas muestra JSON, cuántas descarga
   Excel y de cuántas son los totales? **25, 60 y 60**.
2. Hay 5,001 filas. ¿Por qué se rechaza antes de consultar el detalle?
   **El límite evita cargar y renderizar un archivo grande; se pide acotar filtros.**
3. R17 está oculto para otro rol. ¿Eso basta? **No: el backend vuelve a
   comprobar permisos en JSON y en las dos descargas.**

## Borrador de descripción del PR

Copiar después de completar la revisión; sustituir los pendientes por los
resultados reales. No usar `Closes #24`: esta entrega solo aporta 3 de 15.

```markdown
## Qué hace
Implementa la pantalla genérica de reportes y exportaciones Excel/PDF para
R05 Inventario disponible, R16 Documentos por vencer y R17 Bitácora de auditoría.

## Spec
Implementa specs/016-capa-generica-reportes.md, aprobada en #61.
Avance de #24, sin cerrarlo.

## Cambios
- Catálogo con filtros, columnas y permisos; JSON paginado en PostgreSQL.
- Totales del conjunto filtrado y exportadores compartidos con límite de 5,000 filas.
- Monedas separadas, prevención de doble conteo y R17 solo para administración.
- Pantalla /reportes, descargas autenticadas y tipos desde OpenAPI.
- Pruebas de selectores, permisos, paginación y archivos; sin migraciones.

## Cómo probarlo
1. Instalar dependencias, preparar PostgreSQL y cargar datos ficticios.
2. Ingresar y abrir /reportes; seguir docs/016-revision-y-pr.md.
3. Adjuntar resultados actuales de ruff, formato, migraciones, pytest,
   OpenAPI, lint, typecheck y build.

## Pendientes
- Prueba de navegador: pendiente de registrar.
- Revisión y comprensión por Nathaly: pendiente.
- Otros 12 reportes y Power BI: propuesta en spec 021, aún sin aprobar.
```

La rama destino es `develop`. Según `docs/convenciones.md` §§2 y 5, la
estudiante debe revisar y entender el código. Nathaly autorizó expresamente
el 2026-11-01 que Codex ejecute commit, push y apertura del PR usando su
configuración de Git. La autorización no sustituye la comprensión del código.
Otro integrante debe aprobar con **Approve** antes de fusionar
mediante **Create a merge commit**. Este documento no sustituye esa aprobación.
