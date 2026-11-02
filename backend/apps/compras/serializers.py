"""Serializadores de compras: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos: los ids de país y ciudad
se resuelven con los selectores de core, como en crm.
"""

from rest_framework import serializers

from apps.core.selectors import listar_ciudades, listar_paises
from apps.core.serializers import PaisResumenSerializer

from .enums import TipoProveedor
from .models import Proveedor


class CiudadResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ProveedorSerializer(serializers.ModelSerializer):
    """Salida de un proveedor, con su país y ciudad resumidos."""

    pais = PaisResumenSerializer()
    ciudad = CiudadResumenSerializer(allow_null=True)

    class Meta:
        model = Proveedor
        fields = [
            "id",
            "codigo",
            "tipo",
            "nombre",
            "nit",
            "email",
            "telefono",
            "pais",
            "ciudad",
            "direccion",
            "activo",
        ]


class ProveedorEntradaSerializer(serializers.Serializer):
    """Entrada para crear (POST) o editar (PATCH, parcial) un proveedor.

    El NIT llega como lo escribe el usuario; el servicio lo normaliza y decide
    si es obligatorio según el tipo (spec 006, reglas 2 y 3).
    """

    tipo = serializers.ChoiceField(choices=TipoProveedor.choices)
    nombre = serializers.CharField(max_length=200)
    nit = serializers.CharField(max_length=30, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    telefono = serializers.CharField(max_length=30, allow_blank=True, default="")
    pais = serializers.PrimaryKeyRelatedField(queryset=listar_paises())
    ciudad = serializers.PrimaryKeyRelatedField(
        queryset=listar_ciudades(), allow_null=True, default=None
    )
    direccion = serializers.CharField(max_length=255, allow_blank=True, default="")
