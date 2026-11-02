"""Serializadores de compras: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos: los ids se resuelven con
los selectores de core, catalogo y compras, como en crm y ventas.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.catalogo.selectors import listar_propiedades
from apps.catalogo.serializers import PropiedadResumenSerializer
from apps.core.selectors import listar_ciudades, listar_monedas, listar_paises
from apps.core.serializers import MonedaResumenSerializer, PaisResumenSerializer

from .enums import TipoProveedor
from .models import ContratoCompra, Proveedor
from .selectors import listar_proveedores


class CiudadDeProveedorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ProveedorSerializer(serializers.ModelSerializer):
    """Salida de un proveedor, con su país y ciudad resumidos."""

    pais = PaisResumenSerializer()
    ciudad = CiudadDeProveedorSerializer(allow_null=True)

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


# ---------- Contratos de compra (spec 017) ----------


class ProveedorResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()


class ContratoCompraSerializer(serializers.ModelSerializer):
    """Salida de un contrato de compra, con proveedor, propiedad y moneda."""

    proveedor = ProveedorResumenSerializer()
    propiedad = PropiedadResumenSerializer()
    moneda = MonedaResumenSerializer()

    class Meta:
        model = ContratoCompra
        fields = [
            "id",
            "codigo",
            "proveedor",
            "propiedad",
            "fecha_compra",
            "monto",
            "gastos_legales",
            "impuestos",
            "costo_total",
            "moneda",
            "tasa_a_usd",
            "costo_total_usd",
            "estado",
            "observaciones",
        ]


class ContratoCompraEntradaSerializer(serializers.Serializer):
    """
    Entrada para registrar un contrato (POST). Solo valida el formato: que la
    propiedad esté en negociación y sin otro contrato, la fecha y la tasa los
    revisa el servicio (spec 017, reglas 1 a 5).

    El proveedor se busca entre los activos: uno desactivado responde 400 como
    si no existiera (regla 1). costo_total no se recibe: lo calcula el sistema.
    """

    proveedor = serializers.PrimaryKeyRelatedField(queryset=listar_proveedores())
    propiedad = serializers.PrimaryKeyRelatedField(queryset=listar_propiedades())
    fecha_compra = serializers.DateField()
    monto = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    gastos_legales = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    impuestos = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    moneda = serializers.PrimaryKeyRelatedField(queryset=listar_monedas())
    observaciones = serializers.CharField(allow_blank=True, default="")


class MotivoContratoCompraSerializer(serializers.Serializer):
    """Entrada de /anular/: el motivo es obligatorio (regla 7)."""

    motivo = serializers.CharField(max_length=255)
