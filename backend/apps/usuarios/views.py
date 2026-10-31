"""Vistas de usuarios: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.http import obtener_ip_cliente, obtener_user_agent

from .enums import NombreRol
from .filters import UsuarioFilter
from .permissions import TieneRol
from .selectors import listar_usuarios_activos
from .serializers import (
    LoginSerializer,
    TokensSerializer,
    UsuarioActualSerializer,
    UsuarioListadoSerializer,
)
from .services import iniciar_sesion


class LoginView(APIView):
    """POST /api/v1/auth/login/ — par de tokens a cambio de correo y contraseña."""

    authentication_classes = []
    permission_classes = [AllowAny]
    # 30 intentos por minuto por IP: frena a quien prueba contraseñas en masa
    # sin bloquear a varias personas que entran desde la misma red.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: TokensSerializer},
        summary="Iniciar sesión",
    )
    def post(self, request: Request) -> Response:
        entrada = LoginSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        tokens = iniciar_sesion(
            email=entrada.validated_data["email"],
            password=entrada.validated_data["password"],
            ip=obtener_ip_cliente(request),
            user_agent=obtener_user_agent(request),
        )
        return Response(TokensSerializer(tokens).data)


class RenovarTokenView(TokenRefreshView):
    """
    POST /api/v1/auth/refresh/ — nuevo token de acceso a cambio del de refresco.

    Es la vista de SimpleJWT sin cambios, salvo el límite de peticiones. Tiene
    uno propio y más alto que el login: el token de refresco es una firma que
    no se puede adivinar, así que el límite solo frena abusos, no ataques a
    contraseñas.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "renovacion"


class UsuarioActualView(APIView):
    """GET /api/v1/auth/yo/ — datos del usuario dueño del token."""

    @extend_schema(responses={200: UsuarioActualSerializer}, summary="Usuario actual")
    def get(self, request: Request) -> Response:
        # request.user ya lo cargó la autenticación JWT a partir del token.
        return Response(UsuarioActualSerializer(request.user).data)


class ListarUsuariosView(ListAPIView):
    """
    GET /api/v1/usuarios/?rol=&buscar= — usuarios activos, para elegir el de un
    agente nuevo (spec 013).

    Solo administración y gerencia: son quienes crean agentes, y el listado
    tiene correos y nombres de todo el personal. Como GET queda declarado en
    roles_por_metodo, TieneRol ya no lo deja abierto a cualquier autenticado.
    """

    serializer_class = UsuarioListadoSerializer
    filterset_class = UsuarioFilter
    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]}

    def get_queryset(self):
        return listar_usuarios_activos()
