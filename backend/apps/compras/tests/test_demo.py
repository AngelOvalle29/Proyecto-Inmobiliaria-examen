"""Pruebas de los proveedores de demostración (spec 006, §8)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.auditoria.models import LogAuditoria
from apps.compras.models import Proveedor
from apps.core.tests.factories import PaisFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def paises_demo():
    return [PaisFactory(codigo_iso="GTM"), PaisFactory(codigo_iso="MEX")]


def correr() -> str:
    salida = StringIO()
    call_command("cargar_demo_compras", stdout=salida)
    return salida.getvalue()


def test_carga_los_proveedores_con_su_codigo_y_no_duplica():
    correr()
    cantidad = Proveedor.objects.count()

    salida = correr()

    assert cantidad == 6
    assert Proveedor.objects.count() == 6
    assert "proveedores: 0 nuevos" in salida
    assert not Proveedor.objects.filter(codigo__isnull=True).exists()


def test_no_registra_auditoria():
    correr()
    assert not LogAuditoria.objects.filter(entidad="compras_proveedor").exists()
