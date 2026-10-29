"""Servicios de auditoría: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth.base_user import AbstractBaseUser

from .enums import AccionAuditoria
from .models import LogAuditoria


def registrar_auditoria(
    *,
    usuario: AbstractBaseUser | None,
    entidad: str,
    entidad_id: int | None,
    accion: AccionAuditoria,
    valores_anteriores: dict | None = None,
    valores_nuevos: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> LogAuditoria:
    """
    Registra una operación en la bitácora del sistema (CLAUDE.md §8).

    Se llama explícitamente desde cada servicio de escritura, y no con
    señales de Django, para que la auditoría se vea en el código que escribe.

    No abre su propia transacción a propósito: debe llamarse dentro de la
    transacción del servicio que escribe. Así, si la operación de negocio
    falla y se revierte, su registro se revierte con ella, y nunca queda una
    operación sin registro ni un registro de algo que no ocurrió.

    usuario es None cuando la acción la hace el sistema (una tarea
    programada) o cuando nadie se autenticó (un login fallido). Se anota como
    AbstractBaseUser, la clase de Django, para no importar la app usuarios.
    """
    return LogAuditoria.objects.create(
        usuario=usuario,
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        valores_anteriores=valores_anteriores,
        valores_nuevos=valores_nuevos,
        ip=ip,
        user_agent=user_agent or "",
    )
