"""Vistas de IA: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import ConsultaAgenteSerializer, RespuestaAgenteSerializer
from .services import responder_consulta_publica


class ConsultaAgenteView(APIView):
    """POST /api/v1/agente/consultas/: el agente público (spec 005, §5).

    Público a propósito: lo usa cualquier visitante del sitio. Por eso lleva
    límite de peticiones por IP, que además protege la cuota de Gemini.
    """

    # Sin autenticación: un token vencido de un usuario no debe convertir una
    # consulta pública en un 401.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "agente"

    @extend_schema(
        request=ConsultaAgenteSerializer,
        responses=RespuestaAgenteSerializer,
        summary="Preguntar al agente de IA",
    )
    def post(self, request):
        entrada = ConsultaAgenteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        resultado = responder_consulta_publica(
            pregunta=entrada.validated_data["pregunta"]
        )
        return Response(RespuestaAgenteSerializer(resultado).data)
