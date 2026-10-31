"""
Pruebas del manejador global de errores.

Se llama a manejar_excepcion directamente con cada tipo de excepción, sin
pasar por una vista: así se prueba la traducción sin depender de que exista
un endpoint que lance cada error.
"""

from datetime import date

from django.http import Http404
from rest_framework import exceptions

from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.manejador_errores import manejar_excepcion


def test_un_error_de_dominio_usa_su_codigo_y_su_estado():
    error = TipoCambioNoDisponible(origen="USD", destino="GTQ", fecha=date(2026, 10, 1))

    respuesta = manejar_excepcion(error, context={})

    assert respuesta.status_code == 422
    assert respuesta.data == {
        "error": {
            "codigo": "TIPO_CAMBIO_NO_DISPONIBLE",
            "mensaje": "No hay tipo de cambio de USD a GTQ vigente al 01/10/2026.",
            "detalles": {
                "moneda_origen": "USD",
                "moneda_destino": "GTQ",
                "fecha": "2026-10-01",
            },
        }
    }


def test_un_error_de_validacion_lleva_los_errores_por_campo():
    error = exceptions.ValidationError({"email": ["Este campo es requerido."]})

    respuesta = manejar_excepcion(error, context={})

    assert respuesta.status_code == 400
    assert respuesta.data["error"]["codigo"] == "VALIDACION"
    assert respuesta.data["error"]["detalles"] == {
        "email": ["Este campo es requerido."]
    }


def test_sin_autenticacion_responde_no_autenticado():
    respuesta = manejar_excepcion(exceptions.NotAuthenticated(), context={})

    assert respuesta.data["error"]["codigo"] == "NO_AUTENTICADO"


def test_el_404_de_django_tambien_sale_en_el_formato_uniforme():
    respuesta = manejar_excepcion(Http404(), context={})

    assert respuesta.status_code == 404
    assert respuesta.data["error"]["codigo"] == "NO_ENCONTRADO"


def test_el_404_no_muestra_el_mensaje_de_django_ni_el_nombre_del_modelo():
    """get_object_or_404 lanza Http404 con un texto en inglés que nombra el
    modelo; la respuesta debe decir lo mismo para cualquier recurso."""
    respuesta = manejar_excepcion(
        Http404("No ContratoVenta matches the given query."), context={}
    )

    assert respuesta.data["error"] == {
        "codigo": "NO_ENCONTRADO",
        "mensaje": "No se encontró el recurso.",
        "detalles": {},
    }


def test_el_limite_de_peticiones_indica_cuanto_esperar():
    respuesta = manejar_excepcion(exceptions.Throttled(wait=42), context={})

    assert respuesta.status_code == 429
    assert respuesta.data["error"]["codigo"] == "DEMASIADAS_PETICIONES"
    assert respuesta.data["error"]["detalles"] == {"espera_segundos": 42}
    # La cabecera estándar que indica cuándo reintentar se conserva.
    assert respuesta["Retry-After"] == "42"


def test_un_error_no_previsto_se_deja_pasar_como_500():
    """Un fallo de programación no se disfraza: Django responde 500 y lo registra."""
    assert manejar_excepcion(ZeroDivisionError(), context={}) is None
