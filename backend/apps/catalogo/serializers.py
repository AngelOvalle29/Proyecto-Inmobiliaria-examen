"""Serializadores de catálogo: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.

Las relaciones se leen como un resumen ({"id": 3, "nombre": "Antigua"}) y se
escriben con su id en un campo aparte (ciudad_id: 3). El frontend muestra el
nombre sin otra petición, y al guardar solo manda el número. Los querysets de
los campos *_id vienen de los selectores: así solo se acepta un tipo, una
ciudad o una moneda activos.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.core.selectors import listar_ciudades, listar_monedas
from apps.core.serializers import MonedaResumenSerializer, PaisResumenSerializer

from .enums import EstadoPropiedad
from .models import Propiedad, TipoPropiedad, Unidad
from .selectors import listar_tipos_propiedad

# Regla 4: precios y áreas mayores que cero. La base lo garantiza con sus
# constraints; validarlo aquí da un 400 con el campo señalado en vez de un 500.
MAYOR_QUE_CERO = {"min_value": Decimal("0.01")}


class TipoPropiedadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoPropiedad
        fields = ["id", "nombre", "descripcion", "requiere_unidades"]


class TipoPropiedadResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class CiudadConPaisSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    pais = PaisResumenSerializer()


class PropiedadSerializer(serializers.ModelSerializer):
    tipo = TipoPropiedadResumenSerializer(read_only=True)
    tipo_id = serializers.PrimaryKeyRelatedField(
        source="tipo", queryset=listar_tipos_propiedad(), write_only=True
    )
    ciudad = CiudadConPaisSerializer(read_only=True)
    ciudad_id = serializers.PrimaryKeyRelatedField(
        source="ciudad", queryset=listar_ciudades(), write_only=True
    )
    moneda = MonedaResumenSerializer(read_only=True)
    moneda_id = serializers.PrimaryKeyRelatedField(
        source="moneda", queryset=listar_monedas(), write_only=True
    )

    class Meta:
        model = Propiedad
        fields = [
            "id",
            "codigo",
            "nombre",
            "tipo",
            "tipo_id",
            "ciudad",
            "ciudad_id",
            "direccion",
            "latitud",
            "longitud",
            "area_m2",
            "area_construida_m2",
            "estado",
            "precio_lista",
            "moneda",
            "moneda_id",
            "es_publica",
            "descripcion",
            "creado_en",
            "actualizado_en",
        ]
        # El estado solo cambia por /cambiar-estado/ (regla 7).
        read_only_fields = ["codigo", "estado", "creado_en", "actualizado_en"]
        extra_kwargs = {
            "area_m2": MAYOR_QUE_CERO,
            "area_construida_m2": MAYOR_QUE_CERO,
            "precio_lista": MAYOR_QUE_CERO,
        }


class CambiarEstadoSerializer(serializers.Serializer):
    """Entrada de /propiedades/{id}/cambiar-estado/ y /unidades/{id}/cambiar-estado/."""

    estado = serializers.ChoiceField(choices=EstadoPropiedad.choices)
    # Obligatorio: queda en la bitácora y explica por qué cambió a mano.
    motivo = serializers.CharField(max_length=255)


class PropiedadResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()


class UnidadSerializer(serializers.ModelSerializer):
    # La propiedad sale de la URL al crear y no se cambia después.
    propiedad = PropiedadResumenSerializer(read_only=True)
    moneda = MonedaResumenSerializer(read_only=True)
    moneda_id = serializers.PrimaryKeyRelatedField(
        source="moneda", queryset=listar_monedas(), write_only=True
    )

    class Meta:
        model = Unidad
        fields = [
            "id",
            "propiedad",
            "codigo",
            "nivel",
            "area_m2",
            "habitaciones",
            "banos",
            "estado",
            "precio_lista",
            "moneda",
            "moneda_id",
        ]
        # Como en la propiedad, el estado solo cambia por /cambiar-estado/.
        read_only_fields = ["estado"]
        extra_kwargs = {
            "area_m2": MAYOR_QUE_CERO,
            "precio_lista": MAYOR_QUE_CERO,
        }
