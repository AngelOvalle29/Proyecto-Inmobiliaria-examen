"""Servicios de usuarios: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria

from .enums import NombreRol
from .exceptions import (
    ContrasenaActualIncorrecta,
    ContrasenaInvalida,
    CredencialesInvalidas,
    OperacionSobreSiMismo,
    SuperusuarioEsAdministrador,
    UltimoAdministrador,
    UsuarioConPerfilAgente,
    UsuarioDuplicado,
)
from .models import Rol, Usuario
from .selectors import (
    contar_administradores_activos,
    existe_superusuario,
    obtener_id_usuario_por_email,
    tiene_perfil_de_agente_activo,
)

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


# --- Gestión de usuarios (spec 026) -----------------------------------------

# Lo que se puede editar después de crear la cuenta. El correo no: identifica
# la cuenta y su historial en la bitácora (spec 026, §10).
CAMPOS_EDITABLES = ["nombre_completo", "rol", "pais", "telefono"]


def _valores(usuario: Usuario, campos: list[str]) -> dict:
    """Los campos como se guardan en la bitácora: rol y país por su nombre."""
    valores = {}
    for campo in campos:
        valor = getattr(usuario, campo)
        if campo == "rol":
            valor = valor.nombre
        elif campo == "pais":
            valor = valor.nombre if valor else None
        valores[campo] = valor
    return valores


def _validar_contrasena(password: str, *, usuario: Usuario, campo: str) -> None:
    """Regla 3: los mismos validadores que el panel de Django."""
    try:
        validate_password(password, user=usuario)
    except ValidationError as error:
        raise ContrasenaInvalida(motivos=list(error.messages), campo=campo) from error


def _bloquear(usuario: Usuario) -> Usuario:
    """Bloquea la fila del usuario hasta el fin de la transacción."""
    return Usuario.objects.select_for_update().get(pk=usuario.pk)


def _deja_sin_administradores(usuario: Usuario) -> bool:
    """
    Regla 5: si quitarle el rol o desactivarlo deja cero administradores.

    Bloquea antes las filas de todos los administradores activos. Si solo se
    bloqueara la del usuario, dos administradores que se desactivan uno al
    otro a la vez contarían "quedan dos" cada uno, y el sistema se quedaría
    sin ninguno. Con el bloqueo, el segundo espera y cuenta uno.
    """
    if not (usuario.is_active and usuario.rol.nombre == NombreRol.ADMINISTRADOR):
        return False
    list(
        Usuario.objects.select_for_update()
        .filter(is_active=True, rol__nombre=NombreRol.ADMINISTRADOR)
        .values_list("pk", flat=True)
    )
    return contar_administradores_activos() <= 1


def _auditar(usuario, *, accion, autor, ip, anteriores=None, nuevos=None) -> None:
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_USUARIO,
        entidad_id=usuario.pk,
        accion=accion,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
        ip=ip,
    )


@transaction.atomic
def crear_usuario(
    *, datos: dict, password: str, autor: AbstractBaseUser, ip: str | None
) -> Usuario:
    """
    Crea una cuenta desde la pantalla de Usuarios (spec 026, reglas 2, 3 y 11).

    El correo se guarda en minúsculas y no se repite sin importar mayúsculas.
    La contraseña pasa por los validadores del sistema antes de guardar. La
    cuenta no entra al panel de Django (is_staff en falso).
    """
    email = Usuario.objects.normalize_email(datos["email"])
    if obtener_id_usuario_por_email(email=email) is not None:
        raise UsuarioDuplicado(email=email)
    nuevo = Usuario(
        email=email,
        nombre_completo=datos["nombre_completo"],
        rol=datos["rol"],
        pais=datos.get("pais"),
        telefono=datos.get("telefono", ""),
    )
    _validar_contrasena(password, usuario=nuevo, campo="password")
    usuario = Usuario.objects.create_user(
        email=email,
        password=password,
        nombre_completo=nuevo.nombre_completo,
        rol=nuevo.rol,
        pais=nuevo.pais,
        telefono=nuevo.telefono,
    )
    _auditar(
        usuario,
        accion=AccionAuditoria.CREAR,
        autor=autor,
        ip=ip,
        nuevos={"email": usuario.email, **_valores(usuario, CAMPOS_EDITABLES)},
    )
    return usuario


@transaction.atomic
def actualizar_usuario(
    *, usuario: Usuario, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Usuario:
    """
    Edita nombre, rol, país y teléfono (spec 026). Un cambio de rol revisa las
    reglas 4 a 7: no sobre uno mismo, no a un superusuario, no a quien tiene un
    perfil de agente activo y no al último administrador.
    """
    usuario = _bloquear(usuario)
    anteriores = _valores(usuario, CAMPOS_EDITABLES)
    nuevo_rol = datos.get("rol")
    if nuevo_rol is not None and nuevo_rol.pk != usuario.rol_id:
        if usuario.pk == autor.pk:
            raise OperacionSobreSiMismo(accion="cambiar el rol de")
        if usuario.is_superuser:
            raise SuperusuarioEsAdministrador()
        if tiene_perfil_de_agente_activo(usuario=usuario):
            raise UsuarioConPerfilAgente(accion="cambiar el rol")
        if _deja_sin_administradores(usuario):
            raise UltimoAdministrador()

    for campo in CAMPOS_EDITABLES:
        if campo in datos:
            setattr(usuario, campo, datos[campo])
    nuevos = _valores(usuario, CAMPOS_EDITABLES)
    cambiados = [c for c in CAMPOS_EDITABLES if anteriores[c] != nuevos[c]]
    if not cambiados:
        return usuario
    usuario.save(update_fields=cambiados)
    _auditar(
        usuario,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        anteriores={c: anteriores[c] for c in cambiados},
        nuevos={c: nuevos[c] for c in cambiados},
    )
    return usuario


@transaction.atomic
def desactivar_usuario(
    *, usuario: Usuario, autor: AbstractBaseUser, ip: str | None
) -> Usuario:
    """
    Borrado lógico (spec 026, regla 8). Revisa las reglas 4, 5 y 7. Desde la
    siguiente petición, la autenticación JWT rechaza sus tokens.
    """
    usuario = _bloquear(usuario)
    if not usuario.is_active:
        return usuario
    if usuario.pk == autor.pk:
        raise OperacionSobreSiMismo(accion="desactivar")
    if tiene_perfil_de_agente_activo(usuario=usuario):
        raise UsuarioConPerfilAgente(accion="desactivar el usuario")
    if _deja_sin_administradores(usuario):
        raise UltimoAdministrador()
    usuario.is_active = False
    usuario.save(update_fields=["is_active"])
    _auditar(
        usuario,
        accion=AccionAuditoria.ELIMINAR,
        autor=autor,
        ip=ip,
        anteriores={"activo": True},
        nuevos={"activo": False},
    )
    return usuario


@transaction.atomic
def reactivar_usuario(
    *, usuario: Usuario, autor: AbstractBaseUser, ip: str | None
) -> Usuario:
    """Vuelve a permitir el inicio de sesión de una cuenta desactivada."""
    usuario = _bloquear(usuario)
    if usuario.is_active:
        return usuario
    usuario.is_active = True
    usuario.save(update_fields=["is_active"])
    _auditar(
        usuario,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        anteriores={"activo": False},
        nuevos={"activo": True},
    )
    return usuario


@transaction.atomic
def restablecer_contrasena(
    *, usuario: Usuario, password: str, autor: AbstractBaseUser, ip: str | None
) -> None:
    """
    Un administrador pone una contraseña nueva (spec 026). La bitácora anota
    que se restableció, nunca el valor (regla 10).
    """
    usuario = _bloquear(usuario)
    _validar_contrasena(password, usuario=usuario, campo="password")
    usuario.set_password(password)
    usuario.save(update_fields=["password"])
    _auditar(
        usuario,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        nuevos={"contrasena": "restablecida por un administrador"},
    )


@transaction.atomic
def cambiar_mi_contrasena(
    *, usuario: Usuario, actual: str, nueva: str, ip: str | None
) -> None:
    """
    Cualquier usuario cambia su contraseña dando la actual (spec 026, regla
    9). La sesión abierta sigue: sus tokens no dependen de la contraseña.
    """
    usuario = _bloquear(usuario)
    if not usuario.check_password(actual):
        raise ContrasenaActualIncorrecta()
    _validar_contrasena(nueva, usuario=usuario, campo="nueva")
    usuario.set_password(nueva)
    usuario.save(update_fields=["password"])
    _auditar(
        usuario,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=usuario,
        ip=ip,
        nuevos={"contrasena": "cambiada por el usuario"},
    )
