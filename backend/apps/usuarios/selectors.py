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
    """
    email = Usuario.objects.normalize_email(email)
    return Usuario.objects.filter(email=email).values_list("id", flat=True).first()
