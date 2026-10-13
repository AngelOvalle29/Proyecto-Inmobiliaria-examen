"""Pruebas de los selectores de core: tipo de cambio y conversión (reglas 6 a 8)."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import OperationalError

from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.selectors import (
    convertir_monto,
    obtener_tipo_cambio,
    verificar_base_datos,
)

from .factories import MonedaFactory, TipoCambioFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD")


@pytest.fixture
def gtq():
    return MonedaFactory(codigo="GTQ")


# ---------- obtener_tipo_cambio ----------


def test_usa_la_tasa_de_la_fecha_exacta(usd, gtq):
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    tasa = obtener_tipo_cambio(origen=usd, destino=gtq, fecha=date(2026, 10, 1))

    assert tasa == Decimal("7.75")


def test_sin_fecha_exacta_usa_la_anterior_mas_cercana(usd, gtq):
    """Regla 6."""
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.70"),
        fecha=date(2026, 9, 1),
    )
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    tasa = obtener_tipo_cambio(origen=usd, destino=gtq, fecha=date(2026, 10, 15))

    assert tasa == Decimal("7.75")


def test_ignora_las_tasas_posteriores_a_la_fecha(usd, gtq):
    """Regla 6: una transacción no se convierte con una tasa del futuro."""
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.70"),
        fecha=date(2026, 9, 1),
    )
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    tasa = obtener_tipo_cambio(origen=usd, destino=gtq, fecha=date(2026, 9, 20))

    assert tasa == Decimal("7.70")


def test_sin_ninguna_tasa_anterior_lanza_excepcion(usd, gtq):
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    with pytest.raises(TipoCambioNoDisponible) as error:
        obtener_tipo_cambio(origen=usd, destino=gtq, fecha=date(2026, 9, 30))

    assert error.value.codigo == "TIPO_CAMBIO_NO_DISPONIBLE"
    assert error.value.detalles == {
        "moneda_origen": "USD",
        "moneda_destino": "GTQ",
        "fecha": "2026-09-30",
    }


def test_la_misma_moneda_tiene_tasa_uno(usd):
    """Regla 7: no hace falta ningún registro."""
    tasa = obtener_tipo_cambio(origen=usd, destino=usd, fecha=date(2026, 10, 1))

    assert tasa == Decimal("1")


def test_no_calcula_la_tasa_inversa(usd, gtq):
    """Regla 7: existir USD→GTQ no implica que exista GTQ→USD."""
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    with pytest.raises(TipoCambioNoDisponible):
        obtener_tipo_cambio(origen=gtq, destino=usd, fecha=date(2026, 10, 1))


# ---------- convertir_monto ----------


def test_convierte_entre_dos_monedas(usd, gtq):
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.75"),
        fecha=date(2026, 10, 1),
    )

    monto = convertir_monto(
        monto=Decimal("1500.00"), origen=usd, destino=gtq, fecha=date(2026, 10, 1)
    )

    assert monto == Decimal("11625.00")


def test_redondea_hacia_arriba_en_el_empate(usd, gtq):
    """
    Regla 8: 1.00 × 7.745 = 7.745 queda justo a la mitad entre 7.74 y 7.75.
    ROUND_HALF_UP da 7.75; el redondeo por defecto de Python daría 7.74.
    """
    TipoCambioFactory(
        moneda_origen=usd,
        moneda_destino=gtq,
        tasa=Decimal("7.745"),
        fecha=date(2026, 10, 1),
    )

    monto = convertir_monto(
        monto=Decimal("1.00"), origen=usd, destino=gtq, fecha=date(2026, 10, 1)
    )

    assert monto == Decimal("7.75")


def test_convertir_a_la_misma_moneda_devuelve_el_mismo_monto(usd):
    monto = convertir_monto(
        monto=Decimal("250.00"), origen=usd, destino=usd, fecha=date(2026, 10, 1)
    )

    assert monto == Decimal("250.00")


# ---------- verificar_base_datos ----------


def test_verificar_base_datos_responde_true_si_la_base_contesta():
    assert verificar_base_datos() is True


def test_verificar_base_datos_responde_false_si_la_base_falla(monkeypatch):
    """Se simula la caída haciendo que abrir un cursor falle."""

    def cursor_que_falla():
        raise OperationalError("la base no responde")

    monkeypatch.setattr("apps.core.selectors.connection.cursor", cursor_que_falla)

    assert verificar_base_datos() is False
