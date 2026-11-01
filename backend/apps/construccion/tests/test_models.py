"""Pruebas de las restricciones de Constructora en la base (spec 006, §4)."""

import pytest
from django.db import IntegrityError

from apps.core.tests.factories import PaisFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db


def test_la_base_rechaza_una_constructora_sin_nit():
    with pytest.raises(IntegrityError):
        ConstructoraFactory(nit="")


def test_la_base_rechaza_el_mismo_nit_en_el_mismo_pais():
    pais = PaisFactory()
    ConstructoraFactory(nit="123", pais=pais)
    with pytest.raises(IntegrityError):
        ConstructoraFactory(nit="123", pais=pais)


@pytest.mark.parametrize("calificacion", [0, 6])
def test_la_base_rechaza_una_calificacion_fuera_de_1_a_5(calificacion):
    with pytest.raises(IntegrityError):
        ConstructoraFactory(calificacion=calificacion)


@pytest.mark.parametrize("calificacion", [None, 1, 5])
def test_la_base_acepta_sin_calificacion_o_de_1_a_5(calificacion):
    assert ConstructoraFactory(calificacion=calificacion).pk
