"""Selectores de usuarios: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from .models import Usuario


def obtener_id_usuario_por_email(*, email: str) -> int | None:
    """
    Id del usuario con ese correo, o None si no existe.

    Lo usa la auditoría de logins fallidos: un intento fallido sobre una
    cuenta que sí existe queda asociado a ella, así se pueden detectar
    intentos repetidos contra una misma cuenta.

    Busca sin distinguir mayúsculas, igual que el login
    (UsuarioManager.get_by_natural_key): una cuenta guardada con mayúsculas
    antes de normalizar los correos se autentica, y sus intentos fallidos
    también deben quedar asociados a ella.
    """
    return (
        Usuario.objects.filter(email__iexact=email).values_list("id", flat=True).first()
    )


def existe_superusuario() -> bool:
    """
    True si ya hay al menos un superusuario.

    Lo usa el arranque del contenedor para crear el administrador inicial una
    sola vez (spec 002, §5.8): si ya existe alguno, no se crea otro.
    """
    return Usuario.objects.filter(is_superuser=True).exists()
