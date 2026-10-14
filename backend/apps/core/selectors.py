"""Selectores de core: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import DatabaseError, connection
from django.db.models import QuerySet

from .exceptions import TipoCambioNoDisponible
from .models import Ciudad, Moneda, Pais, TipoCambio

CENTAVOS = Decimal("0.01")


# ---------- Catálogos ----------
#
# Cada selector devuelve la consulta base de su listado: qué registros se ven,
# en qué orden y qué relaciones se cargan de una vez. Los filtros que pide el
# cliente (?pais=, ?fecha_desde=) se aplican después, en filters.py.
#
# El orden siempre termina en una combinación única: con un orden ambiguo, la
# paginación podría repetir u omitir registros entre una página y otra.


def listar_monedas() -> QuerySet[Moneda]:
    """Monedas activas, por código."""
    return Moneda.objects.filter(activo=True).order_by("codigo")


def listar_paises() -> QuerySet[Pais]:
    """Países activos, por nombre, con su moneda principal."""
    return (
        Pais.objects.filter(activo=True)
        .select_related("moneda_principal")
        .order_by("nombre")
    )


def listar_ciudades() -> QuerySet[Ciudad]:
    """
    Ciudades activas de países activos, por país y nombre.

    Un país desactivado es uno donde la agencia ya no opera: sus ciudades
    tampoco deben ofrecerse, aunque cada una siga marcada como activa.
    """
    return (
        Ciudad.objects.filter(activo=True, pais__activo=True)
        .select_related("pais")
        .order_by("pais__nombre", "nombre")
    )


def listar_tipos_cambio() -> QuerySet[TipoCambio]:
    """Tipos de cambio, del más reciente al más antiguo."""
    return TipoCambio.objects.select_related(
        "moneda_origen", "moneda_destino"
    ).order_by("-fecha", "moneda_origen__codigo", "moneda_destino__codigo")


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
