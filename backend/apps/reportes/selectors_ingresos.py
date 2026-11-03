"""R12: cobros reales; cada abono conserva la fecha y tasa de su log (spec 021).

SQL explícito porque la bitácora guarda los abonos en JSON. Los valores del
cliente siempre viajan como parámetros. PostgreSQL agrega y pagina antes de
materializar detalle. No se crea una segunda tabla de pagos.
"""

from dataclasses import asdict
from decimal import Decimal

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import connection

from .estructuras import FiltrosIngresos, Grupo, ResumenReporte
from .exceptions import DatosCobrosIncompletos

# pg_input_is_valid (PostgreSQL 16) evita que un JSON incompleto o una fecha
# imposible fallen como error 500 al convertirlos. NaN/Infinity no son dinero.
BASE = """
WITH ventas AS (
    SELECT v.*, m.codigo AS moneda, p.id AS pais_id, p.nombre AS pais
    FROM ventas_contratoventa v
    JOIN core_moneda m ON m.id = v.moneda_id
    LEFT JOIN catalogo_propiedad pp ON pp.id = v.propiedad_id
    LEFT JOIN catalogo_unidad u ON u.id = v.unidad_id
    LEFT JOIN catalogo_propiedad pu ON pu.id = u.propiedad_id
    JOIN core_ciudad c ON c.id = COALESCE(pp.ciudad_id, pu.ciudad_id)
    JOIN core_pais p ON p.id = c.pais_id
    WHERE v.activo AND v.estado <> 'ANULADO'
      AND (%(pais)s::bigint IS NULL OR p.id = %(pais)s)
      AND (%(moneda)s::text IS NULL OR m.codigo = %(moneda)s)
), abonos AS (
    SELECT l.id AS id_fuente, q.id AS cuota_id, v.codigo AS contrato,
           v.moneda, v.pais, v.pais_id,
           CASE WHEN pg_input_is_valid(l.valores_nuevos->>'pago', 'numeric')
                 AND l.valores_nuevos->>'pago' ~ '^[0-9]+([.][0-9]+)?$'
                THEN (l.valores_nuevos->>'pago')::numeric END AS recibido,
           CASE WHEN pg_input_is_valid(l.valores_nuevos->>'tasa_a_usd', 'numeric')
                 AND l.valores_nuevos->>'tasa_a_usd' ~ '^[0-9]+([.][0-9]+)?$'
                THEN (l.valores_nuevos->>'tasa_a_usd')::numeric END AS tasa_a_usd,
           CASE WHEN pg_input_is_valid(l.valores_nuevos->>'fecha', 'date')
                 AND l.valores_nuevos->>'fecha' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN (l.valores_nuevos->>'fecha')::date END AS fecha,
           v.fecha_firma
    FROM auditoria_log_sistema l
    JOIN ventas_cuotapago q ON q.id = l.entidad_id AND q.activo
    JOIN ventas v ON v.id = q.contrato_id
    WHERE l.entidad = 'ventas_cuotapago' AND l.accion = 'ACTUALIZAR'
      AND l.valores_nuevos ? 'pago'
), rentas AS (
    SELECT r.id AS id_fuente, a.codigo AS contrato, r.fecha_pago AS fecha,
           p.id AS pais_id, p.nombre AS pais, m.codigo AS moneda,
           r.monto_pagado AS recibido, r.tasa_a_usd,
           ROUND(r.monto_pagado * r.tasa_a_usd, 2) AS monto_usd
    FROM arrendamientos_pagorenta r
    JOIN arrendamientos_contratoarrendamiento a ON a.id = r.contrato_id
    JOIN core_moneda m ON m.id = a.moneda_id
    LEFT JOIN catalogo_propiedad pp ON pp.id = a.propiedad_id
    LEFT JOIN catalogo_unidad u ON u.id = a.unidad_id
    LEFT JOIN catalogo_propiedad pu ON pu.id = u.propiedad_id
    JOIN core_ciudad c ON c.id = COALESCE(pp.ciudad_id, pu.ciudad_id)
    JOIN core_pais p ON p.id = c.pais_id
    WHERE r.activo AND a.activo AND r.estado = 'PAGADO'
      AND (%(pais)s::bigint IS NULL OR p.id = %(pais)s)
      AND (%(moneda)s::text IS NULL OR m.codigo = %(moneda)s)
), cobros AS (
    SELECT 'CUOTA'::text AS origen, id_fuente, contrato, fecha, pais_id, pais,
           moneda, recibido, tasa_a_usd, ROUND(recibido * tasa_a_usd, 2) AS monto_usd
    FROM abonos
    UNION ALL
    SELECT 'CONTADO', id, codigo, fecha_firma, pais_id, pais, moneda,
           monto_total, tasa_a_usd, monto_total_usd
    FROM ventas WHERE modalidad = 'CONTADO'
    UNION ALL
    SELECT 'ENGANCHE', id, codigo, fecha_firma, pais_id, pais, moneda,
           enganche, tasa_a_usd, ROUND(enganche * tasa_a_usd, 2)
    FROM ventas WHERE modalidad = 'FINANCIADO' AND enganche > 0
    UNION ALL
    SELECT 'RENTA', id_fuente, contrato, fecha, pais_id, pais, moneda,
           recibido, tasa_a_usd, monto_usd FROM rentas
), filtrados AS (
    SELECT * FROM cobros
    WHERE (%(fecha_desde)s::date IS NULL OR fecha >= %(fecha_desde)s)
      AND (%(fecha_hasta)s::date IS NULL OR fecha <= %(fecha_hasta)s)
      AND (%(origen)s::text IS NULL OR origen = %(origen)s)
)
"""


def _consultar(sql: str, parametros: dict) -> list[dict]:
    """Ejecuta SQL fijo y devuelve únicamente el resumen o la página pedida."""
    with connection.cursor() as cursor:
        cursor.execute(BASE + sql, parametros)
        columnas = [c[0] for c in cursor.description]
        return [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]


def verificar_integridad_cobros(*, filtros: FiltrosIngresos) -> None:
    """Concilia todos los abonos de las cuotas del país/moneda seleccionados.

    No se limita por fecha: si falta un log, su fecha es desconocida. Acotar
    un mes no debe ocultar una pérdida de evidencia. No carga JSON en Python.
    """
    if filtros.origen not in (None, "CUOTA", "RENTA"):
        return
    resultado = _consultar(
        """
        SELECT
          (%(origen)s::text IS NULL OR %(origen)s = 'CUOTA') AND (
            EXISTS (SELECT 1 FROM abonos WHERE recibido IS NULL OR recibido <= 0
                    OR tasa_a_usd IS NULL OR tasa_a_usd <= 0 OR fecha IS NULL
                    OR fecha < fecha_firma
                    OR fecha >
                       (CURRENT_TIMESTAMP AT TIME ZONE 'America/Guatemala')::date)
            OR EXISTS (
                SELECT 1 FROM ventas_cuotapago q JOIN ventas v ON v.id=q.contrato_id
                LEFT JOIN (SELECT cuota_id, SUM(recibido) AS total
                           FROM abonos GROUP BY cuota_id) a ON a.cuota_id=q.id
                WHERE q.activo AND q.monto_pagado <> COALESCE(a.total, 0)
            )
          ) OR (
            (%(origen)s::text IS NULL OR %(origen)s = 'RENTA') AND
            EXISTS (SELECT 1 FROM rentas WHERE fecha IS NULL OR tasa_a_usd IS NULL
                    OR tasa_a_usd <= 0 OR recibido IS NULL OR recibido <= 0)
          ) AS incompletos
    """,
        asdict(filtros),
    )
    if resultado[0]["incompletos"]:
        raise DatosCobrosIncompletos(
            "Los cobros no concilian o falta evidencia de fecha/tasa. "
            "Revise los registros de pago antes de generar este reporte."
        )


def resumir_ingresos(
    *, filtros: FiltrosIngresos, usuario: AbstractBaseUser | None = None
) -> ResumenReporte:
    """Totales de todo el filtro por mes/origen/moneda y consolidado USD."""
    verificar_integridad_cobros(filtros=filtros)
    grupos = _consultar(
        """
        SELECT to_char(fecha, 'YYYY-MM') AS mes, origen, moneda,
               COUNT(*) AS cantidad, SUM(recibido) AS recibido,
               SUM(monto_usd) AS monto_usd
        FROM filtrados GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """,
        asdict(filtros),
    )
    monedas: dict[str, Decimal] = {}
    for g in grupos:
        monedas[g["moneda"]] = monedas.get(g["moneda"], Decimal("0.00")) + g["recibido"]
    return ResumenReporte(
        sum(g["cantidad"] for g in grupos),
        dict(
            cantidad=sum(g["cantidad"] for g in grupos),
            recibido_por_moneda=dict(sorted(monedas.items())),
            total_usd=sum((g["monto_usd"] for g in grupos), Decimal("0.00")),
        ),
        [Grupo(f"{g['mes']} / {g['origen']} / {g['moneda']}", g) for g in grupos],
    )


def seleccionar_ingresos(
    *,
    filtros: FiltrosIngresos,
    offset: int,
    limite: int,
    usuario: AbstractBaseUser | None = None,
) -> list[dict]:
    """Orden por fecha/origen/ID; el límite se aplica dentro de PostgreSQL."""
    return _consultar(
        """
        SELECT origen, id_fuente, contrato, fecha, pais, moneda,
               recibido, tasa_a_usd, monto_usd FROM filtrados
        ORDER BY fecha, origen, id_fuente LIMIT %(limite)s OFFSET %(offset)s
    """,
        {**asdict(filtros), "limite": limite, "offset": offset},
    )
