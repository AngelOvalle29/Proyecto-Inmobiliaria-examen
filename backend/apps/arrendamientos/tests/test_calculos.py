"""
Pruebas de las funciones puras de arrendamientos (spec 008, §9, nivel unidad):
fecha de fin, calendario de cobros y recargo. No necesitan base de datos.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.arrendamientos.services import (
    calcular_calendario,
    calcular_fecha_fin,
    calcular_recargo,
)

# ---------- Fecha de fin (regla 3) ----------


@pytest.mark.parametrize(
    ("inicio", "meses", "fin"),
    [
        (date(2026, 1, 1), 12, date(2026, 12, 31)),
        (date(2026, 3, 15), 1, date(2026, 4, 14)),
        (date(2026, 1, 31), 1, date(2026, 2, 27)),  # 28 de febrero menos un día
        (date(2027, 11, 10), 3, date(2028, 2, 9)),  # cambio de año
    ],
)
def test_la_fecha_de_fin_es_inicio_mas_duracion_menos_un_dia(inicio, meses, fin):
    assert calcular_fecha_fin(inicio=inicio, duracion_meses=meses) == fin


# ---------- Calendario (regla 4) ----------


def test_si_el_inicio_es_antes_del_dia_de_cobro_el_primero_vence_ese_mes():
    calendario = calcular_calendario(
        inicio=date(2026, 10, 3), duracion_meses=3, dia_cobro=5
    )

    assert calendario == [date(2026, 10, 5), date(2026, 11, 5), date(2026, 12, 5)]


def test_si_el_inicio_es_despues_del_dia_de_cobro_el_primero_vence_el_mes_siguiente():
    calendario = calcular_calendario(
        inicio=date(2026, 10, 20), duracion_meses=2, dia_cobro=5
    )

    assert calendario == [date(2026, 11, 5), date(2026, 12, 5)]


def test_el_inicio_el_mismo_dia_de_cobro_vence_ese_mismo_dia():
    assert calcular_calendario(
        inicio=date(2026, 10, 5), duracion_meses=1, dia_cobro=5
    ) == [date(2026, 10, 5)]


def test_el_calendario_cruza_el_cambio_de_anio_sin_repetir_periodos():
    calendario = calcular_calendario(
        inicio=date(2026, 11, 1), duracion_meses=4, dia_cobro=28
    )

    assert calendario[-1] == date(2027, 2, 28)
    assert len({(f.year, f.month) for f in calendario}) == 4


# ---------- Recargo (regla 6) ----------


def recargo(fecha_pago, dias_gracia=5):
    return calcular_recargo(
        renta=Decimal("1000.00"),
        porcentaje=Decimal("5.00"),
        vencimiento=date(2026, 10, 5),
        dias_gracia=dias_gracia,
        fecha_pago=fecha_pago,
    )


def test_dentro_de_la_gracia_no_hay_recargo():
    assert recargo(date(2026, 10, 1)) == 0  # por adelantado
    assert recargo(date(2026, 10, 10)) == 0  # último día de gracia


def test_el_dia_siguiente_a_la_gracia_hay_recargo_fijo():
    assert recargo(date(2026, 10, 11)) == Decimal("50.00")
    assert recargo(date(2027, 3, 1)) == Decimal("50.00")  # fijo, no por día


def test_sin_dias_de_gracia_el_recargo_empieza_al_dia_siguiente():
    assert recargo(date(2026, 10, 5), dias_gracia=0) == 0
    assert recargo(date(2026, 10, 6), dias_gracia=0) == Decimal("50.00")


def test_el_recargo_se_redondea_a_centavos_hacia_arriba_en_el_empate():
    """333.33 · 1.5 % = 4.99995 → 5.00 (ROUND_HALF_UP)."""
    assert calcular_recargo(
        renta=Decimal("333.33"),
        porcentaje=Decimal("1.50"),
        vencimiento=date(2026, 10, 5),
        dias_gracia=0,
        fecha_pago=date(2026, 10, 6),
    ) == Decimal("5.00")
