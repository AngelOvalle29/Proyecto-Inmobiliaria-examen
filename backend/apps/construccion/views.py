"""Vistas de construcción: reciben la petición, delegan en un servicio o
selector y devuelven la respuesta.

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

from .filters import ConstructoraFilter
from .selectors import listar_constructoras
from .serializers import ConstructoraEntradaSerializer, ConstructoraSerializer
from .services import (
    actualizar_constructora,
    crear_constructora,
    desactivar_constructora,
)

# Regla 10: escriben administración y gerencia; todos los roles leen.
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]


class ConstructorasView(ListAPIView):
    """GET y POST /api/v1/constructoras/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": ESCRIBEN}
    serializer_class = ConstructoraSerializer
    filterset_class = ConstructoraFilter

    def get_queryset(self):
        return listar_constructoras()

    @extend_schema(
        request=ConstructoraEntradaSerializer,
        responses={201: ConstructoraSerializer},
        summary="Registrar una constructora",
    )
    def post(self, request: Request) -> Response:
        entrada = ConstructoraEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        constructora = crear_constructora(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ConstructoraSerializer(constructora).data, status=status.HTTP_201_CREATED
        )


class ConstructoraDetalleView(RetrieveAPIView):
    """
    GET, PATCH y DELETE /api/v1/constructoras/{id}/

    get_object busca entre las constructoras activas: una desactivada responde
    404, igual que una que no existe.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"PATCH": ESCRIBEN, "DELETE": ESCRIBEN}
    serializer_class = ConstructoraSerializer

    def get_queryset(self):
        return listar_constructoras()

    @extend_schema(
        request=ConstructoraEntradaSerializer,
        responses={200: ConstructoraSerializer},
        summary="Editar los datos de una constructora",
    )
    def patch(self, request: Request, pk: int) -> Response:
        constructora = self.get_object()
        entrada = ConstructoraEntradaSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        actualizar_constructora(
            constructora=constructora,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ConstructoraSerializer(constructora).data)

    @extend_schema(responses={204: None}, summary="Desactivar una constructora")
    def delete(self, request: Request, pk: int) -> Response:
        desactivar_constructora(
            constructora=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
