"""Serializadores de arrendamientos: validan el formato de entrada y arman la
salida.

Sin reglas de negocio. Los ids se validan con consultas de selectores; el
cliente, solo entre los visibles para quien firma (cartera, spec 004).
"""

from decimal import Decimal

from rest_framework import serializers

from apps.catalogo.selectors import (
    listar_documentos,
    listar_propiedades,
    listar_unidades,
)
from apps.catalogo.serializers import (
    DocumentoOficialResumenSerializer,
    PropiedadResumenSerializer,
)
from apps.core.selectors import listar_monedas
from apps.core.serializers import MonedaResumenSerializer
from apps.crm.models import Cliente
from apps.crm.selectors import listar_clientes_visibles
from apps.crm.serializers import (
    AgenteResumenSerializer,
    ClienteResumenSerializer,
    UnidadResumenSerializer,
)

from .models import ContratoArrendamiento, PagoRenta


class PagoRentaSerializer(serializers.ModelSerializer):
    """Un mes de renta, con si está en mora (regla 8)."""

    # DRF llama a PagoRenta.en_mora() sin argumentos: usa la fecha de hoy.
    en_mora = serializers.BooleanField(read_only=True)

    class Meta:
        model = PagoRenta
        fields = [
            "id",
            "periodo_anio",
            "periodo_mes",
            "fecha_vencimiento",
            "monto",
            "estado",
            "en_mora",
            "fecha_pago",
            "monto_pagado",
            "mora_aplicada",
            "referencia_pago",
            "tasa_a_usd",
        ]


class ArrendamientoSerializer(serializers.ModelSerializer):
    """Salida de un contrato en el listado (sin sus pagos)."""

    cliente = ClienteResumenSerializer()
    agente = AgenteResumenSerializer()
    propiedad = PropiedadResumenSerializer(allow_null=True)
    unidad = UnidadResumenSerializer(allow_null=True)
    moneda = MonedaResumenSerializer()
    documento = DocumentoOficialResumenSerializer(allow_null=True)

    class Meta:
        model = ContratoArrendamiento
        fields = [
            "id",
            "codigo",
            "cliente",
            "agente",
            "propiedad",
            "unidad",
            "fecha_inicio",
            "duracion_meses",
            "fecha_fin",
            "renta_mensual",
            "moneda",
            "tasa_a_usd",
            "deposito",
            "dia_cobro",
            "dias_gracia",
            "porcentaje_mora",
            "estado",
            "fecha_rescision",
            "contrato_anterior",
            "documento",
        ]


class ArrendamientoDetalleSerializer(ArrendamientoSerializer):
    """El detalle trae además sus pagos de renta: el calendario de cobros."""

    pagos = PagoRentaSerializer(many=True, read_only=True)

    class Meta(ArrendamientoSerializer.Meta):
        fields = [*ArrendamientoSerializer.Meta.fields, "pagos"]


class FirmarArrendamientoSerializer(serializers.Serializer):
    """Entrada para firmar (reglas 1 a 3), con los rangos de la regla 3."""

    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.none())
    propiedad = serializers.PrimaryKeyRelatedField(
        queryset=listar_propiedades(), required=False
    )
    unidad = serializers.PrimaryKeyRelatedField(
        queryset=listar_unidades(), required=False
    )
    fecha_inicio = serializers.DateField()
    duracion_meses = serializers.IntegerField(min_value=1, max_value=120)
    renta_mensual = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    moneda = serializers.PrimaryKeyRelatedField(queryset=listar_monedas())
    deposito = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False
    )
    dia_cobro = serializers.IntegerField(min_value=1, max_value=28)
    dias_gracia = serializers.IntegerField(min_value=0, max_value=31)
    porcentaje_mora = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )
    documento = serializers.PrimaryKeyRelatedField(
        queryset=listar_documentos(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuario = self.context.get("usuario")
        if usuario is not None:
            self.fields["cliente"].queryset = listar_clientes_visibles(usuario=usuario)

    def validate(self, datos: dict) -> dict:
        if ("propiedad" in datos) == ("unidad" in datos):
            raise serializers.ValidationError(
                {"propiedad": ["Indique una propiedad o una unidad."]}
            )
        return datos


class VincularDocumentoSerializer(serializers.Serializer):
    """Vincula o cambia el documento; no acepta null: no se quita (regla 18)."""

    documento = serializers.PrimaryKeyRelatedField(queryset=listar_documentos())


class RenovarArrendamientoSerializer(serializers.Serializer):
    renta_mensual = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    duracion_meses = serializers.IntegerField(min_value=1, max_value=120)


class RescindirArrendamientoSerializer(serializers.Serializer):
    fecha_rescision = serializers.DateField()


class PagarRentaSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    monto = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    referencia = serializers.CharField(max_length=100, allow_blank=True)
