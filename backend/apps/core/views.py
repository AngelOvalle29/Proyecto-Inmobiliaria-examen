"""Vistas de core: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import verificar_base_datos
from .serializers import EstadoServicioSerializer


class EstadoServicioView(APIView):
    """
    GET /api/v1/health/

    Público: lo consultan Railway y el Dockerfile para saber si el contenedor
    está sano, sin credenciales. Responde 503 si la base de datos no responde,
    para que la plataforma sepa que el servicio no puede atender.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: EstadoServicioSerializer, 503: EstadoServicioSerializer},
        summary="Estado del servicio",
    )
    def get(self, request: Request) -> Response:
        if verificar_base_datos():
            datos = {"estado": "ok", "base_datos": "ok"}
            codigo = status.HTTP_200_OK
        else:
            datos = {"estado": "error", "base_datos": "error"}
            codigo = status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(EstadoServicioSerializer(datos).data, status=codigo)
