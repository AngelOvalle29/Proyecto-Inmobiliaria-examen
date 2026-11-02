"""Vistas de ventas: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos. Cada vista declara
qué roles pueden escribir (roles_por_metodo, spec 004 §6); qué contratos ve
cada usuario lo decide el selector (cartera).
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import ContratoVentaFilter
from .models import ContratoVenta, CuotaPago
from .selectors import listar_contratos_visibles, listar_cuotas_visibles
from .serializers import (
    ContratoVentaDetalleSerializer,
    ContratoVentaSerializer,
    CuotaSerializer,
    FirmarContratoSerializer,
    PagoCuotaSerializer,
    VincularDocumentoSerializer,
)
from .services import (
    anular_contrato,
    firmar_contrato,
    registrar_pago_cuota,
    vincular_documento,
)

# Spec 007, reglas 20 y 21.
FIRMAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE, NombreRol.AGENTE]
ANULAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
REGISTRAN_PAGOS = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE, NombreRol.CONTABILIDAD]


def _contratos_visibles(vista):
    """
    Contratos de la cartera de quien pide. Al generar el esquema de /api/docs/
    no hay usuario real (swagger_fake_view): basta una consulta vacía.
    """
    if getattr(vista, "swagger_fake_view", False):
        return ContratoVenta.objects.none()
    return listar_contratos_visibles(usuario=vista.request.user)


class ContratosVentaView(ListAPIView):
    """GET y POST /api/v1/contratos-venta/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": FIRMAN}
    serializer_class = ContratoVentaSerializer
    filterset_class = ContratoVentaFilter

    def get_queryset(self):
        return _contratos_visibles(self)

    @extend_schema(
        request=FirmarContratoSerializer,
        responses={201: ContratoVentaDetalleSerializer},
        summary="Firmar un contrato de venta, con o sin cotización",
    )
    def post(self, request: Request) -> Response:
        entrada = FirmarContratoSerializer(
            data=request.data, context={"usuario": request.user}
        )
        entrada.is_valid(raise_exception=True)
        contrato = firmar_contrato(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ContratoVentaDetalleSerializer(contrato).data,
            status=status.HTTP_201_CREATED,
        )


class ContratoVentaDetalleView(RetrieveAPIView):
    """GET /api/v1/contratos-venta/{id}/ (con sus cuotas y su mora)."""

    permission_classes = [TieneRol]
    serializer_class = ContratoVentaDetalleSerializer

    def get_queryset(self):
        return _contratos_visibles(self)


class AnularContratoView(GenericAPIView):
    """POST /api/v1/contratos-venta/{id}/anular/ (regla 15)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ANULAN}
    serializer_class = ContratoVentaDetalleSerializer

    def get_queryset(self):
        return _contratos_visibles(self)

    @extend_schema(request=None, responses={200: ContratoVentaDetalleSerializer})
    def post(self, request: Request, pk: int) -> Response:
        contrato = anular_contrato(
            contrato=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ContratoVentaDetalleSerializer(contrato).data)


class DocumentoContratoView(GenericAPIView):
    """POST /api/v1/contratos-venta/{id}/documento/ (reglas 23 y 24)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": FIRMAN}
    serializer_class = ContratoVentaDetalleSerializer

    def get_queryset(self):
        return _contratos_visibles(self)

    @extend_schema(
        request=VincularDocumentoSerializer,
        responses={200: ContratoVentaDetalleSerializer},
        summary="Vincular o cambiar el documento de un contrato",
    )
    def post(self, request: Request, pk: int) -> Response:
        contrato = self.get_object()
        entrada = VincularDocumentoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        contrato = vincular_documento(
            contrato=contrato,
            documento=entrada.validated_data["documento"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ContratoVentaDetalleSerializer(contrato).data)


class PagarCuotaView(GenericAPIView):
    """POST /api/v1/cuotas/{id}/pagos/ (reglas 16 a 18)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": REGISTRAN_PAGOS}
    serializer_class = PagoCuotaSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CuotaPago.objects.none()
        return listar_cuotas_visibles(usuario=self.request.user)

    @extend_schema(
        request=PagoCuotaSerializer,
        responses={200: CuotaSerializer},
        summary="Registrar un pago, total o parcial, de una cuota",
    )
    def post(self, request: Request, pk: int) -> Response:
        cuota = self.get_object()
        entrada = PagoCuotaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cuota = registrar_pago_cuota(
            cuota=cuota,
            monto=entrada.validated_data["monto"],
            fecha=entrada.validated_data["fecha"],
            referencia=entrada.validated_data["referencia"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(CuotaSerializer(cuota).data)
