"""Excepciones de dominio de core.

El manejador global de errores las traduce al formato uniforme.
"""

from datetime import date


class ErrorDominio(Exception):
    """
    Base de toda excepción que representa una regla de negocio incumplida.

    Las excepciones de cada app heredan de esta y fijan su codigo y su
    estado_http. El manejador global (spec 001, §5) las convierte en la
    respuesta de error uniforme, así que servicios y selectores solo lanzan
    la excepción y nunca arman respuestas HTTP.
    """

    codigo = "ERROR_DOMINIO"
    estado_http = 400

    def __init__(self, mensaje: str, detalles: dict | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or {}


class TipoCambioNoDisponible(ErrorDominio):
    """No hay ninguna tasa registrada en la fecha pedida ni en fechas anteriores."""

    codigo = "TIPO_CAMBIO_NO_DISPONIBLE"
    # 422: la petición está bien formada, pero no se puede procesar con los
    # datos que hay.
    estado_http = 422

    def __init__(self, *, origen: str, destino: str, fecha: date) -> None:
        super().__init__(
            f"No hay tipo de cambio de {origen} a {destino} vigente al "
            f"{fecha:%d/%m/%Y}.",
            detalles={
                "moneda_origen": origen,
                "moneda_destino": destino,
                "fecha": fecha.isoformat(),
            },
        )
