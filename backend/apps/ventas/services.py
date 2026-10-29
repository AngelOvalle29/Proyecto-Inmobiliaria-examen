"""Servicios de ventas: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apps.core.fechas import sumar_meses

CENTAVOS = Decimal("0.01")


def calcular_cuotas(
    *, saldo: Decimal, tasa_anual: Decimal, numero_cuotas: int, primera: date
) -> list[dict]:
    """
    Plan de cuotas fijas de una venta financiada (spec 007, regla 12; sistema
    francés, decidido por B).

    Todas las cuotas valen lo mismo. Con tasa mensual i = tasa anual / 12 / 100:

        cuota = saldo · i / (1 − (1 + i)^−n)        (con i = 0: saldo / n)

    En cada mes, el interés es lo que todavía se debe por i, y el capital es
    el resto de la cuota. Al principio se debe mucho, así que la cuota es casi
    todo interés; al final, casi todo capital.

    Cada monto se redondea a centavos con ROUND_HALF_UP, y la última cuota
    ajusta los centavos que el redondeo dejó: su capital es exactamente lo que
    falta, así el capital de todas las cuotas suma el saldo sin un centavo de
    diferencia.

    Es una función pura (no toca la base): recibe números y devuelve la lista,
    y se prueba sola. La cuota k vence en primera + k − 1 meses (core/fechas).
    """
    tasa_mensual = tasa_anual / Decimal(12) / Decimal(100)
    if tasa_mensual == 0:
        cuota = saldo / numero_cuotas
    else:
        cuota = saldo * tasa_mensual / (1 - (1 + tasa_mensual) ** -numero_cuotas)
    cuota = _a_centavos(cuota)

    cuotas = []
    pendiente = saldo
    for numero in range(1, numero_cuotas + 1):
        interes = _a_centavos(pendiente * tasa_mensual)
        if numero == numero_cuotas:
            capital = pendiente
        else:
            capital = cuota - interes
        cuotas.append(
            {
                "numero": numero,
                "fecha_vencimiento": sumar_meses(primera, numero - 1),
                "monto_capital": capital,
                "monto_interes": interes,
                "monto_total": capital + interes,
            }
        )
        pendiente -= capital
    return cuotas


def _a_centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
