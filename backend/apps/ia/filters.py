"""
Filtros de la lista de documentos del agente (django-filter, spec 020, §5).

Un valor con formato inválido responde 400 con el código VALIDACION.
"""

import django_filters

from .enums import EstadoIndexacion, TipoDocumentoRAG
from .models import DocumentoRAG


class DocumentoRAGFilter(django_filters.FilterSet):
    tipo = django_filters.ChoiceFilter(choices=TipoDocumentoRAG.choices)
    estado_indexacion = django_filters.ChoiceFilter(choices=EstadoIndexacion.choices)
    buscar = django_filters.CharFilter(field_name="titulo", lookup_expr="icontains")

    class Meta:
        model = DocumentoRAG
        fields = ["tipo", "estado_indexacion", "buscar"]
