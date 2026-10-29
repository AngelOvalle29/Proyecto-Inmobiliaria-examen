"""Pruebas de los selectores de catálogo."""

import pytest

from apps.catalogo.selectors import (
    listar_propiedades,
    listar_propiedades_publicas,
    listar_tipos_propiedad,
    listar_unidades,
)
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory

pytestmark = pytest.mark.django_db


def test_listar_tipos_propiedad_trae_los_siete_activos():
    assert listar_tipos_propiedad().count() == 7


def test_listar_propiedades_omite_las_desactivadas():
    activa = PropiedadFactory()
    PropiedadFactory(activo=False)

    assert list(listar_propiedades()) == [activa]


def test_listar_propiedades_publicas_solo_trae_publicas_y_activas():
    publica = PropiedadFactory(es_publica=True)
    PropiedadFactory(es_publica=False)
    PropiedadFactory(es_publica=True, activo=False)

    assert list(listar_propiedades_publicas()) == [publica]


def test_listar_unidades_filtra_por_propiedad_y_omite_desactivadas():
    unidad = UnidadFactory()
    UnidadFactory(propiedad=unidad.propiedad, activo=False)
    UnidadFactory()

    assert list(listar_unidades(propiedad=unidad.propiedad)) == [unidad]


def test_listar_unidades_omite_las_de_propiedades_desactivadas():
    UnidadFactory(propiedad=PropiedadFactory(activo=False))

    assert not listar_unidades().exists()
