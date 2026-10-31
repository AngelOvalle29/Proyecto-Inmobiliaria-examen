"""Selectores de usuarios: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

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


def listar_usuarios_activos() -> QuerySet[Usuario]:
    """
    Usuarios que pueden iniciar sesión (is_active es su borrado lógico).

    Lo usan otras apps para validar que un id de usuario recibido en la API
    exista, por ejemplo al crear el perfil de agente (spec 004), y el listado
    de /usuarios/ para elegir a quién crearle ese perfil (spec 013).

    Rol y país vienen en la misma consulta, para que el listado no haga una
    consulta más por usuario. El orden por nombre es el que se muestra al
    elegir; el id desempata a dos personas con el mismo nombre, para que la
    paginación sea estable.
    """
    return (
        Usuario.objects.filter(is_active=True)
        .select_related("rol", "pais")
        .order_by("nombre_completo", "id")
    )
