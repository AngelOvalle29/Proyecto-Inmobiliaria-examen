"""Pruebas de los datos de demostración de ventas (spec 007, paso 5)."""

import pytest
from django.core.management import call_command

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.models import Unidad
from apps.crm.enums import EstadoCotizacion
from apps.crm.models import Cotizacion
from apps.ventas.enums import EstadoContrato, EstadoCuota
from apps.ventas.models import ContratoVenta

pytestmark = pytest.mark.django_db


def test_seed_demo_carga_ventas_coherentes_y_no_duplica(monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("seed_demo")
    call_command("seed_demo")

    assert ContratoVenta.objects.count() == 3
    assert Cotizacion.objects.count() == 5

    financiado = ContratoVenta.objects.get(modalidad="FINANCIADO")
    cuotas = list(financiado.cuotas.order_by("numero")[:3])
    assert [c.estado for c in cuotas] == [
        EstadoCuota.PAGADA,
        EstadoCuota.PARCIAL,
        EstadoCuota.PENDIENTE,
    ]
    assert cuotas[1].en_mora() and cuotas[2].en_mora()
    assert financiado.estado == EstadoContrato.VIGENTE

    contado = ContratoVenta.objects.get(modalidad="CONTADO", cotizacion=None)
    assert contado.estado == EstadoContrato.LIQUIDADO

    con_cotizacion = ContratoVenta.objects.get(cotizacion__isnull=False)
    assert con_cotizacion.cotizacion.descuento > 0
    assert con_cotizacion.monto_total == con_cotizacion.cotizacion.total

    estados = list(Cotizacion.objects.values_list("estado", flat=True))
    assert estados.count(EstadoCotizacion.APROBADA) == 2
    assert {
        EstadoCotizacion.BORRADOR,
        EstadoCotizacion.ENVIADA,
        EstadoCotizacion.RECHAZADA,
    } < set(estados)


def test_seed_demo_deja_unidades_para_vender_en_vivo(monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("seed_demo")

    disponibles = Unidad.objects.filter(estado=EstadoPropiedad.DISPONIBLE)
    assert {"A-103", "A-203"} <= set(disponibles.values_list("codigo", flat=True))
