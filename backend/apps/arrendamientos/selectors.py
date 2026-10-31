"""Selectores de arrendamientos: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

from apps.core.models import Moneda
from apps.core.selectors import listar_monedas
from apps.crm.selectors import listar_clientes_visibles
from apps.usuarios.models import Usuario

from .models import ContratoArrendamiento, PagoRenta


def listar_arrendamientos_visibles(
    *, usuario: Usuario
) -> QuerySet[ContratoArrendamiento]:
    """
    Contratos de arrendamiento que el usuario puede ver (regla 16 de la spec
    008). Reutiliza la cartera de la spec 004, como ventas: un agente ve los
    de sus clientes y lo ajeno no se encuentra (404).
    """
    return (
        ContratoArrendamiento.objects.filter(
            activo=True, cliente__in=listar_clientes_visibles(usuario=usuario)
        )
        .select_related(
            "cliente",
            "agente__usuario",
            "propiedad",
            "unidad__propiedad",
            "moneda",
            "contrato_anterior",
        )
        .prefetch_related("pagos")
        .order_by("-fecha_inicio", "-id")
    )


def listar_pagos_renta_visibles(*, usuario: Usuario) -> QuerySet[PagoRenta]:
    """Pagos de los contratos visibles: para registrar uno (regla 15)."""
    return PagoRenta.objects.filter(
        contrato__in=listar_arrendamientos_visibles(usuario=usuario)
    ).select_related("contrato__moneda")


def obtener_dolar() -> Moneda | None:
    """
    La moneda a la que se convierte cada contrato y pago (regla 5). Es la misma
    función que en ventas, repetida a propósito: importarla de ventas haría
    depender a arrendamientos de ventas, y la spec 008 no lo prevé.
    """
    return listar_monedas().filter(codigo="USD").first()
