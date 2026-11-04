"""
Filtros del listado de usuarios (django-filter, spec 013).

Un valor con formato inválido, como un rol que no existe, responde 400 con
el código VALIDACION.
"""

import django_filters
from django.db.models import Q, QuerySet

from .enums import NombreRol
from .models import Usuario
from .selectors import ESTADOS_LISTADO


class UsuarioFilter(django_filters.FilterSet):
    # ChoiceFilter y no CharFilter: un rol mal escrito ("AGENT") es un error de
    # quien llama y debe decirlo, no devolver una lista vacía.
    rol = django_filters.ChoiceFilter(
        field_name="rol__nombre", choices=NombreRol.choices
    )
    buscar = django_filters.CharFilter(method="filtrar_por_texto")
    # Spec 026: la pantalla de Usuarios ve también los desactivados. Sin el
    # parámetro, solo activos, como el listado de la spec 013.
    estado = django_filters.ChoiceFilter(
        choices=[(e, e.capitalize()) for e in ESTADOS_LISTADO],
        method="filtrar_por_estado",
    )

    class Meta:
        model = Usuario
        fields = ["rol"]

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            data.setdefault("estado", "ACTIVOS")
        super().__init__(data, *args, **kwargs)

    def filtrar_por_estado(
        self, queryset: QuerySet[Usuario], nombre: str, valor: str
    ) -> QuerySet[Usuario]:
        activo = ESTADOS_LISTADO[valor]
        return queryset if activo is None else queryset.filter(is_active=activo)

    def filtrar_por_texto(
        self, queryset: QuerySet[Usuario], nombre: str, valor: str
    ) -> QuerySet[Usuario]:
        """Nombre completo o correo que contengan el texto, sin distinguir
        mayúsculas."""
        return queryset.filter(
            Q(nombre_completo__icontains=valor) | Q(email__icontains=valor)
        )
