"""Pruebas de los proveedores de demostración (spec 006, §8)."""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.compras.enums import EstadoContratoCompra
from apps.compras.models import ContratoCompra, Proveedor
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


# ---------- Contratos de compra (spec 017) ----------


def test_carga_los_contratos_con_el_estado_de_su_propiedad_y_no_duplica():
    terreno = PropiedadFactory(
        nombre="Terreno Las Lomas", estado=EstadoPropiedad.EN_NEGOCIACION
    )
    PropiedadFactory(nombre="Gasolinera Ruta Sur", estado=EstadoPropiedad.ADQUIRIDA)
    PropiedadFactory(
        nombre="Hotel Brisas del Pacífico", estado=EstadoPropiedad.EN_CONSTRUCCION
    )
    correr()

    salida = correr()

    assert "contratos: 0 nuevos" in salida
    assert ContratoCompra.objects.count() == 3
    del_terreno = ContratoCompra.objects.get(propiedad=terreno)
    assert del_terreno.estado == EstadoContratoCompra.EN_PROCESO
    assert del_terreno.codigo == f"CC-{del_terreno.pk:05d}"
    assert del_terreno.costo_total == Decimal("262500.00")
    # La demo es una foto: el terreno sigue en negociación, listo para completar.
    terreno.refresh_from_db()
    assert terreno.estado == EstadoPropiedad.EN_NEGOCIACION
    assert not LogAuditoria.objects.filter(entidad="compras_contratocompra").exists()


def test_sin_las_propiedades_del_catalogo_no_carga_contratos_ni_falla():
    assert "contratos: 0 nuevos" in correr()
