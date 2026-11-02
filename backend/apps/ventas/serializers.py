"""Serializadores de ventas: validan el formato de entrada y arman la salida.

Sin reglas de negocio. Los campos que reciben un id validan que exista con
una consulta que viene de un selector; la cotización y el cliente, además,
solo entre los visibles para quien firma (cartera, spec 004).
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
from apps.crm.models import Cliente, Cotizacion
from apps.crm.selectors import listar_clientes_visibles, listar_cotizaciones_visibles
from apps.crm.serializers import (
    AgenteResumenSerializer,
    ClienteResumenSerializer,
    UnidadResumenSerializer,
)

from .enums import ModalidadVenta
from .models import ContratoVenta, CuotaPago

# Los datos del plan que exige una venta financiada (regla 11).
DATOS_DEL_PLAN = ["numero_cuotas", "tasa_interes_anual", "fecha_primera_cuota"]


class CuotaSerializer(serializers.ModelSerializer):
    """Una cuota, con lo que falta pagar y si está en mora (regla 17)."""

    saldo = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    # DRF llama a CuotaPago.en_mora() sin argumentos: usa la fecha de hoy.
    en_mora = serializers.BooleanField(read_only=True)

    class Meta:
        model = CuotaPago
        fields = [
            "id",
            "numero",
            "fecha_vencimiento",
            "monto_capital",
            "monto_interes",
            "monto_total",
            "estado",
            "monto_pagado",
            "saldo",
            "en_mora",
            "fecha_ultimo_pago",
            "referencia_ultimo_pago",
            "tasa_a_usd_ultimo_pago",
        ]


class ContratoVentaSerializer(serializers.ModelSerializer):
    """Salida de un contrato en el listado (sin sus cuotas)."""

    cliente = ClienteResumenSerializer()
    agente = AgenteResumenSerializer()
    propiedad = PropiedadResumenSerializer(allow_null=True)
    unidad = UnidadResumenSerializer(allow_null=True)
    moneda = MonedaResumenSerializer()
    documento = DocumentoOficialResumenSerializer(allow_null=True)

    class Meta:
        model = ContratoVenta
        fields = [
            "id",
            "codigo",
            "cotizacion",
            "cliente",
            "agente",
            "propiedad",
            "unidad",
            "fecha_firma",
            "monto_total",
            "moneda",
            "tasa_a_usd",
            "monto_total_usd",
            "modalidad",
            "enganche",
            "numero_cuotas",
            "tasa_interes_anual",
            "fecha_primera_cuota",
            "comision_agente",
            "estado",
            "observaciones",
            "documento",
        ]


class ContratoVentaDetalleSerializer(ContratoVentaSerializer):
    """El detalle trae además sus cuotas (vacío en un contrato de contado)."""

    cuotas = CuotaSerializer(many=True, read_only=True)

    class Meta(ContratoVentaSerializer.Meta):
        fields = [*ContratoVentaSerializer.Meta.fields, "cuotas"]


class FirmarContratoSerializer(serializers.Serializer):
    """
    Entrada para firmar (regla 7): con `cotizacion`, o sin ella con `cliente`,
    `propiedad` o `unidad`, `monto_total` y `moneda`. Con cotización, esos
    cinco datos salen de ella y no se envían.
    """

    cotizacion = serializers.PrimaryKeyRelatedField(
        queryset=Cotizacion.objects.none(), required=False
    )
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.none(), required=False
    )
    propiedad = serializers.PrimaryKeyRelatedField(
        queryset=listar_propiedades(), required=False
    )
    unidad = serializers.PrimaryKeyRelatedField(
        queryset=listar_unidades(), required=False
    )
    monto_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    moneda = serializers.PrimaryKeyRelatedField(
        queryset=listar_monedas(), required=False
    )
    fecha_firma = serializers.DateField()
    modalidad = serializers.ChoiceField(choices=ModalidadVenta.choices)
    enganche = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False
    )
    numero_cuotas = serializers.IntegerField(min_value=1, max_value=360, required=False)
    tasa_interes_anual = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False
    )
    fecha_primera_cuota = serializers.DateField(required=False)
    observaciones = serializers.CharField(required=False, allow_blank=True)
    documento = serializers.PrimaryKeyRelatedField(
        queryset=listar_documentos(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuario = self.context.get("usuario")
        if usuario is not None:
            self.fields["cotizacion"].queryset = listar_cotizaciones_visibles(
                usuario=usuario
            )
            self.fields["cliente"].queryset = listar_clientes_visibles(usuario=usuario)

    def validate(self, datos: dict) -> dict:
        errores = {}
        if "cotizacion" in datos:
            for campo in ["cliente", "propiedad", "unidad", "monto_total", "moneda"]:
                if campo in datos:
                    errores[campo] = ["Con cotización, este dato sale de ella."]
        else:
            for campo in ["cliente", "monto_total", "moneda"]:
                if campo not in datos:
                    errores[campo] = ["Obligatorio si no hay cotización."]
            if ("propiedad" in datos) == ("unidad" in datos):
                errores["propiedad"] = ["Indique una propiedad o una unidad."]

        if datos["modalidad"] == ModalidadVenta.FINANCIADO:
            for campo in DATOS_DEL_PLAN:
                if campo not in datos:
                    errores[campo] = ["Obligatorio en una venta financiada."]
        if errores:
            raise serializers.ValidationError(errores)
        return datos


class VincularDocumentoVentaSerializer(serializers.Serializer):
    """Vincula o cambia el documento; no acepta null: no se quita (regla 24)."""

    documento = serializers.PrimaryKeyRelatedField(queryset=listar_documentos())


class PagoCuotaSerializer(serializers.Serializer):
    monto = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    fecha = serializers.DateField()
    referencia = serializers.CharField(max_length=100, allow_blank=True)
