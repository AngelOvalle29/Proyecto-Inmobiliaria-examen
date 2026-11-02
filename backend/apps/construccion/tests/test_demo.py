"""Pruebas de las constructoras de demostración (spec 006, §8)."""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory
from apps.construccion.enums import EstadoPago, EstadoProyecto
from apps.construccion.models import (
    Constructora,
    PagoConstructora,
    ProyectoConstruccion,
)
from apps.construccion.selectors import total_comprometido
from apps.construccion.services import finalizar_proyecto, registrar_avance
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
    assert "constructoras: 0 nuevos" in salida
    assert not Constructora.objects.filter(codigo__isnull=True).exists()


def test_sin_los_paises_no_carga_nada_ni_falla():
    assert "constructoras: 0 nuevos" in correr()


# ---------- Proyectos y pagos (spec 017) ----------


def _propiedades_demo():
    """Las dos propiedades de la demo del catálogo que usan los proyectos."""
    PaisFactory(codigo_iso="GTM")
    PaisFactory(codigo_iso="MEX")
    return {
        "hotel": PropiedadFactory(
            nombre="Hotel Brisas del Pacífico", estado=EstadoPropiedad.EN_CONSTRUCCION
        ),
        "gasolinera": PropiedadFactory(
            nombre="Gasolinera Ruta Sur", estado=EstadoPropiedad.ADQUIRIDA
        ),
    }


def test_carga_proyectos_y_pagos_coherentes_y_no_duplica():
    propiedades = _propiedades_demo()
    correr()

    salida = correr()

    assert "proyectos: 0 nuevos" in salida
    assert ProyectoConstruccion.objects.count() == 2
    assert PagoConstructora.objects.count() == 4
    hotel = ProyectoConstruccion.objects.get(propiedad=propiedades["hotel"])
    assert hotel.estado == EstadoProyecto.EN_EJECUCION
    assert hotel.codigo == f"PC-{hotel.pk:05d}"
    # Regla 19: lo comprometido cabe en el presupuesto.
    assert total_comprometido(proyecto=hotel) <= hotel.presupuesto_total
    # Un pago PAGADO tiene sus datos completos (lo exige también la base).
    for pago in hotel.pagos.filter(estado=EstadoPago.PAGADO):
        assert pago.fecha_pago and pago.referencia_pago and pago.monto_usd
    # La demo es una foto: no cambia el estado de las propiedades.
    propiedades["hotel"].refresh_from_db()
    assert propiedades["hotel"].estado == EstadoPropiedad.EN_CONSTRUCCION
    assert hotel.tasa_a_usd == Decimal("1")


def test_la_obra_del_hotel_de_la_demo_se_puede_finalizar_por_el_servicio():
    """La demo queda lista para mostrar el cierre de la obra en la defensa."""
    propiedades = _propiedades_demo()
    suite = UnidadFactory(
        propiedad=propiedades["hotel"], estado=EstadoPropiedad.EN_CONSTRUCCION
    )
    correr()
    hotel = ProyectoConstruccion.objects.get(propiedad=propiedades["hotel"])

    registrar_avance(
        proyecto=hotel, porcentaje=100, descripcion="Fin", autor=None, ip=None
    )
    finalizar_proyecto(proyecto=hotel, autor=None, ip=None)

    suite.refresh_from_db()
    assert suite.estado == EstadoPropiedad.DISPONIBLE


def test_sin_las_propiedades_del_catalogo_no_carga_proyectos_ni_falla():
    PaisFactory(codigo_iso="GTM")
    PaisFactory(codigo_iso="MEX")
    assert "proyectos: 0 nuevos" in correr()


def test_los_proyectos_de_la_demo_no_registran_auditoria():
    _propiedades_demo()
    correr()
    assert not LogAuditoria.objects.filter(
        entidad__in=[
            "construccion_proyectoconstruccion",
            "construccion_pagoconstructora",
        ]
    ).exists()
