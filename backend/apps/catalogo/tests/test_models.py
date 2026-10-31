"""Pruebas de los modelos de catálogo: tipos iniciales y constraints (spec 003)."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.models import (
    TAMANO_MAXIMO_DOCUMENTO,
    TipoPropiedad,
    ruta_documento,
)

from .factories import (
    AvaluoFactory,
    DocumentoOficialFactory,
    PropiedadFactory,
    UnidadFactory,
)

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


def test_la_base_rechaza_un_avaluo_con_valor_cero():
    """Regla 1 de la spec 011: el valor es mayor que cero."""
    with pytest.raises(IntegrityError):
        AvaluoFactory(valor=Decimal("0"))


def test_la_base_rechaza_un_vencimiento_anterior_a_la_emision():
    """Regla 5 de la spec 011."""
    with pytest.raises(IntegrityError):
        DocumentoOficialFactory(
            fecha_emision=date(2026, 1, 10),
            fecha_vencimiento=date(2026, 1, 9),
        )


def test_la_base_rechaza_un_documento_de_mas_de_diez_megas():
    """Regla 6 de la spec 011."""
    with pytest.raises(IntegrityError):
        DocumentoOficialFactory(tamano_bytes=TAMANO_MAXIMO_DOCUMENTO + 1)


def test_la_ruta_del_documento_usa_el_codigo_y_un_uuid():
    """Regla 8 de la spec 011."""
    documento = DocumentoOficialFactory()

    ruta = ruta_documento(documento, "Mi Escritura.PDF")

    assert ruta.startswith(f"documentos/{documento.propiedad.codigo}/")
    assert ruta.endswith(".pdf")
    assert ruta != ruta_documento(documento, "Mi Escritura.PDF")
