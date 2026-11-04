"""Arma el texto del catálogo público del asistente (spec 025).

Es una función pura: recibe propiedades y unidades ya leídas y devuelve
Markdown. No consulta la base ni llama a la IA, así se puede probar y leer
sola. El servicio sincronizar_catalogo_publico decide cuándo usarla.

El texto depende solo de los datos (regla 4): no lleva la fecha de
generación. Si la llevara, cambiaría en cada pregunta y el catálogo se
reindexaría siempre.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.catalogo.enums import EstadoPropiedad

if TYPE_CHECKING:
    # Solo para las anotaciones: los datos llegan por los selectores del
    # catálogo (docs/arquitectura.md §3).
    from apps.catalogo.models import Propiedad, Unidad

TITULO_CATALOGO = "Catálogo público de propiedades"

INTRODUCCION = """\
## Acerca de este catálogo

Este catálogo reúne las propiedades que la agencia ofrece al público, con su
ubicación, sus características, su precio de lista y su estado actual. El
sistema lo genera a partir de su inventario y lo actualiza solo cuando una
propiedad o unidad cambia de estado.

Los precios de lista están en la moneda del país de la propiedad y no incluyen
impuestos ni gastos de escrituración. Para reservar, cotizar o financiar una
compra se aplican la política comercial y el manual de procesos de venta de la
agencia.
"""


def _monto(valor: Decimal, moneda: str) -> str:
    return f"{moneda} {valor:,.2f}"


def _area(valor: Decimal) -> str:
    """80.00 → '80'; 85.50 → '85.5'. Sin ceros que no aportan."""
    texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
    return f"{texto} m²"


def _cantidad(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def _estado(estado: str) -> str:
    return EstadoPropiedad(estado).label.lower()


def _ficha(propiedad: Propiedad, unidades: list[Unidad]) -> str:
    ciudad = propiedad.ciudad
    lineas = [
        f"## {propiedad.nombre}, {ciudad.nombre}, {ciudad.pais.nombre}",
        "",
        f"Tipo: {propiedad.tipo.nombre}. Dirección: {propiedad.direccion}, "
        f"{ciudad.nombre}, {ciudad.pais.nombre}. Código: {propiedad.codigo}.",
    ]
    if propiedad.descripcion:
        lineas.append(propiedad.descripcion.strip())
    areas = f"El terreno mide {_area(propiedad.area_m2)}"
    if propiedad.area_construida_m2:
        areas += f" y el área construida es de {_area(propiedad.area_construida_m2)}"
    lineas.append(areas + ".")
    lineas.append("")

    if not unidades:
        # Se vende o arrienda entera: su estado es el de la propiedad.
        precio = _monto(propiedad.precio_lista, propiedad.moneda.codigo)
        lineas.append(f"Precio de lista: {precio}.")
        if propiedad.estado == EstadoPropiedad.DISPONIBLE:
            lineas.append("Está disponible.")
        else:
            lineas.append(
                f"No está disponible: su estado actual es {_estado(propiedad.estado)}."
            )
        return "\n".join(lineas)

    # Un edificio se vende por unidad (spec 003): cada una con su estado.
    lineas.append("Se ofrece por unidad:")
    lineas.append("")
    for unidad in unidades:
        detalle = [f"nivel {unidad.nivel}", _area(unidad.area_m2)]
        if unidad.habitaciones:
            detalle.append(_cantidad(unidad.habitaciones, "habitación", "habitaciones"))
        if unidad.banos:
            detalle.append(_cantidad(unidad.banos, "baño", "baños"))
        precio = _monto(unidad.precio_lista, unidad.moneda.codigo)
        lineas.append(
            f"- {unidad.codigo}: {', '.join(detalle)}. {precio}. "
            f"Estado: {_estado(unidad.estado)}."
        )
    disponibles = [u.codigo for u in unidades if u.estado == EstadoPropiedad.DISPONIBLE]
    lineas.append("")
    if disponibles:
        lineas.append(f"Unidades disponibles ahora: {', '.join(disponibles)}.")
    else:
        lineas.append("Por ahora no hay unidades disponibles en esta propiedad.")
    return "\n".join(lineas)


def armar_catalogo(propiedades: Iterable[Propiedad], unidades: Iterable[Unidad]) -> str:
    """El Markdown del catálogo: una sección por propiedad (spec 025, §6).

    Cada propiedad es una sección "##": el troceo la convierte en su propio
    fragmento, y la cita del asistente apunta a esa ficha.
    """
    por_propiedad: dict[int, list[Unidad]] = {}
    for unidad in unidades:
        por_propiedad.setdefault(unidad.propiedad_id, []).append(unidad)

    secciones = [f"# {TITULO_CATALOGO}", "", INTRODUCCION]
    for propiedad in propiedades:
        secciones.append(_ficha(propiedad, por_propiedad.get(propiedad.pk, [])))
        secciones.append("")
    return "\n".join(secciones).rstrip() + "\n"
