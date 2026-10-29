"""Pruebas de la carga de datos de demostración del catálogo."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.auditoria.models import LogAuditoria
from apps.catalogo import datos_demo
from apps.catalogo.models import Propiedad, Unidad
from apps.catalogo.services import cargar_demo_catalogo
from apps.core.services import cargar_catalogos_demo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def catalogos_de_core():
    """El catálogo usa las ciudades y monedas de demostración de core."""
    cargar_catalogos_demo(hasta=timezone.localdate())


def test_carga_las_propiedades_y_unidades_con_su_codigo():
    creados = cargar_demo_catalogo()

    total_unidades = sum(len(u) for u in datos_demo.UNIDADES.values())
    assert creados == {
        "propiedades": len(datos_demo.PROPIEDADES),
        "unidades": total_unidades,
    }
    for propiedad in Propiedad.objects.all():
        assert propiedad.codigo == f"PROP-{propiedad.pk:05d}"


def test_correrla_dos_veces_no_duplica():
    cargar_demo_catalogo()

    assert cargar_demo_catalogo() == {"propiedades": 0, "unidades": 0}
    assert Propiedad.objects.count() == len(datos_demo.PROPIEDADES)


def test_solo_hay_unidades_en_tipos_que_las_admiten():
    cargar_demo_catalogo()

    assert not Unidad.objects.filter(propiedad__tipo__requiere_unidades=False).exists()


def test_no_registra_auditoria():
    cargar_demo_catalogo()

    assert not LogAuditoria.objects.exists()


def test_el_comando_muestra_el_resumen():
    salida = StringIO()

    call_command("cargar_demo_catalogo", stdout=salida)

    assert f"propiedades: {len(datos_demo.PROPIEDADES)} nuevos" in salida.getvalue()
