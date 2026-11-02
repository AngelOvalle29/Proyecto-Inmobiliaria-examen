"""Serializadores de usuarios: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.
"""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.core.serializers import PaisResumenSerializer

from .models import Usuario


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    # Sin recortar espacios: forman parte de la contraseña si el usuario los puso.
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokensSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class RenovarTokenSerializer(TokenRefreshSerializer):
    """
    El de SimpleJWT, salvo un caso: si el usuario del token ya no existe (por
    ejemplo, se reinició la base), SimpleJWT 5.5.1 deja escapar DoesNotExist y
    la API responde 500. Aquí es un 401 NO_AUTENTICADO, como un token inválido
    (spec 001, §5), y el frontend cierra la sesión.
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except Usuario.DoesNotExist as error:
            raise AuthenticationFailed(
                "El usuario de esta sesión ya no existe.", "usuario_inexistente"
            ) from error


class UsuarioListadoSerializer(serializers.ModelSerializer):
    """
    Un usuario en el listado de /usuarios/ (spec 013, regla 3). Solo lo mínimo
    para elegirlo: sin teléfono, último acceso ni permisos, porque es un
    listado de todo el personal.
    """

    rol = serializers.CharField(source="rol.nombre")
    # Nulo si el usuario no tiene país (por ejemplo, el administrador inicial).
    pais = PaisResumenSerializer(allow_null=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre_completo", "rol", "pais"]


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
