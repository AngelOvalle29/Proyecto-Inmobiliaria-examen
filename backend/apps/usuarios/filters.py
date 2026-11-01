"""
Filtros del listado de usuarios (django-filter, spec 013).

Un valor con formato inválido, como un rol que no existe, responde 400 con
el código VALIDACION.
"""

import django_filters
from django.db.models import Q, QuerySet

from .enums import NombreRol
from .models import Usuario


class UsuarioFilter(django_filters.FilterSet):
    # ChoiceFilter y no CharFilter: un rol mal escrito ("AGENT") es un error de
    # quien llama y debe decirlo, no devolver una lista vacía.
    rol = django_filters.ChoiceFilter(
        field_name="rol__nombre", choices=NombreRol.choices
    )
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Usuario
        fields = ["rol"]

    def filtrar_por_texto(
        self, queryset: QuerySet[Usuario], nombre: str, valor: str
    ) -> QuerySet[Usuario]:
        """Nombre completo o correo que contengan el texto, sin distinguir
        mayúsculas."""
        return queryset.filter(
            Q(nombre_completo__icontains=valor) | Q(email__icontains=valor)
        )
