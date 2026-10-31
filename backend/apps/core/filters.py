"""
Filtros de los listados de core (django-filter).

Traducen los parámetros de la URL (?pais=3, ?fecha_desde=2026-01-01) a
condiciones sobre la consulta que entrega el selector. Son parte de la capa
HTTP, como los serializadores: validan la entrada y, si un valor no tiene el
formato correcto (una fecha inválida), la API responde 400 con el código
VALIDACION.
"""

import django_filters

from .models import Ciudad, TipoCambio

# Las fechas se aceptan solo en formato ISO (2026-10-05). Con el idioma en
# español, Django también aceptaría "05/10/2026" como día/mes/año; un cliente
# que mande mes/día recibiría otra fecha sin ningún aviso. En una API, un
# formato ambiguo debe rechazarse, no adivinarse.
FORMATO_FECHA_ISO = ["%Y-%m-%d"]


class CiudadFilter(django_filters.FilterSet):
    pais = django_filters.NumberFilter(field_name="pais_id")
    # Para buscar la ciudad mientras se escribe en un formulario (spec 010,
    # regla 11): una ciudad no cabe en un selector cuando hay cientos.
    buscar = django_filters.CharFilter(field_name="nombre", lookup_expr="icontains")

    class Meta:
        model = Ciudad
        fields = ["pais", "buscar"]


class TipoCambioFilter(django_filters.FilterSet):
    moneda_origen = django_filters.NumberFilter(field_name="moneda_origen_id")
    moneda_destino = django_filters.NumberFilter(field_name="moneda_destino_id")
    fecha = django_filters.DateFilter(
        field_name="fecha", input_formats=FORMATO_FECHA_ISO
    )
    # Rango inclusivo en ambos extremos.
    fecha_desde = django_filters.DateFilter(
        field_name="fecha", lookup_expr="gte", input_formats=FORMATO_FECHA_ISO
    )
    fecha_hasta = django_filters.DateFilter(
        field_name="fecha", lookup_expr="lte", input_formats=FORMATO_FECHA_ISO
    )

    class Meta:
        model = TipoCambio
        fields = ["moneda_origen", "moneda_destino", "fecha"]
