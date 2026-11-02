"""Selectores de construcción: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.core.models import Moneda, Pais
from apps.core.selectors import listar_monedas

from .enums import ESTADOS_ACTIVOS
from .models import Constructora, ProyectoConstruccion

if TYPE_CHECKING:
    # Solo para la anotación de tipos: construcción usa los selectores y
    # servicios de catalogo, nunca sus modelos (spec 017, §4).
    from apps.catalogo.models import Propiedad

# Moneda en que se guardan los presupuestos convertidos (spec 017, regla 11).
CODIGO_DOLAR = "USD"


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


def listar_proyectos() -> QuerySet[ProyectoConstruccion]:
    """
    Proyectos activos en el sentido de borrado lógico (activo=True), en
    cualquier estado: los finalizados y cancelados son historia de la propiedad.
    Con propiedad, constructora y moneda cargadas en la misma consulta.
    """
    return (
        ProyectoConstruccion.objects.filter(activo=True)
        .select_related("propiedad", "constructora", "moneda")
        .order_by("-fecha_inicio", "-id")
    )


def existe_proyecto_activo(*, propiedad: "Propiedad") -> bool:
    """Si la propiedad ya tiene un proyecto que puede avanzar (regla 10)."""
    return ProyectoConstruccion.objects.filter(
        propiedad=propiedad, estado__in=ESTADOS_ACTIVOS
    ).exists()


def constructora_tiene_proyectos_activos(*, constructora: Constructora) -> bool:
    """Si la constructora tiene obras sin cerrar: no se desactiva (regla 23)."""
    return ProyectoConstruccion.objects.filter(
        constructora=constructora, estado__in=ESTADOS_ACTIVOS
    ).exists()


def obtener_dolar() -> Moneda | None:
    """
    La moneda a la que se convierte cada presupuesto (regla 11).

    El mismo selector que tienen ventas y compras: las apps no dependen entre
    sí (spec 017, §4), así que no se importa de ninguna de ellas.
    """
    return listar_monedas().filter(codigo=CODIGO_DOLAR).first()
