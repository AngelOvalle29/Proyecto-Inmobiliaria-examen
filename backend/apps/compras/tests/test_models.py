"""Pruebas de las restricciones de Proveedor en la base de datos (spec 006, §4)."""

import pytest
from django.db import IntegrityError

from apps.compras.enums import TipoProveedor
from apps.core.tests.factories import PaisFactory

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
