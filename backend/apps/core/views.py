"""Vistas de core: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import CiudadFilter, TipoCambioFilter
from .selectors import (
    listar_ciudades,
    listar_monedas,
    listar_paises,
    listar_tipos_cambio,
    verificar_base_datos,
)
from .serializers import (
    CiudadSerializer,
    EstadoServicioSerializer,
    MonedaSerializer,
    PaisSerializer,
    TipoCambioSerializer,
)


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


# ---------- Catálogos (solo lectura) ----------
#
# Cada vista solo declara qué selector da los datos, cómo se serializan y qué
# filtros acepta. Paginación (25), autenticación y permiso (autenticado) vienen
# de REST_FRAMEWORK en settings. Los catálogos se editan desde el panel de
# Django en esta fase (spec 001, §5).


class ListarMonedasView(ListAPIView):
    """GET /api/v1/monedas/"""

    serializer_class = MonedaSerializer

    def get_queryset(self):
        return listar_monedas()


class ListarPaisesView(ListAPIView):
    """GET /api/v1/paises/"""

    serializer_class = PaisSerializer

    def get_queryset(self):
        return listar_paises()


class ListarCiudadesView(ListAPIView):
    """GET /api/v1/ciudades/?pais=<id>"""

    serializer_class = CiudadSerializer
    filterset_class = CiudadFilter

    def get_queryset(self):
        return listar_ciudades()


class ListarTiposCambioView(ListAPIView):
    """GET /api/v1/tipos-cambio/?moneda_origen=&moneda_destino=&fecha_desde=…"""

    serializer_class = TipoCambioSerializer
    filterset_class = TipoCambioFilter

    def get_queryset(self):
        return listar_tipos_cambio()
