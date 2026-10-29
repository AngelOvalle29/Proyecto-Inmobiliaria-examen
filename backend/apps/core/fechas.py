"""
Cálculos con fechas que comparten varias apps.

Funciones puras: no consultan la base ni importan ninguna app. Las usan las
cuotas de ventas (spec 007) y el calendario de rentas de arrendamientos
(spec 008). Acordado con A en #35.
"""

import calendar
from datetime import date


def sumar_meses(fecha: date, meses: int) -> date:
    """
    La misma fecha, `meses` meses después.

    Si ese mes no tiene el día (31 de enero + 1 mes), se usa el último día del
    mes: 28 o 29 de febrero. Se calcula siempre desde la fecha original, así
    una serie mensual que empieza el 31 vuelve al 31 en los meses que lo
    tienen (31 ene → 28 feb → 31 mar), en lugar de quedarse en el 28.
    """
    # Meses contados desde el año 0 para que el cambio de año salga solo.
    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))
