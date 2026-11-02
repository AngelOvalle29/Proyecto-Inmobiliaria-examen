"""
Filtros del listado de contratos de venta (django-filter).

Capa HTTP: qué contratos ve cada usuario (la cartera) ya lo decidió el
selector antes de llegar aquí.
"""

import django_filters

from .enums import EstadoContrato, ModalidadVenta
from .models import ContratoVenta


class ContratoVentaFilter(django_filters.FilterSet):
    estado = django_filters.ChoiceFilter(choices=EstadoContrato.choices)
    modalidad = django_filters.ChoiceFilter(choices=ModalidadVenta.choices)
    cliente = django_filters.NumberFilter(field_name="cliente_id")
    agente = django_filters.NumberFilter(field_name="agente_id")

    class Meta:
        model = ContratoVenta
        fields = ["estado", "modalidad", "cliente", "agente"]
