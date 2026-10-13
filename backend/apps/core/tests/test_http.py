"""Pruebas de la obtención de la IP del cliente detrás de proxies."""

import pytest
from rest_framework.test import APIRequestFactory

from apps.core.http import obtener_ip_cliente


@pytest.fixture
def peticion():
    """Petición que llega con X-Forwarded-For: un valor inventado y uno real."""
    return APIRequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7",
    )


def test_sin_proxies_ignora_x_forwarded_for(peticion, settings):
    """En desarrollo no hay proxy: la cabecera la escribió el cliente."""
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}

    assert obtener_ip_cliente(peticion) == "10.0.0.1"


def test_con_un_proxy_usa_la_ip_que_agrego_el_proxy(peticion, settings):
    """
    El cliente envió "1.2.3.4" para hacerse pasar por otro; el proxy agregó
    al final la IP real, 198.51.100.7, y esa es la que se registra.
    """
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}

    assert obtener_ip_cliente(peticion) == "198.51.100.7"
