"""Servicios de usuarios: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria

from .exceptions import CredencialesInvalidas
from .models import Usuario
from .selectors import obtener_id_usuario_por_email

# Nombre de la tabla de usuarios, tal como se guarda en la bitácora.
ENTIDAD_USUARIO = Usuario._meta.db_table


def iniciar_sesion(
    *, email: str, password: str, ip: str | None, user_agent: str | None
) -> dict[str, str]:
    """
    Verifica las credenciales y entrega el par de tokens JWT.

    Regla 11: todo intento queda en la bitácora, exitoso o fallido. Un
    usuario desactivado no puede iniciar sesión: authenticate lo rechaza
    igual que a una contraseña incorrecta.

    Esta función no es atómica a propósito. Si lo fuera, la excepción
    CredencialesInvalidas revertiría también el registro LOGIN_FALLIDO, y
    justo los intentos fallidos son los que más interesa conservar.
    """
    usuario = authenticate(email=email, password=password)
    if usuario is None:
        registrar_login_fallido(email=email, ip=ip, user_agent=user_agent)
        raise CredencialesInvalidas()

    registrar_acceso(usuario=usuario, ip=ip, user_agent=user_agent)
    refresh = RefreshToken.for_user(usuario)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@transaction.atomic
def registrar_acceso(
    *, usuario: Usuario, ip: str | None, user_agent: str | None
) -> None:
    """
    Actualiza el último acceso y lo registra en la bitácora (INICIAR_SESION).

    Las dos escrituras van en una transacción: o quedan ambas o ninguna.
    """
    usuario.last_login = timezone.now()
    usuario.save(update_fields=["last_login"])
    registrar_auditoria(
        usuario=usuario,
        entidad=ENTIDAD_USUARIO,
        entidad_id=usuario.pk,
        accion=AccionAuditoria.INICIAR_SESION,
        ip=ip,
        user_agent=user_agent,
    )


def registrar_login_fallido(
    *, email: str, ip: str | None, user_agent: str | None
) -> None:
    """
    Registra un intento fallido (LOGIN_FALLIDO) con el correo intentado.

    usuario queda nulo porque nadie se autenticó. Si el correo pertenece a una
    cuenta, entidad_id apunta a ella. La contraseña intentada nunca se guarda:
    podría ser la contraseña real con un error de dedo.
    """
    registrar_auditoria(
        usuario=None,
        entidad=ENTIDAD_USUARIO,
        entidad_id=obtener_id_usuario_por_email(email=email),
        accion=AccionAuditoria.LOGIN_FALLIDO,
        valores_nuevos={"email": email},
        ip=ip,
        user_agent=user_agent,
    )
