"""Selectores de ventas: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

from apps.core.models import Moneda
from apps.core.selectors import listar_monedas
from apps.crm.selectors import listar_clientes_visibles
from apps.usuarios.models import Usuario

from .enums import EstadoCuota
from .models import ContratoVenta, CuotaPago

# Moneda en que se consolidan los reportes (spec 007, regla 14), la misma de
# referencia que usa seed_demo para los tipos de cambio.
CODIGO_DOLAR = "USD"


def listar_contratos_visibles(*, usuario: Usuario) -> QuerySet[ContratoVenta]:
    """
    Contratos de venta que el usuario puede ver (regla 22 de la spec 007).

    Como las cotizaciones, reutiliza la cartera de la spec 004: un agente ve
    los contratos de sus clientes y lo ajeno no se encuentra (404).
    """
    return (
        ContratoVenta.objects.filter(
            activo=True, cliente__in=listar_clientes_visibles(usuario=usuario)
        )
        .select_related(
            "cliente",
            "agente__usuario",
            "propiedad",
            "unidad__propiedad",
            "moneda",
            "cotizacion",
            "documento",
        )
        .prefetch_related("cuotas")
        .order_by("-fecha_firma", "-id")
    )


def listar_cuotas_visibles(*, usuario: Usuario) -> QuerySet[CuotaPago]:
    """Cuotas de los contratos visibles: para registrar un pago (regla 21)."""
    return CuotaPago.objects.filter(
        contrato__in=listar_contratos_visibles(usuario=usuario)
    ).select_related("contrato__moneda")


def contrato_tiene_pagos(*, contrato: ContratoVenta) -> bool:
    """Regla 15: algún pago, aunque sea parcial, en alguna de sus cuotas."""
    return contrato.cuotas.filter(monto_pagado__gt=0).exists()


def contrato_esta_pagado(*, contrato: ContratoVenta) -> bool:
    """Regla 18: todas sus cuotas están PAGADA."""
    return not contrato.cuotas.exclude(estado=EstadoCuota.PAGADA).exists()


def obtener_dolar() -> Moneda | None:
    """La moneda a la que se convierte cada contrato y pago (regla 14)."""
    return listar_monedas().filter(codigo=CODIGO_DOLAR).first()
