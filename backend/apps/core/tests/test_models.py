"""
Pruebas de los constraints de core.

Comprueban que la base de datos misma rechaza los datos inválidos, sin pasar
por formularios ni servicios: así las reglas se cumplen aunque el dato entre
por el panel, por un script o por el seed.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection

from apps.core.models import Ciudad, Moneda, Pais, TipoCambio

pytestmark = pytest.mark.django_db


@pytest.fixture
def usd():
    return Moneda.objects.create(codigo="USD", nombre="Dólar", simbolo="$")


@pytest.fixture
def gtq():
    return Moneda.objects.create(codigo="GTQ", nombre="Quetzal", simbolo="Q")


def test_no_se_repite_un_tipo_de_cambio_en_la_misma_fecha(usd, gtq):
    """Regla 4: único por moneda origen, moneda destino y fecha."""
    TipoCambio.objects.create(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    with pytest.raises(IntegrityError):
        TipoCambio.objects.create(
            moneda_origen=usd,
            moneda_destino=gtq,
            tasa=Decimal("7.80"),
            fecha=date(2026, 10, 1),
        )


@pytest.mark.parametrize("tasa", [Decimal("0"), Decimal("-7.75")])
def test_la_tasa_debe_ser_mayor_que_cero(usd, gtq, tasa):
    """Regla 5."""
    with pytest.raises(IntegrityError):
        TipoCambio.objects.create(
            moneda_origen=usd, moneda_destino=gtq, tasa=tasa, fecha=date(2026, 10, 1)
        )


def test_una_moneda_no_tiene_tipo_de_cambio_consigo_misma(usd):
    """Regla 5: la conversión a la misma moneda usa tasa 1, no un registro."""
    with pytest.raises(IntegrityError):
        TipoCambio.objects.create(
            moneda_origen=usd,
            moneda_destino=usd,
            tasa=Decimal("1"),
            fecha=date(2026, 10, 1),
        )


def test_una_ciudad_no_se_repite_en_el_mismo_pais(gtq):
    guatemala = Pais.objects.create(
        nombre="Guatemala", codigo_iso="GTM", moneda_principal=gtq
    )
    Ciudad.objects.create(nombre="Quetzaltenango", pais=guatemala)

    with pytest.raises(IntegrityError):
        Ciudad.objects.create(nombre="Quetzaltenango", pais=guatemala)


def test_la_extension_vector_queda_habilitada():
    """Spec 002, §5.6: la migración core.0003 habilita pgvector para el RAG."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cursor.fetchone() is not None
