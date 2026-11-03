"""Selectores de catálogo: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.

Las demás apps (ventas, arrendamientos, compras, construcción, ia) leen el
catálogo solo por estos selectores, nunca con los modelos directamente
(docs/arquitectura.md §3).
"""

from django.db.models import Max, Prefetch, QuerySet

from .models import (
    Avaluo,
    DocumentoOficial,
    ImagenPropiedad,
    Propiedad,
    TipoPropiedad,
    Unidad,
)


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


def listar_propiedades_con_portada() -> QuerySet[Propiedad]:
    """
    Las propiedades de la pantalla de catálogo, con su portada (spec 019, §6).

    El Prefetch trae las portadas de toda la página en una sola consulta más,
    no una por fila; quedan en propiedad.portadas, una lista de 0 o 1 imagen.
    Es un selector aparte y no parte de listar_propiedades porque las demás
    apps leen propiedades sin necesitar la foto, y el Prefetch les sumaría una
    consulta en cada lectura.
    """
    return listar_propiedades().prefetch_related(
        Prefetch(
            "imagenes",
            queryset=ImagenPropiedad.objects.filter(activo=True, es_portada=True),
            to_attr="portadas",
        )
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


def listar_imagenes(*, propiedad: Propiedad | None = None) -> QuerySet[ImagenPropiedad]:
    """
    Imágenes activas de propiedades activas, en el orden de la galería (spec
    019, regla 7): por orden y, a igual orden, por fecha de subida. Con
    propiedad, solo las de esa propiedad.
    """
    imagenes = (
        ImagenPropiedad.objects.filter(activo=True, propiedad__activo=True)
        .select_related("propiedad")
        .order_by("orden", "creado_en", "id")
    )
    if propiedad is not None:
        imagenes = imagenes.filter(propiedad=propiedad)
    return imagenes


def contar_imagenes_activas(*, propiedad: Propiedad) -> int:
    """Spec 019, regla 2: cuántas imágenes activas ocupan el límite de 10."""
    return listar_imagenes(propiedad=propiedad).count()


def siguiente_orden_imagen(*, propiedad: Propiedad) -> int:
    """Spec 019, regla 7: una imagen nueva va al final de la galería."""
    ultimo = listar_imagenes(propiedad=propiedad).aggregate(ultimo=Max("orden"))
    return (ultimo["ultimo"] or 0) + 1


def obtener_portada(*, propiedad: Propiedad) -> ImagenPropiedad | None:
    """La portada activa de la propiedad, o None si no tiene (regla 6)."""
    return listar_imagenes(propiedad=propiedad).filter(es_portada=True).first()


def primera_imagen_sin_portada(*, propiedad: Propiedad) -> ImagenPropiedad | None:
    """
    La que hereda la portada al desactivar la anterior (regla 6): la primera
    de la galería, según el orden.
    """
    return listar_imagenes(propiedad=propiedad).filter(es_portada=False).first()
