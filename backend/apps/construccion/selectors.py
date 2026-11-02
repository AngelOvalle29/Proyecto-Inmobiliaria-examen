"""Selectores de construcción: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import DecimalField, F, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.models import Moneda, Pais
from apps.core.selectors import listar_monedas

from .enums import ESTADOS_ACTIVOS, ESTADOS_COMPROMETIDOS
from .models import Constructora, PagoConstructora, ProyectoConstruccion

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


def listar_proyectos_con_totales() -> QuerySet[ProyectoConstruccion]:
    """
    Los proyectos de listar_proyectos() con total_comprometido y disponible
    calculados en la misma consulta, para el detalle (spec 017, §5).

    Usa la misma regla que valida el presupuesto (regla 19): cuentan los pagos
    programados y pagados, no los anulados. Así la pantalla y la validación
    nunca dan números distintos. Coalesce deja 0 en un proyecto sin pagos, en
    vez de NULL.
    """
    comprometido = Coalesce(
        Sum("pagos__monto", filter=Q(pagos__estado__in=ESTADOS_COMPROMETIDOS)),
        Value(Decimal("0")),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    return listar_proyectos().annotate(
        total_comprometido=comprometido,
        disponible=F("presupuesto_total") - comprometido,
    )


def total_comprometido(*, proyecto: ProyectoConstruccion) -> Decimal:
    """
    Suma de los pagos programados y pagados del proyecto (regla 19). La usan
    programar_pago, actualizar_proyecto y el detalle del proyecto.
    """
    resultado = PagoConstructora.objects.filter(
        proyecto=proyecto, estado__in=ESTADOS_COMPROMETIDOS
    ).aggregate(total=Sum("monto"))
    return resultado["total"] or Decimal("0")


def listar_pagos(
    *, proyecto: ProyectoConstruccion | None = None
) -> QuerySet[PagoConstructora]:
    """
    Pagos activos de proyectos activos, con su proyecto, la constructora del
    proyecto y la moneda cargados en la misma consulta. Con proyecto, solo los
    de ese proyecto (la tabla de pagos de su detalle).
    """
    pagos = (
        PagoConstructora.objects.filter(activo=True, proyecto__activo=True)
        .select_related("proyecto__constructora", "moneda", "documento")
        .order_by("fecha_programada", "id")
    )
    if proyecto is not None:
        pagos = pagos.filter(proyecto=proyecto)
    return pagos


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
