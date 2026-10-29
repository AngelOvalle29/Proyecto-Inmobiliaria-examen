"""Excepciones de dominio de auditoría.

El manejador global de errores las traduce al formato uniforme.
"""


class RegistroAuditoriaInmutable(Exception):
    """
    Se intentó modificar o borrar un registro de la bitácora.

    No hereda de core.ErrorDominio a propósito, por dos razones. auditoria no
    importa ninguna app (spec 001, §4). Y no es una regla que un usuario
    pueda incumplir desde la API: si ocurre, es un error de programación y
    debe verse como un 500, no como una respuesta de negocio.
    """
