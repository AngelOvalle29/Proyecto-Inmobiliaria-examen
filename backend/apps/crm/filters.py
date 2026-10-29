"""
Filtros de los listados de CRM (django-filter).

Traducen los parámetros de la URL (?pais=3, ?buscar=demo) a condiciones sobre
la consulta que entrega el selector. Son capa HTTP: qué registros puede ver
cada usuario (la cartera) ya lo decidió el selector antes de llegar aquí.

?buscar= es un filtro más y no el SearchFilter de DRF, para no cambiar la
configuración global de core (spec 004, §10).
"""

import django_filters
from django.db.models import Q

from .enums import TipoCliente
from .models import Agente, Cliente


class AgenteFilter(django_filters.FilterSet):
    pais = django_filters.NumberFilter(field_name="usuario__pais_id")
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Agente
        fields = ["pais"]

    def filtrar_por_texto(self, consulta, nombre, valor):
        """Nombre, correo o código, sin distinguir mayúsculas."""
        return consulta.filter(
            Q(usuario__nombre_completo__icontains=valor)
            | Q(usuario__email__icontains=valor)
            | Q(codigo__icontains=valor)
        )


class ClienteFilter(django_filters.FilterSet):
    tipo = django_filters.ChoiceFilter(choices=TipoCliente.choices)
    pais = django_filters.NumberFilter(field_name="pais_id")
    ciudad = django_filters.NumberFilter(field_name="ciudad_id")
    agente = django_filters.NumberFilter(field_name="agente_asignado_id")
    buscar = django_filters.CharFilter(method="filtrar_por_texto")

    class Meta:
        model = Cliente
        fields = ["tipo", "pais", "ciudad", "agente"]

    def filtrar_por_texto(self, consulta, nombre, valor):
        """
        Nombre, apellidos, razón social, documento, NIT, correo o código, sin
        distinguir mayúsculas.
        """
        return consulta.filter(
            Q(nombre__icontains=valor)
            | Q(apellidos__icontains=valor)
            | Q(razon_social__icontains=valor)
            | Q(documento_identidad__icontains=valor)
            | Q(nit__icontains=valor)
            | Q(email__icontains=valor)
            | Q(codigo__icontains=valor)
        )
