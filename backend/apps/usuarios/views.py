"""Vistas de usuarios: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import GenericAPIView, ListCreateAPIView
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
from .selectors import listar_usuarios
from .serializers import (
    CambiarContrasenaSerializer,
    LoginSerializer,
    RenovarTokenSerializer,
    RestablecerContrasenaSerializer,
    TokensSerializer,
    UsuarioActualSerializer,
    UsuarioCrearSerializer,
    UsuarioDetalleSerializer,
    UsuarioEditarSerializer,
    UsuarioListadoSerializer,
)
from .services import (
    actualizar_usuario,
    cambiar_mi_contrasena,
    crear_usuario,
    desactivar_usuario,
    iniciar_sesion,
    reactivar_usuario,
    restablecer_contrasena,
)

# Spec 026, regla 1: solo administración gestiona cuentas.
SOLO_ADMINISTRADOR = [NombreRol.ADMINISTRADOR]


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

    Es la vista de SimpleJWT con dos cambios:
    - Un límite de peticiones propio y más alto que el login: el token de
      refresco es una firma que no se puede adivinar, así que el límite solo
      frena abusos, no ataques a contraseñas.
    - RenovarTokenSerializer, que responde 401 y no 500 si el usuario del token
      ya no existe.
    """

    serializer_class = RenovarTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "renovacion"


class UsuarioActualView(APIView):
    """GET /api/v1/auth/yo/ — datos del usuario dueño del token."""

    @extend_schema(responses={200: UsuarioActualSerializer}, summary="Usuario actual")
    def get(self, request: Request) -> Response:
        # request.user ya lo cargó la autenticación JWT a partir del token.
        return Response(UsuarioActualSerializer(request.user).data)


@extend_schema_view(
    post=extend_schema(
        request=UsuarioCrearSerializer, responses={201: UsuarioDetalleSerializer}
    )
)
class ListarUsuariosView(ListCreateAPIView):
    """
    GET /api/v1/usuarios/?estado=&rol=&buscar= — sin estado, los activos, para
    elegir el de un agente nuevo (spec 013). POST crea una cuenta (spec 026).

    Leen administración y gerencia: son quienes crean agentes, y el listado
    tiene correos y nombres de todo el personal. Crea solo administración.
    """

    serializer_class = UsuarioListadoSerializer
    filterset_class = UsuarioFilter
    permission_classes = [TieneRol]
    roles_por_metodo = {
        "GET": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE],
        "POST": SOLO_ADMINISTRADOR,
    }

    def get_queryset(self):
        # El filtro estado decide activos, inactivos o todos.
        return listar_usuarios(estado="TODOS")

    def create(self, request: Request, *args, **kwargs) -> Response:
        entrada = UsuarioCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        password = datos.pop("password")
        usuario = crear_usuario(
            datos=datos,
            password=password,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(UsuarioDetalleSerializer(usuario).data, status=201)


class UsuarioDetalleView(GenericAPIView):
    """GET y PATCH /api/v1/usuarios/{id}/ — nombre, rol, país y teléfono."""

    serializer_class = UsuarioDetalleSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": SOLO_ADMINISTRADOR, "PATCH": SOLO_ADMINISTRADOR}

    def get_queryset(self):
        return listar_usuarios(estado="TODOS")

    def get(self, request: Request, pk: int) -> Response:
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(
        request=UsuarioEditarSerializer, responses={200: UsuarioDetalleSerializer}
    )
    def patch(self, request: Request, pk: int) -> Response:
        entrada = UsuarioEditarSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        usuario = actualizar_usuario(
            usuario=self.get_object(),
            datos=dict(entrada.validated_data),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(self.get_serializer(usuario).data)


class AccionUsuarioView(GenericAPIView):
    """Base de /desactivar/ y /reactivar/: sin cuerpo, responde el usuario."""

    serializer_class = UsuarioDetalleSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": SOLO_ADMINISTRADOR}
    servicio = None

    def get_queryset(self):
        return listar_usuarios(estado="TODOS")

    @extend_schema(request=None, responses={200: UsuarioDetalleSerializer})
    def post(self, request: Request, pk: int) -> Response:
        usuario = type(self).servicio(
            usuario=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(self.get_serializer(usuario).data)


class DesactivarUsuarioView(AccionUsuarioView):
    """POST /api/v1/usuarios/{id}/desactivar/ (spec 026, reglas 4, 5, 7 y 8)."""

    servicio = staticmethod(desactivar_usuario)


class ReactivarUsuarioView(AccionUsuarioView):
    """POST /api/v1/usuarios/{id}/reactivar/"""

    servicio = staticmethod(reactivar_usuario)


class RestablecerContrasenaView(GenericAPIView):
    """POST /api/v1/usuarios/{id}/restablecer-contrasena/ — responde 204."""

    serializer_class = RestablecerContrasenaSerializer
    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": SOLO_ADMINISTRADOR}

    def get_queryset(self):
        return listar_usuarios(estado="TODOS")

    @extend_schema(responses={204: None})
    def post(self, request: Request, pk: int) -> Response:
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        restablecer_contrasena(
            usuario=self.get_object(),
            password=entrada.validated_data["password"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(status=204)


class CambiarContrasenaView(GenericAPIView):
    """
    POST /api/v1/auth/cambiar-contrasena/ — cualquier usuario con sesión cambia
    la suya dando la actual (spec 026, regla 9). Responde 204.
    """

    serializer_class = CambiarContrasenaSerializer

    @extend_schema(responses={204: None})
    def post(self, request: Request) -> Response:
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cambiar_mi_contrasena(
            usuario=request.user,
            actual=entrada.validated_data["actual"],
            nueva=entrada.validated_data["nueva"],
            ip=obtener_ip_cliente(request),
        )
        return Response(status=204)
