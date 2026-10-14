"""
Fábricas de datos de prueba para los modelos de core.

Una fábrica crea un objeto válido con valores por defecto, y la prueba solo
indica lo que le importa: TipoCambioFactory(tasa=Decimal("7.75")) crea también
las dos monedas sin que la prueba tenga que mencionarlas.
"""

import string
from datetime import date
from decimal import Decimal

import factory

from apps.core.models import Ciudad, Moneda, Pais, TipoCambio


def _tres_letras(n: int) -> str:
    """Código ISO ficticio y único por secuencia: XAA, XAB, XAC…"""
    letras = string.ascii_uppercase
    return "X" + letras[n // 26 % 26] + letras[n % 26]


class MonedaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Moneda
        # MonedaFactory(codigo="USD") dos veces devuelve la misma moneda en
        # lugar de chocar con el unique.
        django_get_or_create = ["codigo"]

    codigo = factory.Sequence(_tres_letras)
    nombre = factory.LazyAttribute(lambda moneda: f"Moneda {moneda.codigo}")
    simbolo = "¤"


class PaisFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Pais
        django_get_or_create = ["codigo_iso"]

    nombre = factory.LazyAttribute(lambda pais: f"País {pais.codigo_iso}")
    codigo_iso = factory.Sequence(_tres_letras)
    moneda_principal = factory.SubFactory(MonedaFactory)


class CiudadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ciudad

    nombre = factory.Sequence(lambda n: f"Ciudad {n}")
    pais = factory.SubFactory(PaisFactory)


class TipoCambioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TipoCambio

    moneda_origen = factory.SubFactory(MonedaFactory)
    moneda_destino = factory.SubFactory(MonedaFactory)
    tasa = Decimal("1.000000")
    fecha = date(2026, 10, 1)
