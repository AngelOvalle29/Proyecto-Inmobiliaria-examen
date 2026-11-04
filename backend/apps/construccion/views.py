"""Vistas de construcción: reciben la petición, delegan en un servicio o
selector y devuelven la respuesta.

Sin reglas de negocio ni consultas directas a los modelos. Cada vista declara
qué roles pueden escribir (roles_por_metodo, spec 004 §6).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.http import obtener_ip_cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.permissions import TieneRol

from .filters import ConstructoraFilter, PagoFilter, ProyectoFilter
from .selectors import (
    listar_constructoras,
    listar_pagos,
    listar_proyectos,
    listar_proyectos_con_totales,
)
from .serializers import (
    AvanceSerializer,
    ConstructoraEntradaSerializer,
    ConstructoraSerializer,
    MotivoConstruccionSerializer,
    PagarSerializer,
    PagoSerializer,
    ProgramarPagoSerializer,
    ProyectoDetalleSerializer,
    ProyectoEdicionSerializer,
    ProyectoEntradaSerializer,
    ProyectoSerializer,
)
from .services import (
    actualizar_constructora,
    actualizar_proyecto,
    anular_pago,
    cancelar_proyecto,
    crear_constructora,
    crear_proyecto,
    desactivar_constructora,
    finalizar_proyecto,
    iniciar_proyecto,
    pagar,
    programar_pago,
    reanudar_proyecto,
    registrar_avance,
    suspender_proyecto,
)

# Escriben administración y gerencia (spec 006, regla 10, y spec 017, regla
# 24). Leen además contabilidad, y nadie más: un agente no debe ver lo que
# pagó la agencia ni el presupuesto de las obras (spec 024, regla 1).
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
LEEN = [*ESCRIBEN, NombreRol.CONTABILIDAD]
# Los pagos los registra también contabilidad, como los de ventas (regla 24).
PAGAN = [*ESCRIBEN, NombreRol.CONTABILIDAD]


class ConstructorasView(ListAPIView):
    """GET y POST /api/v1/constructoras/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "POST": ESCRIBEN}
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
    roles_por_metodo = {"GET": LEEN, "PATCH": ESCRIBEN, "DELETE": ESCRIBEN}
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


# ---------- Proyectos de construcción (spec 017) ----------


class ProyectosView(ListAPIView):
    """GET y POST /api/v1/proyectos-construccion/"""

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "POST": ESCRIBEN}
    serializer_class = ProyectoSerializer
    filterset_class = ProyectoFilter

    def get_queryset(self):
        return listar_proyectos()

    @extend_schema(
        request=ProyectoEntradaSerializer,
        responses={201: ProyectoSerializer},
        summary="Registrar un proyecto de construcción",
    )
    def post(self, request: Request) -> Response:
        entrada = ProyectoEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        proyecto = crear_proyecto(
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(
            ProyectoSerializer(proyecto).data, status=status.HTTP_201_CREATED
        )


class ProyectoDetalleView(RetrieveAPIView):
    """
    GET y PATCH /api/v1/proyectos-construccion/{id}/ (regla 17).

    El detalle trae total_comprometido y disponible (§5). Después de editar se
    vuelve a leer con el selector, para responder los totales al día.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "PATCH": ESCRIBEN}
    serializer_class = ProyectoDetalleSerializer

    def get_queryset(self):
        return listar_proyectos_con_totales()

    @extend_schema(
        request=ProyectoEdicionSerializer,
        responses={200: ProyectoDetalleSerializer},
        summary="Editar el nombre, la fecha de fin estimada o el presupuesto",
    )
    def patch(self, request: Request, pk: int) -> Response:
        proyecto = self.get_object()
        entrada = ProyectoEdicionSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        actualizar_proyecto(
            proyecto=proyecto,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoDetalleSerializer(self.get_object()).data)


class AccionProyectoView(GenericAPIView):
    """
    Base de las acciones del ciclo del proyecto (POST .../{id}/<acción>/).

    Solo fija lo que comparten: quién escribe, dónde se busca el proyecto y qué
    responde. Cada subclase llama a su servicio en post(), así cada acción se
    lee de corrido en su propia clase.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "POST": ESCRIBEN}
    serializer_class = ProyectoSerializer

    def get_queryset(self):
        return listar_proyectos()


class IniciarProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/iniciar/ (regla 12)."""

    @extend_schema(request=None, responses={200: ProyectoSerializer})
    def post(self, request: Request, pk: int) -> Response:
        proyecto = iniciar_proyecto(
            proyecto=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


class AvanceProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/avance/ (regla 13)."""

    @extend_schema(request=AvanceSerializer, responses={200: ProyectoSerializer})
    def post(self, request: Request, pk: int) -> Response:
        proyecto = self.get_object()
        entrada = AvanceSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        proyecto = registrar_avance(
            proyecto=proyecto,
            porcentaje=entrada.validated_data["porcentaje"],
            descripcion=entrada.validated_data["descripcion"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


class SuspenderProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/suspender/ (regla 14)."""

    @extend_schema(
        request=MotivoConstruccionSerializer, responses={200: ProyectoSerializer}
    )
    def post(self, request: Request, pk: int) -> Response:
        proyecto = self.get_object()
        entrada = MotivoConstruccionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        proyecto = suspender_proyecto(
            proyecto=proyecto,
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


class ReanudarProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/reanudar/ (regla 14)."""

    @extend_schema(request=None, responses={200: ProyectoSerializer})
    def post(self, request: Request, pk: int) -> Response:
        proyecto = reanudar_proyecto(
            proyecto=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


class FinalizarProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/finalizar/ (regla 15)."""

    @extend_schema(request=None, responses={200: ProyectoSerializer})
    def post(self, request: Request, pk: int) -> Response:
        proyecto = finalizar_proyecto(
            proyecto=self.get_object(),
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


class CancelarProyectoView(AccionProyectoView):
    """POST /api/v1/proyectos-construccion/{id}/cancelar/ (regla 16)."""

    @extend_schema(
        request=MotivoConstruccionSerializer, responses={200: ProyectoSerializer}
    )
    def post(self, request: Request, pk: int) -> Response:
        proyecto = self.get_object()
        entrada = MotivoConstruccionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        proyecto = cancelar_proyecto(
            proyecto=proyecto,
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(ProyectoSerializer(proyecto).data)


# ---------- Pagos a constructoras (spec 017) ----------


class PagosProyectoView(ListAPIView):
    """
    GET y POST /api/v1/proyectos-construccion/{id}/pagos/

    Los pagos de un proyecto, para la tabla de su detalle, y programar uno
    nuevo (reglas 19 y 20). El proyecto se busca entre los visibles: uno que
    no existe responde 404.
    """

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "POST": PAGAN}
    serializer_class = PagoSerializer

    def _proyecto(self):
        return get_object_or_404(listar_proyectos(), pk=self.kwargs["pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return listar_pagos().none()
        return listar_pagos(proyecto=self._proyecto())

    @extend_schema(
        request=ProgramarPagoSerializer,
        responses={201: PagoSerializer},
        summary="Programar un pago a la constructora del proyecto",
    )
    def post(self, request: Request, pk: int) -> Response:
        proyecto = self._proyecto()
        entrada = ProgramarPagoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pago = programar_pago(
            proyecto=proyecto,
            datos=entrada.validated_data,
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(PagoSerializer(pago).data, status=status.HTTP_201_CREATED)


class PagosConstructoraView(ListAPIView):
    """GET /api/v1/pagos-constructora/ (todos los pagos, con filtros)."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN}
    serializer_class = PagoSerializer
    filterset_class = PagoFilter

    def get_queryset(self):
        return listar_pagos()


class AccionPagoView(GenericAPIView):
    """Base de /pagar/ y /anular/: quién paga y dónde se busca el pago."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"GET": LEEN, "POST": PAGAN}
    serializer_class = PagoSerializer

    def get_queryset(self):
        return listar_pagos()


class PagarPagoView(AccionPagoView):
    """POST /api/v1/pagos-constructora/{id}/pagar/ (regla 21)."""

    @extend_schema(request=PagarSerializer, responses={200: PagoSerializer})
    def post(self, request: Request, pk: int) -> Response:
        pago = self.get_object()
        entrada = PagarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pago = pagar(
            pago=pago,
            fecha_pago=entrada.validated_data["fecha_pago"],
            referencia=entrada.validated_data["referencia_pago"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(PagoSerializer(pago).data)


class AnularPagoView(AccionPagoView):
    """POST /api/v1/pagos-constructora/{id}/anular/ (regla 21)."""

    @extend_schema(
        request=MotivoConstruccionSerializer, responses={200: PagoSerializer}
    )
    def post(self, request: Request, pk: int) -> Response:
        pago = self.get_object()
        entrada = MotivoConstruccionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pago = anular_pago(
            pago=pago,
            motivo=entrada.validated_data["motivo"],
            autor=request.user,
            ip=obtener_ip_cliente(request),
        )
        return Response(PagoSerializer(pago).data)
