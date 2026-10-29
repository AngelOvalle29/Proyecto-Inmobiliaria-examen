"""Pruebas de sumar_meses (specs 007 y 008)."""

from datetime import date

import pytest

from apps.core.fechas import sumar_meses


@pytest.mark.parametrize(
    ("fecha", "meses", "esperada"),
    [
        (date(2026, 1, 15), 1, date(2026, 2, 15)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),  # año bisiesto
        (date(2026, 1, 31), 2, date(2026, 3, 31)),  # vuelve al 31
        (date(2026, 3, 31), 1, date(2026, 4, 30)),
        (date(2026, 11, 30), 2, date(2027, 1, 30)),  # cambio de año
        (date(2026, 12, 15), 13, date(2028, 1, 15)),
        (date(2026, 5, 10), 0, date(2026, 5, 10)),
    ],
)
def test_suma_meses_y_ajusta_al_ultimo_dia(fecha, meses, esperada):
    assert sumar_meses(fecha, meses) == esperada
