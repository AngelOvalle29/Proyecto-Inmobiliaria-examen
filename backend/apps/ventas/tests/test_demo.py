"""Pruebas de los datos de demostración de ventas (spec 007, paso 5)."""

import pytest
from django.core.management import call_command

from apps.crm.enums import EstadoCotizacion
from apps.crm.models import Cotizacion
from apps.ventas.enums import EstadoContrato, EstadoCuota
from apps.ventas.models import ContratoVenta

pytestmark = pytest.mark.django_db


def test_seed_demo_carga_ventas_coherentes_y_no_duplica(monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("seed_demo")
    call_command("seed_demo")

    assert ContratoVenta.objects.count() == 2
    assert Cotizacion.objects.count() == 1

    financiado = ContratoVenta.objects.get(modalidad="FINANCIADO")
    cuotas = list(financiado.cuotas.order_by("numero")[:3])
    assert [c.estado for c in cuotas] == [
        EstadoCuota.PAGADA,
        EstadoCuota.PARCIAL,
        EstadoCuota.PENDIENTE,
    ]
    assert cuotas[1].en_mora() and cuotas[2].en_mora()
    assert financiado.estado == EstadoContrato.VIGENTE

    contado = ContratoVenta.objects.get(modalidad="CONTADO")
    assert contado.estado == EstadoContrato.LIQUIDADO
    assert Cotizacion.objects.filter(estado=EstadoCotizacion.APROBADA).count() == 1
