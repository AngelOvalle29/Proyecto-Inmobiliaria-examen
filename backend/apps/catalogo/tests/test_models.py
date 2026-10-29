"""Pruebas de los modelos de catálogo: tipos iniciales y constraints (spec 003)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.models import TipoPropiedad

from .factories import PropiedadFactory, UnidadFactory

pytestmark = pytest.mark.django_db


def test_los_siete_tipos_existen_despues_de_migrar():
    nombres = set(TipoPropiedad.objects.values_list("nombre", flat=True))

    assert nombres == {
        "Apartamentos",
        "Terreno",
        "Casa",
        "Hotel",
        "Bodega",
        "Restaurante",
        "Gasolinera",
    }
    con_unidades = set(
        TipoPropiedad.objects.filter(requiere_unidades=True).values_list(
            "nombre", flat=True
        )
    )
    assert con_unidades == {"Apartamentos", "Hotel"}


def test_una_propiedad_nueva_empieza_en_negociacion():
    assert PropiedadFactory().estado == EstadoPropiedad.EN_NEGOCIACION


@pytest.mark.parametrize("campo", ["precio_lista", "area_m2", "area_construida_m2"])
def test_la_base_rechaza_precios_y_areas_no_positivos(campo):
    """Regla 4."""
    with pytest.raises(IntegrityError):
        PropiedadFactory(**{campo: Decimal("0")})


def test_dos_unidades_con_el_mismo_codigo_en_la_misma_propiedad_se_rechazan():
    """Regla 3."""
    unidad = UnidadFactory(codigo="A-101")

    with pytest.raises(IntegrityError):
        UnidadFactory(propiedad=unidad.propiedad, codigo="A-101")


def test_el_mismo_codigo_de_unidad_en_otra_propiedad_se_acepta():
    UnidadFactory(codigo="A-101")

    assert UnidadFactory(codigo="A-101").codigo == "A-101"
