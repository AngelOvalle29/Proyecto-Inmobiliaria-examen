"""Serializadores de core: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.
"""

from rest_framework import serializers

from .models import Ciudad, Moneda, Pais, TipoCambio

# Valores posibles del servicio y de la base de datos. Tiene nombre propio en
# SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"] para que la documentación los
# muestre como un solo tipo y no como dos con las mismas opciones.
ESTADOS_SALUD = ["ok", "error"]


class EstadoServicioSerializer(serializers.Serializer):
    """Respuesta de /health/. También documenta su forma en /api/docs/."""

    estado = serializers.ChoiceField(choices=ESTADOS_SALUD)
    base_datos = serializers.ChoiceField(choices=ESTADOS_SALUD)


# ---------- Catálogos (solo lectura) ----------
#
# Las relaciones se muestran como un resumen ({id, codigo} o {id, nombre}) y no
# solo como un id: el frontend puede mostrar "GTQ" sin hacer otra petición.


class MonedaResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()


class PaisResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class MonedaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Moneda
        fields = ["id", "codigo", "nombre", "simbolo"]


class PaisSerializer(serializers.ModelSerializer):
    moneda_principal = MonedaResumenSerializer()

    class Meta:
        model = Pais
        fields = ["id", "nombre", "codigo_iso", "moneda_principal"]


class CiudadSerializer(serializers.ModelSerializer):
    pais = PaisResumenSerializer()

    class Meta:
        model = Ciudad
        fields = ["id", "nombre", "region", "pais"]


class TipoCambioSerializer(serializers.ModelSerializer):
    moneda_origen = MonedaResumenSerializer()
    moneda_destino = MonedaResumenSerializer()

    class Meta:
        model = TipoCambio
        # tasa sale como texto ("7.750000"), que es como DRF representa los
        # Decimal: un número de JSON podría perder precisión al leerse.
        fields = ["id", "moneda_origen", "moneda_destino", "tasa", "fecha"]
