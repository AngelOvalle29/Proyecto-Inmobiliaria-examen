"""Excepciones de dominio de usuarios.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class CredencialesInvalidas(ErrorDominio):
    """
    Correo o contraseña incorrectos, o usuario desactivado.

    Los tres casos dan el mismo mensaje a propósito: si se distinguiera
    "el correo no existe" de "la contraseña es incorrecta", cualquiera podría
    averiguar qué correos tienen cuenta en el sistema.
    """

    codigo = "CREDENCIALES_INVALIDAS"
    estado_http = 401

    def __init__(self) -> None:
        super().__init__("Correo o contraseña incorrectos.")


class UsuarioDuplicado(ErrorDominio):
    """Spec 026, regla 2: ya hay una cuenta con ese correo."""

    codigo = "USUARIO_DUPLICADO"
    estado_http = 409

    def __init__(self, *, email: str) -> None:
        super().__init__(
            f"Ya existe una cuenta con el correo {email}.", detalles={"email": email}
        )


class ContrasenaInvalida(ErrorDominio):
    """Spec 026, regla 3: la contraseña no cumple los validadores."""

    codigo = "CONTRASENA_INVALIDA"
    estado_http = 400

    def __init__(self, *, motivos: list[str], campo: str = "password") -> None:
        super().__init__(" ".join(motivos), detalles={campo: motivos})


class ContrasenaActualIncorrecta(ErrorDominio):
    """Spec 026, regla 9: cambiar la propia contraseña exige la actual."""

    codigo = "CONTRASENA_ACTUAL_INCORRECTA"
    estado_http = 400

    def __init__(self) -> None:
        mensaje = "La contraseña actual no es correcta."
        super().__init__(mensaje, detalles={"actual": [mensaje]})


class OperacionSobreSiMismo(ErrorDominio):
    """Spec 026, regla 4: nadie se desactiva ni se cambia el rol a sí mismo."""

    codigo = "OPERACION_SOBRE_SI_MISMO"
    estado_http = 409

    def __init__(self, *, accion: str) -> None:
        super().__init__(f"No puede {accion} su propia cuenta.")


class UltimoAdministrador(ErrorDominio):
    """Spec 026, regla 5: siempre queda al menos un administrador activo."""

    codigo = "ULTIMO_ADMINISTRADOR"
    estado_http = 409

    def __init__(self) -> None:
        super().__init__(
            "Es el único administrador activo: el sistema se quedaría sin "
            "nadie que pueda gestionar usuarios."
        )


class SuperusuarioEsAdministrador(ErrorDominio):
    """Spec 026, regla 6 (spec 001, regla 3)."""

    codigo = "SUPERUSUARIO_ES_ADMINISTRADOR"
    estado_http = 409

    def __init__(self) -> None:
        super().__init__("Un superusuario siempre tiene el rol ADMINISTRADOR.")


class UsuarioConPerfilAgente(ErrorDominio):
    """Spec 026, regla 7: primero se desactiva el agente en CRM."""

    codigo = "USUARIO_CON_PERFIL_AGENTE"
    estado_http = 409

    def __init__(self, *, accion: str) -> None:
        super().__init__(
            f"No se puede {accion}: el usuario tiene un perfil de agente "
            "activo. Desactive primero el agente en CRM."
        )
