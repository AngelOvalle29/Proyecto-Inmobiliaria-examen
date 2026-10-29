"""
Pruebas de calcular_cuotas (spec 007, regla 12). Es una función pura: no
necesita base de datos.
"""

from datetime import date
from decimal import Decimal

from apps.ventas.services import calcular_cuotas


def test_caso_de_libro_12_cuotas_al_12_por_ciento():
    """
    10 000 al 12 % anual (1 % mensual) en 12 cuotas: la cuota fija es
    888.49 (10 000 · 0.01 / (1 − 1.01^−12) = 888.4878...). El primer mes, el
    interés es 1 % de 10 000 = 100.00 y el capital, 788.49.
    """
    cuotas = calcular_cuotas(
        saldo=Decimal("10000.00"),
        tasa_anual=Decimal("12"),
        numero_cuotas=12,
        primera=date(2026, 12, 1),
    )

    assert len(cuotas) == 12
    assert cuotas[0]["monto_total"] == Decimal("888.49")
    assert cuotas[0]["monto_interes"] == Decimal("100.00")
    assert cuotas[0]["monto_capital"] == Decimal("788.49")
    # Todas iguales salvo la última, que ajusta centavos.
    assert {c["monto_total"] for c in cuotas[:-1]} == {Decimal("888.49")}
    assert abs(cuotas[-1]["monto_total"] - Decimal("888.49")) < Decimal("0.10")


def test_el_capital_suma_exactamente_el_saldo():
    saldo = Decimal("123456.78")

    cuotas = calcular_cuotas(
        saldo=saldo,
        tasa_anual=Decimal("9.5"),
        numero_cuotas=120,
        primera=date(2026, 12, 1),
    )

    assert sum(c["monto_capital"] for c in cuotas) == saldo
    for cuota in cuotas:
        assert cuota["monto_total"] == cuota["monto_capital"] + cuota["monto_interes"]


def test_el_interes_baja_y_el_capital_sube():
    cuotas = calcular_cuotas(
        saldo=Decimal("50000.00"),
        tasa_anual=Decimal("10"),
        numero_cuotas=24,
        primera=date(2026, 12, 1),
    )

    intereses = [c["monto_interes"] for c in cuotas]
    assert intereses == sorted(intereses, reverse=True)
    assert cuotas[0]["monto_capital"] < cuotas[-2]["monto_capital"]


def test_con_tasa_cero_el_saldo_se_divide_en_partes_iguales():
    cuotas = calcular_cuotas(
        saldo=Decimal("1000.00"),
        tasa_anual=Decimal("0"),
        numero_cuotas=3,
        primera=date(2026, 12, 1),
    )

    assert [c["monto_total"] for c in cuotas] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert all(c["monto_interes"] == 0 for c in cuotas)


def test_una_sola_cuota_es_todo_el_saldo_mas_un_mes_de_interes():
    cuotas = calcular_cuotas(
        saldo=Decimal("1200.00"),
        tasa_anual=Decimal("12"),
        numero_cuotas=1,
        primera=date(2026, 12, 1),
    )

    assert cuotas == [
        {
            "numero": 1,
            "fecha_vencimiento": date(2026, 12, 1),
            "monto_capital": Decimal("1200.00"),
            "monto_interes": Decimal("12.00"),
            "monto_total": Decimal("1212.00"),
        }
    ]


def test_las_fechas_son_mensuales_y_respetan_fin_de_mes():
    cuotas = calcular_cuotas(
        saldo=Decimal("300.00"),
        tasa_anual=Decimal("0"),
        numero_cuotas=3,
        primera=date(2027, 1, 31),
    )

    assert [c["fecha_vencimiento"] for c in cuotas] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
    ]
