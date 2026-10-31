"""Selectores de catálogo: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.

Las demás apps (ventas, arrendamientos, compras, construcción, ia) leen el
catálogo solo por estos selectores, nunca con los modelos directamente
(docs/arquitectura.md §3).
"""

from django.db.models import QuerySet

from .models import Avaluo, DocumentoOficial, Propiedad, TipoPropiedad, Unidad


def listar_tipos_propiedad() -> QuerySet[TipoPropiedad]:
    """Tipos de propiedad activos, por nombre."""
    return TipoPropiedad.objects.filter(activo=True).order_by("nombre")


def listar_propiedades() -> QuerySet[Propiedad]:
    """
    Propiedades activas, con su tipo, ciudad, país y moneda cargados en la misma
    consulta: sin select_related, un listado de 25 haría 100 consultas más.
    """
    return (
        Propiedad.objects.filter(activo=True)
        .select_related("tipo", "ciudad__pais", "moneda")
        .order_by("id")
    )


def obtener_propiedad(*, propiedad_id: int) -> Propiedad:
    """Una propiedad activa. Lanza Propiedad.DoesNotExist si no existe."""
    return listar_propiedades().get(pk=propiedad_id)


def listar_propiedades_publicas() -> QuerySet[Propiedad]:
    """
    Propiedades que el agente de IA puede mostrar en modo público (regla 5):
    activas y marcadas como públicas.
    """
    return listar_propiedades().filter(es_publica=True)


def listar_unidades(*, propiedad: Propiedad | None = None) -> QuerySet[Unidad]:
    """
    Unidades activas de propiedades activas, con su propiedad y moneda. Con
    propiedad, solo las de esa propiedad.
    """
    unidades = (
        Unidad.objects.filter(activo=True, propiedad__activo=True)
        .select_related("propiedad", "moneda")
        .order_by("propiedad_id", "codigo")
    )
    if propiedad is not None:
        unidades = unidades.filter(propiedad=propiedad)
    return unidades


def existe_unidad(
    *, propiedad: Propiedad, codigo: str, excluir_id: int | None = None
) -> bool:
    """
    Regla 3: si la propiedad ya tiene una unidad con ese código.

    Cuenta también las desactivadas, porque la restricción única de la base
    las incluye: reutilizar el código de una unidad dada de baja fallaría igual.
    """
    unidades = Unidad.objects.filter(propiedad=propiedad, codigo=codigo)
    if excluir_id is not None:
        unidades = unidades.exclude(pk=excluir_id)
    return unidades.exists()


def contar_unidades_activas(*, propiedad: Propiedad) -> int:
    """Regla 6: cuántas unidades activas impiden desactivar la propiedad."""
    return Unidad.objects.filter(propiedad=propiedad, activo=True).count()


def listar_avaluos(*, propiedad: Propiedad | None = None) -> QuerySet[Avaluo]:
    """
    Avalúos activos, del más reciente al más antiguo. Con propiedad, solo los
    de esa propiedad.
    """
    avaluos = (
        Avaluo.objects.filter(activo=True, propiedad__activo=True)
        .select_related("propiedad", "moneda", "documento")
        .order_by("-fecha", "-id")
    )
    if propiedad is not None:
        avaluos = avaluos.filter(propiedad=propiedad)
    return avaluos


def avaluo_activo_usa_documento(*, documento: DocumentoOficial) -> bool:
    """Regla 9: si el documento respalda al menos un avalúo activo."""
    return Avaluo.objects.filter(documento=documento, activo=True).exists()


def listar_documentos(
    *, propiedad: Propiedad | None = None
) -> QuerySet[DocumentoOficial]:
    """
    Documentos oficiales activos de propiedades activas. Con propiedad, solo
    los de esa propiedad.
    """
    documentos = (
        DocumentoOficial.objects.filter(activo=True, propiedad__activo=True)
        .select_related("propiedad")
        .order_by("-fecha_emision", "-id")
    )
    if propiedad is not None:
        documentos = documentos.filter(propiedad=propiedad)
    return documentos
