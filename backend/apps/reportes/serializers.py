"""Validación estricta de parámetros y contrato OpenAPI de la pantalla genérica."""

from rest_framework import serializers

from apps.auditoria.enums import AccionAuditoria
from apps.catalogo.enums import TipoDocumento

from .estructuras import FiltrosBitacora, FiltrosInventario, FiltrosVencimientos


class FiltrosBaseSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        desconocidos = set(data) - set(self.fields)
        if desconocidos:
            raise serializers.ValidationError(
                {k: "Filtro desconocido." for k in desconocidos}
            )
        if hasattr(data, "getlist"):
            repetidos = [k for k in data if len(data.getlist(k)) != 1]
            if repetidos:
                raise serializers.ValidationError(
                    {k: "No repita el parámetro." for k in repetidos}
                )
        return super().to_internal_value(data)


class FiltrosInventarioSerializer(FiltrosBaseSerializer):
    pais = serializers.IntegerField(min_value=1, required=False)
    ciudad = serializers.IntegerField(min_value=1, required=False)
    tipo = serializers.IntegerField(min_value=1, required=False)
    moneda = serializers.RegexField(r"^[A-Z]{3}$", required=False)
    precio_min = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False
    )
    precio_max = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False
    )
    area_min = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )
    area_max = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )

    def validate(self, attrs):
        if ("precio_min" in attrs or "precio_max" in attrs) and "moneda" not in attrs:
            raise serializers.ValidationError(
                {"moneda": "Indique moneda para filtrar por precio."}
            )
        for nombre in ("precio", "area"):
            minimo, maximo = attrs.get(nombre + "_min"), attrs.get(nombre + "_max")
            if minimo is not None and maximo is not None and minimo > maximo:
                raise serializers.ValidationError(
                    {nombre + "_max": "Debe ser mayor o igual al mínimo."}
                )
        return attrs


class FiltrosVencimientosSerializer(FiltrosBaseSerializer):
    tipo = serializers.ChoiceField(choices=TipoDocumento.choices, required=False)
    pais = serializers.IntegerField(min_value=1, required=False)
    dias_anticipacion = serializers.IntegerField(min_value=0, max_value=365, default=30)


class FiltrosBitacoraSerializer(FiltrosBaseSerializer):
    usuario = serializers.IntegerField(min_value=1, required=False)
    entidad = serializers.CharField(max_length=100, required=False)
    accion = serializers.ChoiceField(choices=AccionAuditoria.choices, required=False)
    fecha_desde = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])
    fecha_hasta = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])

    def validate(self, attrs):
        desde, hasta = attrs.get("fecha_desde"), attrs.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            raise serializers.ValidationError(
                {"fecha_hasta": "Debe ser mayor o igual a desde."}
            )
        if hasta and hasta.year == 9999:
            raise serializers.ValidationError(
                {"fecha_hasta": "La fecha máxima admitida es 9998-12-31."}
            )
        return attrs


FILTROS = {
    "inventario-disponible": (FiltrosInventarioSerializer, FiltrosInventario),
    "documentos-por-vencer": (FiltrosVencimientosSerializer, FiltrosVencimientos),
    "bitacora-auditoria": (FiltrosBitacoraSerializer, FiltrosBitacora),
}


class ColumnaReporteSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    etiqueta = serializers.CharField()
    tipo = serializers.CharField()
    formato = serializers.CharField(allow_blank=True)
    alineacion = serializers.CharField()


class OpcionFiltroSerializer(serializers.Serializer):
    valor = serializers.CharField()
    etiqueta = serializers.CharField()


class FiltroReporteSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    etiqueta = serializers.CharField()
    tipo = serializers.CharField()
    obligatorio = serializers.BooleanField()
    origen_opciones = serializers.CharField(allow_blank=True)
    buscable = serializers.BooleanField()
    opciones = OpcionFiltroSerializer(many=True)


class CatalogoReporteSerializer(serializers.Serializer):
    slug = serializers.CharField()
    codigo = serializers.CharField()
    titulo = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    columnas = ColumnaReporteSerializer(many=True)
    filtros = FiltroReporteSerializer(many=True)


class FilasReporteSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = serializers.ListField(
        child=serializers.DictField(child=serializers.JSONField())
    )


class GrupoReporteSerializer(serializers.Serializer):
    etiqueta = serializers.CharField()
    valores = serializers.DictField(child=serializers.JSONField())


class ReporteSerializer(serializers.Serializer):
    titulo = serializers.CharField()
    subtitulo = serializers.CharField()
    generado_en = serializers.DateTimeField()
    generado_por = serializers.CharField()
    columnas = ColumnaReporteSerializer(many=True)
    totales = serializers.DictField(child=serializers.JSONField())
    agrupamientos = GrupoReporteSerializer(many=True)
    filas = FilasReporteSerializer()
