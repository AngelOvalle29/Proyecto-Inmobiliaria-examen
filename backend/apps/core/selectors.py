"""Selectores de core: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import DatabaseError, connection

from .exceptions import TipoCambioNoDisponible
from .models import Moneda, TipoCambio

CENTAVOS = Decimal("0.01")


def obtener_tipo_cambio(*, origen: Moneda, destino: Moneda, fecha: date) -> Decimal:
    """
    Tasa para convertir de origen a destino, vigente en la fecha dada.

    Regla 6: la vigente es la registrada en esa fecha o, si no hay, la más
    reciente anterior. Nunca una posterior: un pago del 3 de octubre no
    puede convertirse con una tasa que se publicó el 5.

    Regla 7: la misma moneda usa tasa 1. No se calculan inversas: si solo
    existe USD→GTQ, pedir GTQ→USD lanza TipoCambioNoDisponible.
    """
    if origen.pk == destino.pk:
        return Decimal("1")

    tipo_cambio = (
        TipoCambio.objects.filter(
            moneda_origen=origen, moneda_destino=destino, fecha__lte=fecha
        )
        .order_by("-fecha")
        .first()
    )
    if tipo_cambio is None:
        raise TipoCambioNoDisponible(
            origen=origen.codigo, destino=destino.codigo, fecha=fecha
        )
    return tipo_cambio.tasa


def convertir_monto(
    *, monto: Decimal, origen: Moneda, destino: Moneda, fecha: date
) -> Decimal:
    """
    Convierte un monto con la tasa vigente a la fecha de la transacción.

    Regla 8: el resultado se redondea a centavos con redondeo comercial
    (ROUND_HALF_UP: 0.005 sube a 0.01). Python por defecto usa el redondeo
    bancario (ROUND_HALF_EVEN), que en un empate redondea al par y no es lo
    que espera un cliente al leer un monto.
    """
    tasa = obtener_tipo_cambio(origen=origen, destino=destino, fecha=fecha)
    return (monto * tasa).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def verificar_base_datos() -> bool:
    """
    True si la base de datos responde.

    Lo usa el endpoint de salud: el servicio solo está sano si puede leer sus
    datos. Que Django arranque no basta, porque sin base de datos ninguna
    operación funciona.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True
