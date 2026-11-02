"""Servicios de usuarios: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria

from .exceptions import CredencialesInvalidas
from .models import Rol, Usuario
from .selectors import existe_superusuario, obtener_id_usuario_por_email

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


@transaction.atomic
def asegurar_administrador_inicial(
    *, email: str, nombre_completo: str, password: str
) -> Usuario | None:
    """
    Crea el primer superusuario si todavía no existe ninguno, y devuelve el
    usuario creado o None si no hizo nada.

    Existe porque el plan gratuito de Render no da terminal para correr
    createsuperuser (spec 002, §5.8): lo llama el arranque del contenedor en
    cada despliegue, así que debe ser idempotente. Si ya hay un superusuario, no
    crea otro ni cambia la contraseña del existente.

    La contraseña pasa por los mismos validadores que en el panel (mínimo 10
    caracteres, no parecida al correo, no común). Si no los cumple se lanza
    ValidationError: el contenedor no arranca y Render conserva la versión
    anterior, en lugar de quedar un administrador con una contraseña débil.

    Se audita como CREAR con usuario nulo, porque lo hace el sistema.
    """
    if existe_superusuario():
        return None

    # Usuario sin guardar, solo para que el validador compare la contraseña con
    # el correo y el nombre.
    validate_password(
        password, user=Usuario(email=email, nombre_completo=nombre_completo)
    )
    usuario = Usuario.objects.create_superuser(
        email=email, password=password, nombre_completo=nombre_completo
    )
    registrar_auditoria(
        usuario=None,
        entidad=ENTIDAD_USUARIO,
        entidad_id=usuario.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos={
            "email": usuario.email,
            "nombre_completo": usuario.nombre_completo,
            "rol": usuario.rol.nombre,
            "origen": "arranque del contenedor",
        },
    )
    return usuario


def asegurar_usuario_demo(
    *, email: str, nombre_completo: str, rol: str, password: str | None
) -> tuple[Usuario, bool]:
    """
    Usuario ficticio de los datos de demostración de otras apps (por ejemplo,
    los agentes de crm, spec 004). Devuelve el usuario y si lo acaba de crear.

    Es idempotente: si el correo ya existe, no lo toca. Solo al crearlo usa la
    contraseña recibida; con None la deja inutilizable, así ningún usuario de
    demostración puede iniciar sesión con una contraseña escrita en el
    repositorio (seed_demo corre en cada arranque de producción, spec 002).

    No registra auditoría, como el resto de los datos de demostración.
    """
    existente = Usuario.objects.filter(email__iexact=email).first()
    if existente is not None:
        return existente, False

    # Con password=None, create_user (set_password de Django) guarda una
    # contraseña inutilizable: ninguna contraseña la valida.
    usuario = Usuario.objects.create_user(
        email=email,
        password=password,
        nombre_completo=nombre_completo,
        rol=Rol.objects.get(nombre=rol),
    )
    return usuario, True
