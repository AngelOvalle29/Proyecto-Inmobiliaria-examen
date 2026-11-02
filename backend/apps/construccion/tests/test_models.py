"""Pruebas de las restricciones de construcción en la base (specs 006 y 017, §4)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.catalogo.tests.factories import PropiedadFactory
from apps.construccion.enums import EstadoProyecto
from apps.construccion.models import ProyectoConstruccion
from apps.core.tests.factories import MonedaFactory, PaisFactory

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


# ---------- ProyectoConstruccion (spec 017, §4) ----------


def _proyecto(**cambios):
    """Un proyecto válido creado directo en la base, sin pasar por el servicio."""
    hoy = timezone.localdate()
    datos = {
        "nombre": "Obra demo",
        "propiedad": PropiedadFactory(),
        "constructora": ConstructoraFactory(),
        "fecha_inicio": hoy,
        "fecha_fin_estimada": hoy + timedelta(days=30),
        "presupuesto_total": Decimal("1000.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "tasa_a_usd": Decimal("1"),
        "presupuesto_total_usd": Decimal("1000.00"),
    }
    datos.update(cambios)
    return ProyectoConstruccion.objects.create(**datos)


def test_la_base_rechaza_un_presupuesto_cero():
    with pytest.raises(IntegrityError):
        _proyecto(presupuesto_total=Decimal("0"))


def test_la_base_rechaza_un_fin_estimado_antes_del_inicio():
    hoy = timezone.localdate()
    with pytest.raises(IntegrityError):
        _proyecto(fecha_inicio=hoy, fecha_fin_estimada=hoy - timedelta(days=1))


def test_la_base_rechaza_un_avance_mayor_que_100():
    with pytest.raises(IntegrityError):
        _proyecto(porcentaje_avance=101)


def test_la_base_rechaza_dos_proyectos_activos_de_la_misma_propiedad():
    primero = _proyecto()
    with pytest.raises(IntegrityError):
        _proyecto(propiedad=primero.propiedad, estado=EstadoProyecto.SUSPENDIDO)


def test_los_finalizados_y_cancelados_no_cuentan_como_activos():
    primero = _proyecto(estado=EstadoProyecto.FINALIZADO)
    _proyecto(propiedad=primero.propiedad, estado=EstadoProyecto.CANCELADO)
    _proyecto(propiedad=primero.propiedad)
