"""Vistas de compras: reciben la petición, delegan en un servicio o selector y
devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos. Cada vista declara
qué roles pueden escribir (roles_por_metodo, spec 004 §6).
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import ProveedorFilter
from .selectors import listar_proveedores
from .serializers import ProveedorEntradaSerializer, ProveedorSerializer
from .services import actualizar_proveedor, crear_proveedor, desactivar_proveedor

# Regla 10: escriben administración y gerencia; todos los roles leen.
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
