"""
Pruebas de los constraints de ventas (spec 007, §9, nivel modelo): la base
rechaza los datos inválidos aunque no pasen por el servicio.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.catalogo.tests.factories import PropiedadFactory
from apps.core.tests.factories import MonedaFactory
from apps.crm.tests.factories import ClienteFactory
from apps.ventas.enums import EstadoContrato, ModalidadVenta
from apps.ventas.models import ContratoVenta, CuotaPago

pytestmark = pytest.mark.django_db


def contrato(**cambios):
    cliente = ClienteFactory()
    datos = {
        "cliente": cliente,
        "agente": cliente.agente_asignado,
        "propiedad": PropiedadFactory(),
        "fecha_firma": date(2026, 10, 30),
        "monto_total": Decimal("100000.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "tasa_a_usd": Decimal("1"),
        "monto_total_usd": Decimal("100000.00"),
        "modalidad": ModalidadVenta.CONTADO,
        "comision_agente": Decimal("3000.00"),
    }
    datos.update(cambios)
    return ContratoVenta.objects.create(**datos)


def financiado(**cambios):
    datos = {
        "modalidad": ModalidadVenta.FINANCIADO,
        "enganche": Decimal("20000.00"),
        "numero_cuotas": 12,
        "tasa_interes_anual": Decimal("9.50"),
        "fecha_primera_cuota": date(2026, 12, 1),
    }
    datos.update(cambios)
    return contrato(**datos)


def test_un_contrato_de_contado_y_uno_financiado_validos_se_aceptan():
    contrato()
    financiado()


def test_la_base_exige_exactamente_propiedad_o_unidad():
    with pytest.raises(IntegrityError), transaction.atomic():
        contrato(propiedad=None)


@pytest.mark.parametrize(
    "cambios",
    [
        {"numero_cuotas": None},
        {"numero_cuotas": 0},
        {"numero_cuotas": 361},
        {"tasa_interes_anual": Decimal("100.01")},
        {"fecha_primera_cuota": None},
        {"enganche": Decimal("100000.00")},  # regla 11: sin incluir el total
    ],
)
def test_un_financiado_incompleto_o_fuera_de_rango_se_rechaza(cambios):
    with pytest.raises(IntegrityError), transaction.atomic():
        financiado(**cambios)


def test_un_contrato_de_contado_no_lleva_plan_de_cuotas():
    with pytest.raises(IntegrityError), transaction.atomic():
        contrato(numero_cuotas=12)


def test_la_cuota_no_se_repite_y_no_se_paga_de_mas():
    venta = financiado()
    datos = {
        "contrato": venta,
        "numero": 1,
        "fecha_vencimiento": date(2026, 12, 1),
        "monto_capital": Decimal("100.00"),
        "monto_interes": Decimal("10.00"),
        "monto_total": Decimal("110.00"),
    }
    CuotaPago.objects.create(**datos)

    with pytest.raises(IntegrityError), transaction.atomic():
        CuotaPago.objects.create(**datos)
    with pytest.raises(IntegrityError), transaction.atomic():
        CuotaPago.objects.create(
            **{**datos, "numero": 2, "monto_pagado": Decimal("110.01")}
        )


def test_la_cuota_en_mora_se_calcula_con_la_fecha():
    """Regla 17."""
    venta = financiado()
    cuota = CuotaPago.objects.create(
        contrato=venta,
        numero=1,
        fecha_vencimiento=date(2026, 12, 1),
        monto_capital=Decimal("100.00"),
        monto_interes=Decimal("10.00"),
        monto_total=Decimal("110.00"),
    )

    assert not cuota.en_mora(hoy=date(2026, 12, 1))
    assert cuota.en_mora(hoy=date(2026, 12, 2))


def test_la_cuota_de_un_contrato_anulado_no_esta_en_mora():
    """Regla 17: un contrato anulado ya no se cobra."""
    venta = financiado()
    cuota = CuotaPago.objects.create(
        contrato=venta,
        numero=1,
        fecha_vencimiento=date(2026, 12, 1),
        monto_capital=Decimal("100.00"),
        monto_interes=Decimal("10.00"),
        monto_total=Decimal("110.00"),
    )
    venta.estado = EstadoContrato.ANULADO
    venta.save(update_fields=["estado"])

    assert not cuota.en_mora(hoy=date(2026, 12, 2))
