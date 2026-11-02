"""Vistas de arrendamientos: reciben la petición, delegan en un servicio o
selector y devuelven la respuesta.

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

from .filters import ArrendamientoFilter
from .models import ContratoArrendamiento, PagoRenta
from .selectors import listar_arrendamientos_visibles, listar_pagos_renta_visibles
from .serializers import (
    ArrendamientoDetalleSerializer,
    ArrendamientoSerializer,
    FirmarArrendamientoSerializer,
    PagarRentaSerializer,
    PagoRentaSerializer,
    RenovarArrendamientoSerializer,
    RescindirArrendamientoSerializer,
    VincularDocumentoArrendamientoSerializer,
)
from .services import (
    finalizar_arrendamiento,
    firmar_arrendamiento,
    registrar_pago_renta,
    renovar_arrendamiento,
    rescindir_arrendamiento,
    vincular_documento,
)

# Spec 008, reglas 13 a 15.
FIRMAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE, NombreRol.AGENTE]
TERMINAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
REGISTRAN_PAGOS = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE, NombreRol.CONTABILIDAD]


def _contratos_visibles(vista):
    """Cartera de quien pide; consulta vacía al generar el esquema."""
    if getattr(vista, "swagger_fake_view", False):
        return ContratoArrendamiento.objects.none()
    return listar_arrendamientos_visibles(usuario=vista.request.user)


class ArrendamientosView(ListAPIView):
    """GET y POST /api/v1/contratos-arrendamiento/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": FIRMAN}
    serializer_class = ArrendamientoSerializer
    filterset_class = ArrendamientoFilter

    def get_queryset(self):
        return _contratos_visibles(self)

    @extend_schema(
        request=FirmarArrendamientoSerializer,
        responses={201: ArrendamientoDetalleSerializer},
        summary="Firmar un contrato de arrendamiento",
    )
    def post(self, request: Request) -> Response:
        entrada = FirmarArrendamientoSerializer(
            data=request.data, context={"usuario": request.user}
        )
        entrada.is_valid(raise_exception=True)
        contrato = firmar_arrendamiento(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ArrendamientoDetalleSerializer(contrato).data,
            status=status.HTTP_201_CREATED,
        )


class ArrendamientoDetalleView(RetrieveAPIView):
    """GET /api/v1/contratos-arrendamiento/{id}/ (con su calendario de pagos)."""

    permission_classes = [TieneRol]
    serializer_class = ArrendamientoDetalleSerializer

    def get_queryset(self):
        return _contratos_visibles(self)


class AccionArrendamientoView(GenericAPIView):
    """
    Base de /renovar/, /rescindir/ y /finalizar/: buscan el contrato dentro de
    la cartera y llaman a su servicio. Cada subclase declara sus roles, su
    entrada y qué servicio llama.
    """

    permission_classes = [TieneRol]
    serializer_class = ArrendamientoDetalleSerializer
    entrada = None

    def get_queryset(self):
        return _contratos_visibles(self)

    def ejecutar(self, contrato, datos: dict, autor, ip):
        raise NotImplementedError

    def post(self, request: Request, pk: int) -> Response:
        datos = {}
        if self.entrada is not None:
            entrada = self.entrada(data=request.data)
            entrada.is_valid(raise_exception=True)
            datos = entrada.validated_data
        resultado = self.ejecutar(
            self.get_object(), datos, request.user, obtener_ip_cliente(request)
        )
        return Response(ArrendamientoDetalleSerializer(resultado).data)


class RenovarArrendamientoView(AccionArrendamientoView):
    """POST /api/v1/contratos-arrendamiento/{id}/renovar/ (regla 9)."""

    roles_por_metodo = {"POST": FIRMAN}
    entrada = RenovarArrendamientoSerializer

    @extend_schema(
        request=RenovarArrendamientoSerializer,
        responses={200: ArrendamientoDetalleSerializer},
        summary="Renovar: crea el contrato siguiente",
    )
    def post(self, request: Request, pk: int) -> Response:
        return super().post(request, pk)

    def ejecutar(self, contrato, datos, autor, ip):
        return renovar_arrendamiento(contrato=contrato, autor=autor, ip=ip, **datos)


class RescindirArrendamientoView(AccionArrendamientoView):
    """POST /api/v1/contratos-arrendamiento/{id}/rescindir/ (regla 10)."""

    roles_por_metodo = {"POST": TERMINAN}
    entrada = RescindirArrendamientoSerializer

    @extend_schema(
        request=RescindirArrendamientoSerializer,
        responses={200: ArrendamientoDetalleSerializer},
        summary="Rescindir: el inquilino se va antes de terminar",
    )
    def post(self, request: Request, pk: int) -> Response:
        return super().post(request, pk)

    def ejecutar(self, contrato, datos, autor, ip):
        return rescindir_arrendamiento(contrato=contrato, autor=autor, ip=ip, **datos)


class FinalizarArrendamientoView(AccionArrendamientoView):
    """POST /api/v1/contratos-arrendamiento/{id}/finalizar/ (regla 11)."""

    roles_por_metodo = {"POST": TERMINAN}

    @extend_schema(
        request=None,
        responses={200: ArrendamientoDetalleSerializer},
        summary="Finalizar un contrato cuya fecha de fin ya pasó",
    )
    def post(self, request: Request, pk: int) -> Response:
        return super().post(request, pk)

    def ejecutar(self, contrato, datos, autor, ip):
        return finalizar_arrendamiento(contrato=contrato, autor=autor, ip=ip)


class DocumentoArrendamientoView(AccionArrendamientoView):
    """POST /api/v1/contratos-arrendamiento/{id}/documento/ (reglas 17 y 18)."""

    roles_por_metodo = {"POST": FIRMAN}
    entrada = VincularDocumentoArrendamientoSerializer

    @extend_schema(
        request=VincularDocumentoArrendamientoSerializer,
        responses={200: ArrendamientoDetalleSerializer},
        summary="Vincular o cambiar el documento de un contrato",
    )
    def post(self, request: Request, pk: int) -> Response:
        return super().post(request, pk)

    def ejecutar(self, contrato, datos, autor, ip):
        return vincular_documento(contrato=contrato, autor=autor, ip=ip, **datos)


class PagarRentaView(GenericAPIView):
    """POST /api/v1/pagos-renta/{id}/pagar/ (reglas 6 y 7)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": REGISTRAN_PAGOS}
    serializer_class = PagarRentaSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PagoRenta.objects.none()
        return listar_pagos_renta_visibles(usuario=self.request.user)

    @extend_schema(
        request=PagarRentaSerializer,
        responses={200: PagoRentaSerializer},
        summary="Registrar el pago de un mes de renta",
    )
    def post(self, request: Request, pk: int) -> Response:
        pago = self.get_object()
        entrada = PagarRentaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pago = registrar_pago_renta(
            pago=pago,
            autor=request.user,
            ip=obtener_ip_cliente(request),
            **entrada.validated_data,
        )
        return Response(PagoRentaSerializer(pago).data)
