"""Pruebas de las constructoras de demostración (spec 006, §8)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.construccion.models import Constructora
from apps.core.tests.factories import PaisFactory

pytestmark = pytest.mark.django_db


def correr() -> str:
    salida = StringIO()
    call_command("cargar_demo_construccion", stdout=salida)
    return salida.getvalue()


def test_carga_las_constructoras_y_no_duplica():
    PaisFactory(codigo_iso="GTM")
    PaisFactory(codigo_iso="MEX")
    correr()

    salida = correr()

    assert Constructora.objects.count() == 4
    assert "constructoras: 0 nuevas" in salida
    assert not Constructora.objects.filter(codigo__isnull=True).exists()


def test_sin_los_paises_no_carga_nada_ni_falla():
    assert "constructoras: 0 nuevas" in correr()
