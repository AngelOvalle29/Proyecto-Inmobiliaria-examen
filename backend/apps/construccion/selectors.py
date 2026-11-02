"""Selectores de construcción: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

from apps.core.models import Pais

from .models import Constructora


def listar_constructoras() -> QuerySet[Constructora]:
    """Constructoras activas, con su país cargado en la misma consulta."""
    return (
        Constructora.objects.filter(activo=True)
        .select_related("pais")
        .order_by("codigo")
    )


def existe_constructora_con_nit(
    *, pais: Pais, nit: str, excluir_id: int | None = None
) -> bool:
    """Si ya hay una constructora con ese NIT normalizado en el país.

    Incluye las desactivadas (regla 5). excluir_id deja fuera a la propia
    constructora cuando se edita.
    """
    consulta = Constructora.objects.filter(pais=pais, nit=nit)
    if excluir_id is not None:
        consulta = consulta.exclude(pk=excluir_id)
    return consulta.exists()
