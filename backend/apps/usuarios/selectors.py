"""Selectores de usuarios: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import QuerySet

from .enums import NombreRol
from .models import Rol, Usuario


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


ESTADOS_LISTADO = {"ACTIVOS": True, "INACTIVOS": False, "TODOS": None}


def listar_usuarios(*, estado: str = "ACTIVOS") -> QuerySet[Usuario]:
    """
    Usuarios para la pantalla de gestión (spec 026): activos, inactivos o
    todos. Con ACTIVOS es igual a listar_usuarios_activos.
    """
    usuarios = Usuario.objects.select_related("rol", "pais").order_by(
        "nombre_completo", "id"
    )
    activo = ESTADOS_LISTADO[estado]
    if activo is not None:
        usuarios = usuarios.filter(is_active=activo)
    return usuarios


def contar_administradores_activos() -> int:
    """Spec 026, regla 5: cuántos administradores pueden iniciar sesión."""
    return Usuario.objects.filter(
        is_active=True, rol__nombre=NombreRol.ADMINISTRADOR
    ).count()


def tiene_perfil_de_agente_activo(*, usuario: Usuario) -> bool:
    """
    Spec 026, regla 7. Usa la relación inversa usuario.agente en lugar de
    importar crm: crm ya depende de usuarios y la importación sería circular.
    Sin perfil, Django lanza una excepción que también es AttributeError, por
    eso basta getattr con None.
    """
    agente = getattr(usuario, "agente", None)
    return agente is not None and agente.activo


def listar_roles() -> QuerySet[Rol]:
    """Los cinco roles, para elegir el de un usuario (spec 026)."""
    return Rol.objects.order_by("nombre")
