"""Selectores de compras: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.core.models import Moneda, Pais
from apps.core.selectors import listar_monedas

from .enums import EstadoContratoCompra
from .models import ContratoCompra, Proveedor

if TYPE_CHECKING:
    # Solo para la anotación de tipos: compras usa los selectores y servicios
    # de catalogo, nunca sus modelos (spec 017, §4).
    from apps.catalogo.models import Propiedad

# Moneda en que se guardan los costos convertidos (spec 017, regla 5), la misma
# que usa ventas (spec 007, regla 14).
CODIGO_DOLAR = "USD"


def listar_proveedores() -> QuerySet[Proveedor]:
    """Proveedores activos, con su país y ciudad cargados en la misma consulta."""
    return (
        Proveedor.objects.filter(activo=True)
        .select_related("pais", "ciudad")
        .order_by("codigo")
    )


def existe_proveedor_con_nit(
    *, pais: Pais, nit: str, excluir_id: int | None = None
) -> bool:
    """Si ya hay un proveedor con ese NIT normalizado en el país.

    Incluye los desactivados (regla 3). excluir_id deja fuera al propio
    proveedor cuando se edita.
    """
    consulta = Proveedor.objects.filter(pais=pais, nit=nit)
    if excluir_id is not None:
        consulta = consulta.exclude(pk=excluir_id)
    return consulta.exists()


def listar_contratos_compra() -> QuerySet[ContratoCompra]:
    """
    Contratos de compra activos, con proveedor, propiedad y moneda cargados en
    la misma consulta. Los anulados se listan: siguen siendo historia de la
    propiedad (spec 017, regla 7).
    """
    return (
        ContratoCompra.objects.filter(activo=True)
        .select_related("proveedor", "propiedad", "moneda")
        .order_by("-fecha_compra", "-id")
    )


def existe_contrato_no_anulado(*, propiedad: "Propiedad") -> bool:
    """Si la propiedad ya tiene un contrato EN_PROCESO o COMPLETADO (regla 2)."""
    return (
        ContratoCompra.objects.filter(propiedad=propiedad)
        .exclude(estado=EstadoContratoCompra.ANULADO)
        .exists()
    )


def proveedor_tiene_contratos_en_proceso(*, proveedor: Proveedor) -> bool:
    """Si el proveedor tiene contratos sin cerrar: no se desactiva (regla 22)."""
    return ContratoCompra.objects.filter(
        proveedor=proveedor, estado=EstadoContratoCompra.EN_PROCESO
    ).exists()


def obtener_dolar() -> Moneda | None:
    """
    La moneda a la que se convierte cada costo (regla 5).

    Es el mismo selector que tiene ventas: compras no depende de ventas
    (spec 017, §4), así que no lo importa de allí.
    """
    return listar_monedas().filter(codigo=CODIGO_DOLAR).first()
