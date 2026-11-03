"""Serializadores de catálogo: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.

Las relaciones se leen como un resumen ({"id": 3, "nombre": "Antigua"}) y se
escriben con su id en un campo aparte (ciudad_id: 3). El frontend muestra el
nombre sin otra petición, y al guardar solo manda el número. Los querysets de
los campos *_id vienen de los selectores: así solo se acepta un tipo, una
ciudad o una moneda activos.
"""

from decimal import Decimal

from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import serializers

from apps.core.selectors import listar_ciudades, listar_monedas
from apps.core.serializers import MonedaResumenSerializer, PaisResumenSerializer

from .enums import EstadoPropiedad, TipoDocumento
from .models import (
    Avaluo,
    DocumentoOficial,
    ImagenPropiedad,
    Propiedad,
    TipoPropiedad,
    Unidad,
)
from .selectors import listar_documentos, listar_tipos_propiedad

# Regla 4: precios y áreas mayores que cero. La base lo garantiza con sus
# constraints; validarlo aquí da un 400 con el campo señalado en vez de un 500.
MAYOR_QUE_CERO = {"min_value": Decimal("0.01")}

# Spec 019, regla 8: la URL firmada de S3 vence a los 5 minutos
# (querystring_expire en config/settings/base.py).
SEGUNDOS_URL_IMAGEN = 300


def url_de_imagen(imagen: ImagenPropiedad, request) -> str:
    """
    La URL para mostrar la imagen (spec 019, regla 8). Con S3, default_storage
    la firma con la llave: es un cálculo local, sin consultar a Supabase, y ya
    es absoluta. En desarrollo el almacenamiento es local y devuelve
    /media/...: se completa con el host de la API, como la descarga de
    documentos.
    """
    url = default_storage.url(imagen.archivo.name)
    if url.startswith("/") and request is not None:
        url = request.build_absolute_uri(url)
    return url


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
    portada_url = serializers.SerializerMethodField()

    class Meta:
        model = Propiedad
        fields = [
            "id",
            "codigo",
            "nombre",
            "portada_url",
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

    def get_portada_url(self, propiedad: Propiedad) -> str | None:
        """
        Spec 019, §5: la URL firmada de la portada, o null. Las portadas vienen
        del Prefetch de listar_propiedades_con_portada; sin él (la respuesta de
        crear o editar) se devuelve null y la pantalla vuelve a pedir la lista,
        en vez de hacer aquí una consulta por propiedad.
        """
        portadas = getattr(propiedad, "portadas", None)
        if not portadas:
            return None
        return url_de_imagen(portadas[0], self.context.get("request"))


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


class DocumentoOficialResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    tipo = serializers.CharField()


class AvaluoSerializer(serializers.ModelSerializer):
    # La propiedad sale de la URL al registrar y no se cambia: un avalúo no se
    # edita (regla 3).
    propiedad = PropiedadResumenSerializer(read_only=True)
    moneda = MonedaResumenSerializer(read_only=True)
    moneda_id = serializers.PrimaryKeyRelatedField(
        source="moneda", queryset=listar_monedas(), write_only=True
    )
    # allow_null: un avalúo puede no tener documento, y así el esquema (y el
    # tipo generado del frontend) lo dice (spec 014).
    documento = DocumentoOficialResumenSerializer(read_only=True, allow_null=True)
    documento_id = serializers.PrimaryKeyRelatedField(
        source="documento",
        queryset=listar_documentos(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Avaluo
        fields = [
            "id",
            "propiedad",
            "fecha",
            "valor",
            "moneda",
            "moneda_id",
            "perito",
            "metodologia",
            "documento",
            "documento_id",
            "observaciones",
        ]
        extra_kwargs = {"valor": MAYOR_QUE_CERO}

    def validate_fecha(self, valor):
        # Regla 2: el servicio lo vuelve a comprobar; aquí se señala el campo.
        if valor > timezone.localdate():
            raise serializers.ValidationError("No puede ser futura.")
        return valor


class DocumentoOficialSerializer(serializers.ModelSerializer):
    # El archivo no se expone: se descarga por /descarga/ con una URL firmada.
    # Tampoco se puede reemplazar ni cambiar el tipo (regla 7).
    propiedad = PropiedadResumenSerializer(read_only=True)

    class Meta:
        model = DocumentoOficial
        fields = [
            "id",
            "propiedad",
            "tipo",
            "nombre",
            "nombre_original",
            "tipo_contenido",
            "tamano_bytes",
            "fecha_emision",
            "fecha_vencimiento",
            "emisor",
            "creado_en",
        ]
        read_only_fields = [
            "propiedad",
            "tipo",
            "nombre_original",
            "tipo_contenido",
            "tamano_bytes",
            "creado_en",
        ]

    def validate(self, datos):
        emision = datos.get("fecha_emision", self.instance.fecha_emision)
        vencimiento = datos.get("fecha_vencimiento", self.instance.fecha_vencimiento)
        if vencimiento is not None and vencimiento < emision:
            raise serializers.ValidationError(
                {"fecha_vencimiento": ["No puede ser anterior a la fecha de emisión."]}
            )
        return datos


class DocumentoSubirSerializer(serializers.Serializer):
    """Entrada de la subida: multipart con el archivo y sus datos (regla 5)."""

    archivo = serializers.FileField()
    tipo = serializers.ChoiceField(choices=TipoDocumento.choices)
    nombre = serializers.CharField(max_length=200)
    fecha_emision = serializers.DateField()
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)
    emisor = serializers.CharField(max_length=150)

    def validate(self, datos):
        vencimiento = datos.get("fecha_vencimiento")
        if vencimiento is not None and vencimiento < datos["fecha_emision"]:
            raise serializers.ValidationError(
                {"fecha_vencimiento": ["No puede ser anterior a la fecha de emisión."]}
            )
        return datos


class DescargaDocumentoSerializer(serializers.Serializer):
    url = serializers.CharField()
    vence_en_segundos = serializers.IntegerField()


class ImagenPropiedadSerializer(serializers.ModelSerializer):
    """
    Una imagen de la galería (spec 019, §5). Se editan solo la descripción y
    el orden (regla 4); la portada cambia por /marcar-portada/.
    """

    url = serializers.SerializerMethodField()
    vence_en_segundos = serializers.SerializerMethodField()

    class Meta:
        model = ImagenPropiedad
        fields = [
            "id",
            "descripcion",
            "orden",
            "es_portada",
            "url",
            "vence_en_segundos",
            "nombre_original",
            "creado_en",
        ]
        read_only_fields = ["es_portada", "nombre_original", "creado_en"]
        extra_kwargs = {"orden": {"min_value": 1}}

    def get_url(self, imagen: ImagenPropiedad) -> str:
        return url_de_imagen(imagen, self.context.get("request"))

    def get_vence_en_segundos(self, imagen: ImagenPropiedad) -> int:
        return SEGUNDOS_URL_IMAGEN


class ImagenSubirSerializer(serializers.Serializer):
    """Entrada de la subida: multipart con la foto y su descripción (regla 1)."""

    archivo = serializers.FileField()
    descripcion = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
