"""Filtros de los listados de construcción (django-filter).

?buscar= es un filtro más y no el SearchFilter de DRF, igual que en crm.
"""

import django_filters
from django.db.models import Q

from apps.core.normalizacion import normalizar_documento

from .enums import EstadoPago, EstadoProyecto, TipoPagoConstructora
from .models import Constructora, PagoConstructora, ProyectoConstruccion


class ConstructoraFilter(django_filters.FilterSet):
    pais = django_filters.NumberFilter(field_name="pais_id")
    # Las de calificación igual o mayor; las que no tienen calificación quedan fuera.
    calificacion_min = django_filters.NumberFilter(
        field_name="calificacion", lookup_expr="gte"
    )
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Constructora
        fields = ["pais"]

    def filtrar_por_texto(self, consulta, nombre, valor):
        """Código, nombre o NIT (el NIT, normalizado)."""
        nit = normalizar_documento(valor)
        condicion = Q(codigo__icontains=valor) | Q(nombre__icontains=valor)
        if nit:
            condicion |= Q(nit__icontains=nit)
        return consulta.filter(condicion)


class ProyectoFilter(django_filters.FilterSet):
    """Filtros de /proyectos-construccion/ (spec 017, §5)."""

    estado = django_filters.ChoiceFilter(choices=EstadoProyecto.choices)
    constructora = django_filters.NumberFilter(field_name="constructora_id")
    propiedad = django_filters.NumberFilter(field_name="propiedad_id")

    class Meta:
        model = ProyectoConstruccion
        fields = ["estado", "constructora", "propiedad"]


class PagoFilter(django_filters.FilterSet):
    """Filtros de /pagos-constructora/ (spec 017, §5)."""

    estado = django_filters.ChoiceFilter(choices=EstadoPago.choices)
    tipo = django_filters.ChoiceFilter(choices=TipoPagoConstructora.choices)
    proyecto = django_filters.NumberFilter(field_name="proyecto_id")

    class Meta:
        model = PagoConstructora
        fields = ["estado", "tipo", "proyecto"]
