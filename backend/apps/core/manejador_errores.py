"""
Manejador global de errores de la API (docs/arquitectura.md §4, spec 001 §5).

DRF llama a manejar_excepcion cada vez que una vista lanza una excepción.
Aquí se convierte en la respuesta uniforme:

    {"error": {"codigo": "...", "mensaje": "...", "detalles": {...}}}

Así el frontend lee siempre la misma forma, sin importar si el error vino de
una regla de negocio, de una validación o de la autenticación.
"""

from django.core.exceptions import PermissionDenied as PermisoDenegadoDjango
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .exceptions import ErrorDominio

# Código para cada tipo de error de DRF o de Django. Se recorre en orden y gana
# el primero que coincida.
CODIGOS = [
    (exceptions.ValidationError, "VALIDACION"),
    (exceptions.ParseError, "SOLICITUD_MAL_FORMADA"),
    (exceptions.NotAuthenticated, "NO_AUTENTICADO"),
    (exceptions.AuthenticationFailed, "NO_AUTENTICADO"),
    (exceptions.PermissionDenied, "SIN_PERMISO"),
    (PermisoDenegadoDjango, "SIN_PERMISO"),
    (exceptions.NotFound, "NO_ENCONTRADO"),
    (Http404, "NO_ENCONTRADO"),
    (exceptions.MethodNotAllowed, "METODO_NO_PERMITIDO"),
    (exceptions.UnsupportedMediaType, "FORMATO_NO_SOPORTADO"),
    (exceptions.Throttled, "DEMASIADAS_PETICIONES"),
]

MENSAJE_NO_ENCONTRADO = "No se encontró el recurso."


def manejar_excepcion(exc: Exception, context: dict) -> Response | None:
    # 1. Reglas de negocio: la excepción ya trae todo lo necesario.
    if isinstance(exc, ErrorDominio):
        return Response(
            _cuerpo(exc.codigo, exc.mensaje, exc.detalles), status=exc.estado_http
        )

    # 2. Errores que DRF sabe manejar. Se deja que DRF arme la respuesta
    #    primero porque elige el estado HTTP correcto y agrega cabeceras
    #    necesarias (WWW-Authenticate en un 401, Retry-After en un 429); aquí
    #    solo se reemplaza el cuerpo.
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        # 3. Error no previsto (un fallo de programación): se deja pasar para
        #    que Django responda 500 y lo registre con su traza completa.
        return None

    if isinstance(exc, exceptions.ValidationError):
        mensaje = "Los datos enviados no son válidos."
        # Errores por campo, {"email": ["Este campo es requerido."]}, o una
        # lista de errores generales si no corresponden a un campo.
        if isinstance(respuesta.data, dict):
            detalles = respuesta.data
        else:
            detalles = {"errores": respuesta.data}
    elif isinstance(exc, (exceptions.NotFound, Http404)):
        # get_object_or_404 lanza Http404 con un mensaje de Django en inglés
        # y con el nombre del modelo ("No ContratoVenta matches the given
        # query."). Al usuario no le dice nada y expone cómo está hecho el
        # sistema, así que todo 404 sale con el mismo mensaje.
        mensaje = MENSAJE_NO_ENCONTRADO
        detalles = {}
    else:
        mensaje = str(respuesta.data.get("detail", "Error en la solicitud."))
        detalles = {}
        if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
            detalles = {"espera_segundos": int(exc.wait)}

    respuesta.data = _cuerpo(_codigo_de(exc), mensaje, detalles)
    return respuesta


def _codigo_de(exc: Exception) -> str:
    for tipo, codigo in CODIGOS:
        if isinstance(exc, tipo):
            return codigo
    return "ERROR_SOLICITUD"


def _cuerpo(codigo: str, mensaje: str, detalles: dict) -> dict:
    return {"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles}}
