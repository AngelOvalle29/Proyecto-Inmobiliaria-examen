"""
Filtros del listado de propiedades (django-filter).

Traducen los parámetros de la URL (?tipo=2&precio_max=150000) a condiciones
sobre la consulta que entrega el selector. Un valor con formato inválido
responde 400 con el código VALIDACION.
"""

import django_filters
from django.db.models import Q, QuerySet

from .enums import EstadoPropiedad, TipoDocumento
from .models import DocumentoOficial, Propiedad, Unidad


class PropiedadFilter(django_filters.FilterSet):
    tipo = django_filters.NumberFilter(field_name="tipo_id")
    ciudad = django_filters.NumberFilter(field_name="ciudad_id")
    # El país es el de la ciudad (regla 1).
    pais = django_filters.NumberFilter(field_name="ciudad__pais_id")
    estado = django_filters.ChoiceFilter(choices=EstadoPropiedad.choices)
    moneda = django_filters.NumberFilter(field_name="moneda_id")
    # Rango inclusivo. Compara el número tal cual, sin convertir de moneda:
    # para comparar precios en distintas monedas se filtra también ?moneda=.
    precio_min = django_filters.NumberFilter(
        field_name="precio_lista", lookup_expr="gte"
    )
    precio_max = django_filters.NumberFilter(
        field_name="precio_lista", lookup_expr="lte"
    )
    es_publica = django_filters.BooleanFilter()
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Propiedad
        fields = ["tipo", "ciudad", "pais", "estado", "moneda", "es_publica"]

    def filtrar_por_texto(
        self, queryset: QuerySet[Propiedad], nombre: str, valor: str
    ) -> QuerySet[Propiedad]:
        """Código, nombre o dirección que contengan el texto, sin distinguir
        mayúsculas."""
        return queryset.filter(
            Q(codigo__icontains=valor)
            | Q(nombre__icontains=valor)
            | Q(direccion__icontains=valor)
        )


class DocumentoFilter(django_filters.FilterSet):
    tipo = django_filters.ChoiceFilter(choices=TipoDocumento.choices)
    # "Vence antes de": estricto, y deja fuera los documentos sin vencimiento.
    vence_antes = django_filters.DateFilter(
        field_name="fecha_vencimiento", lookup_expr="lt"
    )

    class Meta:
        model = DocumentoOficial
        fields = ["tipo"]


class UnidadFilter(django_filters.FilterSet):
    # Spec 014, regla 11: para buscar una unidad mientras se escribe (cotizar,
    # vender o arrendar un apartamento) sin quedarse en la primera página.
    buscar = django_filters.CharFilter(field_name="codigo", lookup_expr="icontains")

    class Meta:
        model = Unidad
        fields = ["buscar"]
