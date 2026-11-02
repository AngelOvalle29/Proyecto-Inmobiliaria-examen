"""Pruebas de las restricciones de compras en la base de datos (specs 006 y 017, §4)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.catalogo.tests.factories import PropiedadFactory
from apps.compras.enums import EstadoContratoCompra, TipoProveedor
from apps.compras.models import ContratoCompra
from apps.core.tests.factories import MonedaFactory, PaisFactory

from .factories import ProveedorFactory

pytestmark = pytest.mark.django_db


def test_la_base_rechaza_un_banco_sin_nit():
    with pytest.raises(IntegrityError):
        ProveedorFactory(tipo=TipoProveedor.BANCO, nit="")


def test_varios_particulares_sin_nit_en_el_mismo_pais_se_aceptan():
    pais = PaisFactory()
    ProveedorFactory(tipo=TipoProveedor.PROPIETARIO_PARTICULAR, nit="", pais=pais)
    ProveedorFactory(tipo=TipoProveedor.PROPIETARIO_PARTICULAR, nit="", pais=pais)


def test_la_base_rechaza_el_mismo_nit_en_el_mismo_pais():
    pais = PaisFactory()
    ProveedorFactory(nit="123", pais=pais)
    with pytest.raises(IntegrityError):
        ProveedorFactory(nit="123", pais=pais)


def test_el_mismo_nit_en_otro_pais_se_acepta():
    ProveedorFactory(nit="123", pais=PaisFactory())
    ProveedorFactory(nit="123", pais=PaisFactory())


# ---------- ContratoCompra (spec 017, §4) ----------


def _contrato(**cambios):
    """Un contrato válido creado directo en la base, sin pasar por el servicio."""
    datos = {
        "codigo": None,
        "proveedor": ProveedorFactory(),
        "propiedad": PropiedadFactory(),
        "fecha_compra": timezone.localdate(),
        "monto": Decimal("100.00"),
        "gastos_legales": Decimal("10.00"),
        "impuestos": Decimal("5.00"),
        "costo_total": Decimal("115.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "tasa_a_usd": Decimal("1"),
        "costo_total_usd": Decimal("115.00"),
    }
    datos.update(cambios)
    return ContratoCompra.objects.create(**datos)


def test_la_base_rechaza_un_costo_total_que_no_es_la_suma():
    with pytest.raises(IntegrityError):
        _contrato(costo_total=Decimal("999.00"))


def test_la_base_rechaza_un_monto_cero():
    with pytest.raises(IntegrityError):
        _contrato(monto=Decimal("0"), costo_total=Decimal("15.00"))


def test_la_base_rechaza_dos_contratos_no_anulados_de_la_misma_propiedad():
    primero = _contrato()
    with pytest.raises(IntegrityError):
        _contrato(propiedad=primero.propiedad)


def test_varios_contratos_anulados_de_la_misma_propiedad_se_aceptan():
    primero = _contrato(estado=EstadoContratoCompra.ANULADO)
    _contrato(propiedad=primero.propiedad, estado=EstadoContratoCompra.ANULADO)
    _contrato(propiedad=primero.propiedad)
