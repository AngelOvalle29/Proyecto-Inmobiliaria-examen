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
