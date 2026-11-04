"""Vistas de CRM: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos. Cada vista declara
qué roles pueden escribir (roles_por_metodo, spec 004 §6); qué registros ve
cada usuario lo decide el selector.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import AgenteFilter, ClienteFilter, CotizacionFilter
from .models import Agente, Cliente, Cotizacion
from .selectors import (
    listar_agentes_visibles,
    listar_clientes_visibles,
    listar_cotizaciones_visibles,
    obtener_agente,
)
from .serializers import (
    AgenteCrearSerializer,
    AgenteEditarSerializer,
    AgenteSerializer,
    ClienteEntradaSerializer,
    ClienteSerializer,
    CotizacionCrearSerializer,
    CotizacionEditarSerializer,
    CotizacionSerializer,
    ReasignarClienteSerializer,
)
from .services import (
    actualizar_agente,
    actualizar_cliente,
    actualizar_cotizacion,
    aprobar_cotizacion,
    crear_agente,
    crear_cliente,
    crear_cotizacion,
    desactivar_agente,
    desactivar_cliente,
    enviar_cotizacion,
    reasignar_cliente,
    rechazar_cotizacion,
)

# Regla 11: solo ellos administran agentes y reasignan clientes.
ADMINISTRAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
# Reglas 11 y 12: los agentes también escriben, pero solo sobre su cartera.
ESCRIBEN_CLIENTES = [*ADMINISTRAN, NombreRol.AGENTE]


def _clientes_visibles(vista):
    """
    Clientes que puede ver quien hace la petición (selector de cartera).

    drf-spectacular llama a get_queryset sin un usuario real cuando genera el
    esquema de /api/docs/ (swagger_fake_view); en ese caso no hay cartera que
    calcular y basta una consulta vacía del modelo, que no toca la base.
    """
    if getattr(vista, "swagger_fake_view", False):
        return Cliente.objects.none()
    return listar_clientes_visibles(usuario=vista.request.user)


# ---------- Agentes ----------


def _agentes_visibles(vista):
    """Igual que _clientes_visibles: un AGENTE solo ve su perfil (spec 024)."""
    if getattr(vista, "swagger_fake_view", False):
        return Agente.objects.none()
    return listar_agentes_visibles(usuario=vista.request.user)


class AgentesView(ListAPIView):
    """GET y POST /api/v1/agentes/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRAN}
    serializer_class = AgenteSerializer
    filterset_class = AgenteFilter

    def get_queryset(self):
        return _agentes_visibles(self)

    @extend_schema(
        request=AgenteCrearSerializer,
        responses={201: AgenteSerializer},
        summary="Crear el perfil de agente de un usuario",
    )
    def post(self, request: Request) -> Response:
        entrada = AgenteCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        agente = crear_agente(
            usuario_agente=entrada.validated_data["usuario"],
            porcentaje_comision=entrada.validated_data["porcentaje_comision"],
            fecha_ingreso=entrada.validated_data["fecha_ingreso"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        # Se vuelve a leer con el selector para incluir clientes_activos.
        salida = AgenteSerializer(obtener_agente(agente_id=agente.pk))
        return Response(salida.data, status=status.HTTP_201_CREATED)


class AgenteDetalleView(RetrieveAPIView):
    """GET, PATCH y DELETE /api/v1/agentes/{id}/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": ADMINISTRAN, "DELETE": ADMINISTRAN}
    serializer_class = AgenteSerializer

    def get_queryset(self):
        return _agentes_visibles(self)

    @extend_schema(
        request=AgenteEditarSerializer,
        responses={200: AgenteSerializer},
        summary="Editar comisión o fecha de ingreso",
    )
    def patch(self, request: Request, pk: int) -> Response:
        agente = self.get_object()
        entrada = AgenteEditarSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        actualizar_agente(
            agente=agente,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(AgenteSerializer(obtener_agente(agente_id=agente.pk)).data)

    @extend_schema(responses={204: None}, summary="Desactivar un agente")
    def delete(self, request: Request, pk: int) -> Response:
        desactivar_agente(
            agente=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Clientes ----------


class ClientesView(ListAPIView):
    """GET y POST /api/v1/clientes/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN_CLIENTES}
    serializer_class = ClienteSerializer
    filterset_class = ClienteFilter

    def get_queryset(self):
        return _clientes_visibles(self)

    @extend_schema(
        request=ClienteEntradaSerializer,
        responses={201: ClienteSerializer},
        summary="Registrar un cliente",
    )
    def post(self, request: Request) -> Response:
        entrada = ClienteEntradaSerializer(
            data=request.data,
            context={"autor_es_agente": request.user.rol.nombre == NombreRol.AGENTE},
        )
        entrada.is_valid(raise_exception=True)
        cliente = crear_cliente(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ClienteSerializer(cliente).data, status=status.HTTP_201_CREATED)


class ClienteDetalleView(RetrieveAPIView):
    """
    GET, PATCH y DELETE /api/v1/clientes/{id}/

    get_object busca dentro de los clientes visibles: el cliente de otro
    agente no se encuentra y la respuesta es 404, no 403 (regla 14).
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": ESCRIBEN_CLIENTES, "DELETE": ESCRIBEN_CLIENTES}
    serializer_class = ClienteSerializer

    def get_queryset(self):
        return _clientes_visibles(self)

    @extend_schema(
        request=ClienteEntradaSerializer,
        responses={200: ClienteSerializer},
        summary="Editar los datos de un cliente (no su agente)",
    )
    def patch(self, request: Request, pk: int) -> Response:
        cliente = self.get_object()
        entrada = ClienteEntradaSerializer(
            instance=cliente, data=request.data, partial=True
        )
        entrada.is_valid(raise_exception=True)
        cliente = actualizar_cliente(
            cliente=cliente,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ClienteSerializer(cliente).data)

    @extend_schema(responses={204: None}, summary="Desactivar un cliente")
    def delete(self, request: Request, pk: int) -> Response:
        desactivar_cliente(
            cliente=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReasignarClienteView(GenericAPIView):
    """POST /api/v1/clientes/{id}/reasignar/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ADMINISTRAN}
    serializer_class = ReasignarClienteSerializer

    def get_queryset(self):
        return _clientes_visibles(self)

    @extend_schema(
        request=ReasignarClienteSerializer,
        responses={200: ClienteSerializer},
        summary="Pasar el cliente a otro agente",
    )
    def post(self, request: Request, pk: int) -> Response:
        cliente = self.get_object()
        entrada = ReasignarClienteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cliente = reasignar_cliente(
            cliente=cliente,
            agente=entrada.validated_data["agente"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ClienteSerializer(cliente).data)


# ---------- Cotizaciones (spec 007) ----------


def _cotizaciones_visibles(vista):
    """Igual que _clientes_visibles: cartera, y consulta vacía para el esquema."""
    if getattr(vista, "swagger_fake_view", False):
        return Cotizacion.objects.none()
    return listar_cotizaciones_visibles(usuario=vista.request.user)


class CotizacionesView(ListAPIView):
    """GET y POST /api/v1/cotizaciones/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN_CLIENTES}
    serializer_class = CotizacionSerializer
    filterset_class = CotizacionFilter

    def get_queryset(self):
        return _cotizaciones_visibles(self)

    @extend_schema(
        request=CotizacionCrearSerializer,
        responses={201: CotizacionSerializer},
        summary="Emitir una cotización en borrador",
    )
    def post(self, request: Request) -> Response:
        entrada = CotizacionCrearSerializer(
            data=request.data, context={"usuario": request.user}
        )
        entrada.is_valid(raise_exception=True)
        cotizacion = crear_cotizacion(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            CotizacionSerializer(cotizacion).data, status=status.HTTP_201_CREATED
        )


class CotizacionDetalleView(RetrieveAPIView):
    """GET y PATCH /api/v1/cotizaciones/{id}/ (PATCH solo en borrador)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": ESCRIBEN_CLIENTES}
    serializer_class = CotizacionSerializer

    def get_queryset(self):
        return _cotizaciones_visibles(self)

    @extend_schema(
        request=CotizacionEditarSerializer,
        responses={200: CotizacionSerializer},
        summary="Editar una cotización en borrador",
    )
    def patch(self, request: Request, pk: int) -> Response:
        cotizacion = self.get_object()
        entrada = CotizacionEditarSerializer(
            data=request.data, partial=True, context={"cotizacion": cotizacion}
        )
        entrada.is_valid(raise_exception=True)
        cotizacion = actualizar_cotizacion(
            cotizacion=cotizacion,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(CotizacionSerializer(cotizacion).data)


class AccionCotizacionView(GenericAPIView):
    """
    Base de /enviar/, /aprobar/ y /rechazar/: las tres reciben solo el id,
    buscan la cotización dentro de la cartera y llaman a su servicio. Cada
    subclase dice cuál con el método ejecutar.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN_CLIENTES}
    serializer_class = CotizacionSerializer

    def get_queryset(self):
        return _cotizaciones_visibles(self)

    def ejecutar(self, **kwargs) -> Cotizacion:
        raise NotImplementedError

    @extend_schema(request=None, responses={200: CotizacionSerializer})
    def post(self, request: Request, pk: int) -> Response:
        cotizacion = self.ejecutar(
            cotizacion=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(CotizacionSerializer(cotizacion).data)


class EnviarCotizacionView(AccionCotizacionView):
    """POST /api/v1/cotizaciones/{id}/enviar/"""

    def ejecutar(self, **kwargs) -> Cotizacion:
        return enviar_cotizacion(**kwargs)


class AprobarCotizacionView(AccionCotizacionView):
    """POST /api/v1/cotizaciones/{id}/aprobar/ (reserva el bien, regla 6)."""

    def ejecutar(self, **kwargs) -> Cotizacion:
        return aprobar_cotizacion(**kwargs)


class RechazarCotizacionView(AccionCotizacionView):
    """POST /api/v1/cotizaciones/{id}/rechazar/ (libera el bien si estaba aprobada)."""

    def ejecutar(self, **kwargs) -> Cotizacion:
        return rechazar_cotizacion(**kwargs)
