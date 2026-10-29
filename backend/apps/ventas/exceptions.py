"""Excepciones de dominio de ventas (spec 007, §5).

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class CotizacionNoAprobada(ErrorDominio):
    """Regla 8: un contrato solo nace de una cotización aprobada."""

    codigo = "COTIZACION_NO_APROBADA"
    estado_http = 409

    def __init__(self, *, cotizacion: str, estado: str) -> None:
        super().__init__(
            f"La cotización {cotizacion} está {estado}: solo se firma una aprobada.",
            detalles={"cotizacion": cotizacion, "estado": estado},
        )


class ContratoNoVigente(ErrorDominio):
    """Reglas 15 y 16: se anula o se paga solo un contrato vigente."""

    codigo = "CONTRATO_NO_VIGENTE"
    estado_http = 409

    def __init__(self, *, contrato: str, estado: str) -> None:
        super().__init__(
            f"El contrato {contrato} está {estado}.",
            detalles={"contrato": contrato, "estado": estado},
        )


class ContratoConPagos(ErrorDominio):
    """Regla 15: con pagos registrados no se anula (habría que devolver)."""

    codigo = "CONTRATO_CON_PAGOS"
    estado_http = 409

    def __init__(self, *, contrato: str) -> None:
        super().__init__(
            f"El contrato {contrato} ya tiene pagos registrados y no se puede anular.",
            detalles={"contrato": contrato},
        )


class PagoExcedeSaldo(ErrorDominio):
    """Regla 16: un pago no puede superar lo que falta de la cuota."""

    codigo = "PAGO_EXCEDE_SALDO"
    estado_http = 400

    def __init__(self, *, cuota: int, saldo, monto) -> None:
        super().__init__(
            f"El pago de {monto} supera lo que falta de la cuota {cuota}: {saldo}.",
            detalles={"cuota": cuota, "saldo": str(saldo), "monto": str(monto)},
        )


class EngancheFueraDeRango(ErrorDominio):
    """
    Regla 11: el enganche va de 0 al monto total, sin incluirlo. Se responde
    como un error de validación del campo, igual que los del serializador.
    """

    codigo = "VALIDACION"
    estado_http = 400

    def __init__(self) -> None:
        super().__init__(
            "Los datos enviados no son válidos.",
            detalles={"enganche": ["Debe ser 0 o más y menor que el monto total."]},
        )
