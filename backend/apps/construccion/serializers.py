"""Serializadores de construcción: validan el formato de entrada y arman la
salida.

Sin reglas de negocio ni acceso a la base de datos fuera de resolver el id del
país.
"""

from rest_framework import serializers

from apps.core.models import Pais
from apps.core.serializers import PaisResumenSerializer

from .models import Constructora


class ConstructoraSerializer(serializers.ModelSerializer):
    """Salida de una constructora, con su país resumido."""

    pais = PaisResumenSerializer()

    class Meta:
        model = Constructora
        fields = [
            "id",
            "codigo",
            "nombre",
            "nit",
            "contacto",
            "email",
            "telefono",
            "pais",
            "calificacion",
            "activo",
        ]


class ConstructoraEntradaSerializer(serializers.Serializer):
    """Entrada para crear (POST) o editar (PATCH, parcial) una constructora."""

    nombre = serializers.CharField(max_length=200)
    # Obligatorio (regla 4). Si queda vacío al normalizarlo, lo rechaza el servicio.
    nit = serializers.CharField(max_length=30)
    contacto = serializers.CharField(max_length=150, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    telefono = serializers.CharField(max_length=30, allow_blank=True, default="")
    pais = serializers.PrimaryKeyRelatedField(queryset=Pais.objects.filter(activo=True))
    # Regla 6: de 1 a 5, u omitida mientras no haya trabajos que calificar.
    calificacion = serializers.IntegerField(
        min_value=1, max_value=5, allow_null=True, default=None
    )
