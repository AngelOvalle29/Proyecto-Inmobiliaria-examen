"""Pruebas de los endpoints de core: un caso feliz y uno de error."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    return APIClient()


def test_health_responde_200_sin_autenticacion(cliente):
    respuesta = cliente.get("/api/v1/health/")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_datos": "ok"}


def test_health_responde_503_si_la_base_no_responde(cliente, monkeypatch):
    # Se simula la caída reemplazando el selector, no apagando PostgreSQL.
    monkeypatch.setattr("apps.core.views.verificar_base_datos", lambda: False)

    respuesta = cliente.get("/api/v1/health/")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "error", "base_datos": "error"}


def test_un_error_de_la_api_sale_en_el_formato_uniforme(cliente):
    """Prueba de punta a punta del manejador: health solo acepta GET."""
    respuesta = cliente.post("/api/v1/health/")

    assert respuesta.status_code == 405
    assert respuesta.json()["error"]["codigo"] == "METODO_NO_PERMITIDO"


def test_la_documentacion_esta_disponible(cliente):
    assert cliente.get("/api/docs/").status_code == 200


def test_el_esquema_incluye_los_endpoints(cliente):
    respuesta = cliente.get("/api/schema/", {"format": "json"})

    assert respuesta.status_code == 200
    assert "/api/v1/health/" in respuesta.json()["paths"]


def test_cors_permite_al_frontend_y_rechaza_otros_origenes(cliente, settings):
    """arquitectura.md §9: CORS restringido al dominio del frontend."""
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    permitido = cliente.get("/api/v1/health/", HTTP_ORIGIN="http://localhost:5173")
    ajeno = cliente.get("/api/v1/health/", HTTP_ORIGIN="https://sitio-ajeno.test")

    assert permitido["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in ajeno
