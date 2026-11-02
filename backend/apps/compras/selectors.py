"""Selectores de compras: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

from apps.core.models import Pais

from .models import Proveedor


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
