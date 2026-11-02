"""Vistas de compras: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos. Cada vista declara
qué roles pueden escribir (roles_por_metodo, spec 004 §6).
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import ContratoCompraFilter, ProveedorFilter
from .selectors import listar_contratos_compra, listar_proveedores
from .serializers import (
    ContratoCompraEntradaSerializer,
    ContratoCompraSerializer,
    MotivoSerializer,
    ProveedorEntradaSerializer,
    ProveedorSerializer,
)
from .services import (
    actualizar_proveedor,
    anular_contrato_compra,
    completar_contrato_compra,
    crear_contrato_compra,
    crear_proveedor,
    desactivar_proveedor,
)

# Escriben administración y gerencia; todos los roles leen (spec 006, regla
# 10, y spec 017, regla 24).
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]


class ProveedoresView(ListAPIView):
    """GET y POST /api/v1/proveedores/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN}
    serializer_class = ProveedorSerializer
    filterset_class = ProveedorFilter

    def get_queryset(self):
        return listar_proveedores()

    @extend_schema(
        request=ProveedorEntradaSerializer,
        responses={201: ProveedorSerializer},
        summary="Registrar un proveedor",
    )
    def post(self, request: Request) -> Response:
        entrada = ProveedorEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        proveedor = crear_proveedor(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ProveedorSerializer(proveedor).data, status=status.HTTP_201_CREATED
        )


class ProveedorDetalleView(RetrieveAPIView):
    """
    GET, PATCH y DELETE /api/v1/proveedores/{id}/

    get_object busca entre los proveedores activos: uno desactivado responde
    404, igual que uno que no existe.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": ESCRIBEN, "DELETE": ESCRIBEN}
    serializer_class = ProveedorSerializer

    def get_queryset(self):
        return listar_proveedores()

    @extend_schema(
        request=ProveedorEntradaSerializer,
        responses={200: ProveedorSerializer},
        summary="Editar los datos de un proveedor",
    )
    def patch(self, request: Request, pk: int) -> Response:
        proveedor = self.get_object()
        entrada = ProveedorEntradaSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        actualizar_proveedor(
            proveedor=proveedor,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProveedorSerializer(proveedor).data)

    @extend_schema(responses={204: None}, summary="Desactivar un proveedor")
    def delete(self, request: Request, pk: int) -> Response:
        desactivar_proveedor(
            proveedor=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Contratos de compra (spec 017) ----------


class ContratosCompraView(ListAPIView):
    """GET y POST /api/v1/contratos-compra/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN}
    serializer_class = ContratoCompraSerializer
    filterset_class = ContratoCompraFilter

    def get_queryset(self):
        return listar_contratos_compra()

    @extend_schema(
        request=ContratoCompraEntradaSerializer,
        responses={201: ContratoCompraSerializer},
        summary="Registrar un contrato de compra",
    )
    def post(self, request: Request) -> Response:
        entrada = ContratoCompraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        contrato = crear_contrato_compra(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ContratoCompraSerializer(contrato).data, status=status.HTTP_201_CREATED
        )


class ContratoCompraDetalleView(RetrieveAPIView):
    """GET /api/v1/contratos-compra/{id}/ (sin edición, spec 017 §10)."""

    permission_classes = [TieneRol]
    serializer_class = ContratoCompraSerializer

    def get_queryset(self):
        return listar_contratos_compra()


class CompletarContratoCompraView(GenericAPIView):
    """POST /api/v1/contratos-compra/{id}/completar/ (regla 6)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN}
    serializer_class = ContratoCompraSerializer

    def get_queryset(self):
        return listar_contratos_compra()

    @extend_schema(
        request=None,
        responses={200: ContratoCompraSerializer},
        summary="Completar una compra: la propiedad pasa a ADQUIRIDA",
    )
    def post(self, request: Request, pk: int) -> Response:
        contrato = completar_contrato_compra(
            contrato=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ContratoCompraSerializer(contrato).data)


class AnularContratoCompraView(GenericAPIView):
    """POST /api/v1/contratos-compra/{id}/anular/ (regla 7)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN}
    serializer_class = ContratoCompraSerializer

    def get_queryset(self):
        return listar_contratos_compra()

    @extend_schema(
        request=MotivoSerializer,
        responses={200: ContratoCompraSerializer},
        summary="Anular un contrato de compra en proceso",
    )
    def post(self, request: Request, pk: int) -> Response:
        contrato = self.get_object()
        entrada = MotivoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        contrato = anular_contrato_compra(
            contrato=contrato,
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ContratoCompraSerializer(contrato).data)
