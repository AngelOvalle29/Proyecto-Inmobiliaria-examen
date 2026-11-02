"""
Esquema bi: cuatro vistas en modelo estrella para Power BI (spec 021, §4).

Son vistas, no tablas: no copian datos, siempre muestran lo que hay en las
tablas del sistema. Power BI las lee en modo Import con el rol de solo lectura
powerbi_reader (docs/powerbi/crear_lector.sql), que no ve las tablas.

Cuidado al migrar otras apps: PostgreSQL no deja cambiar el tipo ni borrar una
columna que usa una vista. Quien lo haga borra y recrea aquí las vistas
afectadas en su misma migración, con RunSQL y su reversa (spec 021, §4).
"""

from django.db import migrations

# Las fechas como entero AAAAMMDD: así se relacionan en Power BI con una sola
# columna, sin depender del tipo fecha de cada herramienta.
FECHA_ID = "to_char({}, 'YYYYMMDD')::integer"

VISTAS = [
    (
        "dim_geografia",
        """
        CREATE VIEW bi.dim_geografia AS
        SELECT c.id AS ciudad_id,
               c.nombre AS ciudad,
               c.region,
               p.id AS pais_id,
               p.nombre AS pais,
               p.codigo_iso AS pais_codigo
        FROM core_ciudad c
        JOIN core_pais p ON p.id = c.pais_id
        """,
    ),
    (
        # Los bienes como en R05 (spec 021, regla 12): las propiedades cuyo
        # tipo no lleva unidades y las unidades de los que sí. Un edificio no
        # aparece como bien: se venden sus unidades. Estado y ciudad son los
        # actuales, no los de la fecha de cada venta.
        "dim_propiedad",
        """
        CREATE VIEW bi.dim_propiedad AS
        SELECT 'PROPIEDAD-' || p.id AS bien_clave,
               'PROPIEDAD' AS origen,
               p.id AS bien_id,
               p.codigo,
               p.nombre,
               p.id AS propiedad_id,
               p.codigo AS propiedad_codigo,
               t.nombre AS tipo,
               p.ciudad_id,
               p.estado AS estado_actual,
               p.activo
        FROM catalogo_propiedad p
        JOIN catalogo_tipopropiedad t ON t.id = p.tipo_id
        WHERE NOT t.requiere_unidades
        UNION ALL
        SELECT 'UNIDAD-' || u.id,
               'UNIDAD',
               u.id,
               u.codigo,
               p.nombre || ' · ' || u.codigo,
               p.id,
               p.codigo,
               t.nombre,
               p.ciudad_id,
               u.estado,
               u.activo AND p.activo
        FROM catalogo_unidad u
        JOIN catalogo_propiedad p ON p.id = u.propiedad_id
        JOIN catalogo_tipopropiedad t ON t.id = p.tipo_id
        WHERE t.requiere_unidades
        """,
    ),
    (
        # Un contrato de venta no anulado por fila. neto es monto_total (spec
        # 021, regla 8); el USD es el guardado al firmar, con la tasa de ese
        # día, no la de hoy (regla 3). Sin nombres de clientes (§4).
        "hechos_ventas",
        f"""
        CREATE VIEW bi.hechos_ventas AS
        SELECT v.id AS contrato_id,
               v.codigo,
               {FECHA_ID.format("v.fecha_firma")} AS fecha_id,
               v.fecha_firma,
               CASE WHEN v.unidad_id IS NOT NULL THEN 'UNIDAD-' || v.unidad_id
                    ELSE 'PROPIEDAD-' || v.propiedad_id END AS bien_clave,
               COALESCE(pu.ciudad_id, pp.ciudad_id) AS ciudad_id,
               m.codigo AS moneda,
               v.modalidad,
               v.estado,
               v.monto_total AS neto,
               v.tasa_a_usd,
               ROUND(v.monto_total_usd, 2) AS neto_usd
        FROM ventas_contratoventa v
        JOIN core_moneda m ON m.id = v.moneda_id
        LEFT JOIN catalogo_propiedad pp ON pp.id = v.propiedad_id
        LEFT JOIN catalogo_unidad u ON u.id = v.unidad_id
        LEFT JOIN catalogo_propiedad pu ON pu.id = u.propiedad_id
        WHERE v.activo AND v.estado <> 'ANULADO'
        """,
    ),
    (
        # Un día por fila, desde el 1 de enero del primer año con ventas hasta
        # el 31 de diciembre del año en curso o del último año con ventas, el
        # que sea mayor: así cubre toda fecha que expone un hecho (§4).
        "dim_tiempo",
        f"""
        CREATE VIEW bi.dim_tiempo AS
        WITH limites AS (
            SELECT date_trunc('year', COALESCE(MIN(fecha_firma), CURRENT_DATE))::date AS desde,
                   (date_trunc('year', GREATEST(COALESCE(MAX(fecha_firma), CURRENT_DATE), CURRENT_DATE))
                    + INTERVAL '1 year - 1 day')::date AS hasta
            FROM bi.hechos_ventas
        )
        SELECT {FECHA_ID.format("d")} AS fecha_id,
               d::date AS fecha,
               EXTRACT(YEAR FROM d)::integer AS anio,
               EXTRACT(QUARTER FROM d)::integer AS trimestre,
               EXTRACT(MONTH FROM d)::integer AS mes,
               (ARRAY['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                      'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'])
                   [EXTRACT(MONTH FROM d)::integer] AS nombre_mes,
               to_char(d, 'YYYY-MM') AS anio_mes,
               EXTRACT(DAY FROM d)::integer AS dia
        FROM limites, generate_series(limites.desde, limites.hasta, INTERVAL '1 day') AS d
        """,
    ),
]


def _crear():
    return ["CREATE SCHEMA IF NOT EXISTS bi"] + [sql for _, sql in VISTAS]


def _borrar():
    # Al revés de como se crearon, y sin CASCADE: si algo ajeno depende de una
    # vista, la reversión falla en vez de borrarlo (spec 021, §4).
    return [f"DROP VIEW IF EXISTS bi.{nombre}" for nombre, _ in reversed(VISTAS)] + [
        "DROP SCHEMA IF EXISTS bi"
    ]


class Migration(migrations.Migration):
    initial = True

    # La última migración de cada app cuyas tablas leen las vistas.
    dependencies = [
        ("core", "0003_extension_vector"),
        ("catalogo", "0003_avaluos_y_documentos"),
        ("ventas", "0002_documento_del_contrato"),
    ]

    operations = [migrations.RunSQL(_crear(), reverse_sql=_borrar())]
