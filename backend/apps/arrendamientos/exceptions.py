"""Excepciones de dominio de arrendamientos (spec 008, §5).

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class SeArriendaPorUnidades(ErrorDominio):
    """Regla 1: un edificio no se arrienda completo, sino por unidades."""

    codigo = "PROPIEDAD_CON_UNIDADES"
    estado_http = 409

    def __init__(self, *, propiedad: str) -> None:
        super().__init__(
            f"{propiedad} se arrienda por unidades: elija una de ellas.",
            detalles={"propiedad": propiedad},
        )


class ArrendamientoNoVigente(ErrorDominio):
    """Reglas 10 y 11: se rescinde o finaliza solo un contrato vigente."""

    codigo = "CONTRATO_NO_VIGENTE"
    estado_http = 409

    def __init__(self, *, contrato: str, estado: str) -> None:
        super().__init__(
            f"El contrato {contrato} está {estado}.",
            detalles={"contrato": contrato, "estado": estado},
        )


class ContratoNoTerminado(ErrorDominio):
    """Regla 11: se finaliza un contrato cuya fecha de fin ya pasó."""

    codigo = "CONTRATO_NO_TERMINADO"
    estado_http = 409

    def __init__(self, *, contrato: str, fecha_fin) -> None:
        super().__init__(
            f"El contrato {contrato} termina el {fecha_fin:%d/%m/%Y}: todavía "
            "no se puede finalizar.",
            detalles={"contrato": contrato, "fecha_fin": fecha_fin.isoformat()},
        )


class ContratoYaRenovado(ErrorDominio):
    """Regla 9: se renueva un contrato vigente, una sola vez."""

    codigo = "CONTRATO_YA_RENOVADO"
    estado_http = 409

    def __init__(self, *, contrato: str, estado: str) -> None:
        super().__init__(
            f"El contrato {contrato} está {estado}: solo se renueva uno vigente.",
            detalles={"contrato": contrato, "estado": estado},
        )


class FechaRescisionInvalida(ErrorDominio):
    """Regla 10: la rescisión registra algo que ya pasó."""

    codigo = "FECHA_RESCISION_INVALIDA"
    estado_http = 400

    def __init__(self, *, fecha, desde, hasta) -> None:
        super().__init__(
            f"La fecha de rescisión ({fecha:%d/%m/%Y}) debe estar entre el "
            f"{desde:%d/%m/%Y} y hoy ({hasta:%d/%m/%Y}).",
            detalles={
                "fecha_rescision": fecha.isoformat(),
                "desde": desde.isoformat(),
                "hasta": hasta.isoformat(),
            },
        )


class PagoNoPendiente(ErrorDominio):
    """Regla 6: un pago de renta se registra una sola vez."""

    codigo = "PAGO_NO_PENDIENTE"
    estado_http = 409

    def __init__(self, *, estado: str) -> None:
        super().__init__(
            f"Este pago de renta está {estado}.", detalles={"estado": estado}
        )


class MontoIncorrecto(ErrorDominio):
    """
    Regla 7: el monto recibido debe ser la renta más el recargo. Se dice el
    esperado para que quien registra vea el error de digitación.
    """

    codigo = "MONTO_INCORRECTO"
    estado_http = 400

    def __init__(self, *, recibido, renta, recargo) -> None:
        super().__init__(
            f"El monto debe ser {renta + recargo}: renta {renta} más recargo "
            f"{recargo}.",
            detalles={
                "recibido": str(recibido),
                "esperado": str(renta + recargo),
                "renta": str(renta),
                "recargo": str(recargo),
            },
        )


class FechaPagoRentaInvalida(ErrorDominio):
    """
    Una fecha de pago futura aplicaría como vigente una tasa al dólar que
    todavía no lo es (mismo criterio que la regla 16 de la spec 007).
    """

    codigo = "FECHA_PAGO_INVALIDA"
    estado_http = 400

    def __init__(self, *, fecha, hoy) -> None:
        super().__init__(
            f"La fecha del pago ({fecha:%d/%m/%Y}) no puede ser posterior a hoy.",
            detalles={"fecha": fecha.isoformat(), "hoy": hoy.isoformat()},
        )
