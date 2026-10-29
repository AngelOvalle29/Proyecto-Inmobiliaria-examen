"""Serializadores de usuarios: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.
"""

from rest_framework import serializers

from apps.core.serializers import PaisResumenSerializer

from .models import Usuario


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    # Sin recortar espacios: forman parte de la contraseña si el usuario los puso.
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokensSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class UsuarioActualSerializer(serializers.ModelSerializer):
    """Respuesta de /auth/yo/ (spec 001, §5)."""

    rol = serializers.CharField(source="rol.nombre")
    pais = PaisResumenSerializer(allow_null=True)
    ultimo_acceso = serializers.DateTimeField(source="last_login", allow_null=True)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre_completo",
            "rol",
            "pais",
            "telefono",
            "ultimo_acceso",
        ]
