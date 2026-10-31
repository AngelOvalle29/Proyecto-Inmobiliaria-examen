"""
Filtros del listado de arrendamientos (django-filter).

Capa HTTP: qué contratos ve cada usuario (la cartera) ya lo decidió el
selector antes de llegar aquí.
"""

import django_filters

from .enums import EstadoArrendamiento
from .models import ContratoArrendamiento


class ArrendamientoFilter(django_filters.FilterSet):
    estado = django_filters.ChoiceFilter(choices=EstadoArrendamiento.choices)
    cliente = django_filters.NumberFilter(field_name="cliente_id")
    agente = django_filters.NumberFilter(field_name="agente_id")
    propiedad = django_filters.NumberFilter(field_name="propiedad_id")

    class Meta:
        model = ContratoArrendamiento
        fields = ["estado", "cliente", "agente", "propiedad"]
