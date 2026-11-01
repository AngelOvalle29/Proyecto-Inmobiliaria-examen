"""Filtros del listado de proveedores (django-filter).

Traducen los parámetros de la URL (?tipo=BANCO, ?buscar=demo) a condiciones
sobre la consulta que entrega el selector. ?buscar= es un filtro más y no el
SearchFilter de DRF, igual que en crm (spec 004, §10).
"""

import django_filters
from django.db.models import Q

from apps.core.normalizacion import normalizar_documento

from .enums import TipoProveedor
from .models import Proveedor


class ProveedorFilter(django_filters.FilterSet):
    tipo = django_filters.ChoiceFilter(choices=TipoProveedor.choices)
    pais = django_filters.NumberFilter(field_name="pais_id")
    ciudad = django_filters.NumberFilter(field_name="ciudad_id")
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Proveedor
        fields = ["tipo", "pais", "ciudad"]

    def filtrar_por_texto(self, consulta, nombre, valor):
        """Código, nombre o NIT. El NIT se busca normalizado: "1234567-8"
        encuentra al proveedor guardado como "12345678"."""
        nit = normalizar_documento(valor)
        condicion = Q(codigo__icontains=valor) | Q(nombre__icontains=valor)
        if nit:
            condicion |= Q(nit__icontains=nit)
        return consulta.filter(condicion)
