"""Pruebas de los datos de demostración de CRM (spec 004, incremento 8)."""

from datetime import date

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command

from apps.core.services import cargar_catalogos_demo
from apps.crm import datos_demo
from apps.crm.models import Agente, Cliente

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalogos_core():
    """Países y ciudades de core, que seed_demo carga antes que crm."""
    cargar_catalogos_demo(hasta=date(2026, 10, 1))


def test_carga_agentes_y_clientes_y_no_duplica(catalogos_core, monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("cargar_demo_crm")
    call_command("cargar_demo_crm")

    assert Agente.objects.count() == len(datos_demo.AGENTES)
    assert Cliente.objects.count() == len(datos_demo.CLIENTES)
    assert not Agente.objects.filter(codigo__isnull=True).exists()
    assert not Cliente.objects.filter(codigo__isnull=True).exists()


def test_cada_agente_tiene_su_cartera(catalogos_core, monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("cargar_demo_crm")

    for agente in Agente.objects.all():
        assert agente.clientes.exists()
        assert agente.usuario.pais is not None


def test_sin_la_variable_los_agentes_no_pueden_iniciar_sesion(
    catalogos_core, monkeypatch
):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("cargar_demo_crm")

    agente = Agente.objects.first()
    assert not agente.usuario.has_usable_password()
    assert authenticate(email=agente.usuario.email, password="") is None


def test_con_la_variable_los_agentes_inician_sesion(catalogos_core, monkeypatch):
    monkeypatch.setenv("DEMO_AGENTES_PASSWORD", "contrasena-de-prueba-123")

    call_command("cargar_demo_crm")

    email = datos_demo.AGENTES[0][0]
    assert authenticate(email=email, password="contrasena-de-prueba-123") is not None


def test_la_variable_vacia_cuenta_como_no_definida(catalogos_core, monkeypatch):
    monkeypatch.setenv("DEMO_AGENTES_PASSWORD", "")

    call_command("cargar_demo_crm")

    assert not Agente.objects.first().usuario.has_usable_password()


def test_seed_demo_llama_a_cargar_demo_crm(monkeypatch):
    """seed_demo lo invoca por nombre (COMANDOS_DE_DEMO, #34)."""
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("seed_demo")

    assert Cliente.objects.count() == len(datos_demo.CLIENTES)
