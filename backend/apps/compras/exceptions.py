"""Excepciones de dominio de compras.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class ProveedorDuplicado(ErrorDominio):
    """Ya hay un proveedor con ese NIT en ese país (spec 006, regla 3)."""

    codigo = "PROVEEDOR_DUPLICADO"
    estado_http = 409

    def __init__(self, *, nit: str, pais: str) -> None:
        super().__init__(
            f"Ya existe un proveedor con el NIT {nit} en {pais}.",
            detalles={"nit": nit, "pais": pais},
        )


class NitObligatorio(ErrorDominio):
    """Solo el propietario particular puede registrarse sin NIT (regla 2)."""

    codigo = "NIT_OBLIGATORIO"
    estado_http = 400

    def __init__(self) -> None:
        super().__init__(
            "El NIT es obligatorio para este tipo de proveedor.",
            detalles={"nit": ["El NIT es obligatorio para este tipo de proveedor."]},
        )


class PropiedadConContrato(ErrorDominio):
    """Una propiedad tiene como máximo un contrato no anulado (spec 017, regla 2)."""

    codigo = "PROPIEDAD_CON_CONTRATO"
    estado_http = 409

    def __init__(self, *, propiedad: str) -> None:
        super().__init__(
            f"La propiedad {propiedad} ya tiene un contrato de compra sin anular.",
            detalles={"propiedad": propiedad},
        )


class TransicionInvalida(ErrorDominio):
    """
    La acción no es posible en el estado actual del contrato: completar o
    anular uno que ya no está EN_PROCESO (spec 017, reglas 6 y 7).
    """

    codigo = "TRANSICION_INVALIDA"
    estado_http = 409

    def __init__(self, *, codigo: str, estado: str, accion: str) -> None:
        super().__init__(
            f"{codigo} está {estado}: no se puede {accion}.",
            detalles={"codigo": codigo, "estado": estado, "accion": accion},
        )


class FechaInvalida(ErrorDominio):
    """La fecha de compra no puede ser futura (spec 017, regla 4)."""

    codigo = "FECHA_INVALIDA"
    estado_http = 400

    def __init__(self, *, campo: str, mensaje: str) -> None:
        # detalles por campo, como NitObligatorio: el formulario muestra el
        # error junto al campo (spec 010, regla 8).
        super().__init__(mensaje, detalles={campo: [mensaje]})


class ProveedorConContratos(ErrorDominio):
    """Un proveedor con un contrato EN_PROCESO no se desactiva (spec 017, regla 22)."""

    codigo = "PROVEEDOR_CON_CONTRATOS"
    estado_http = 409

    def __init__(self, *, proveedor: str) -> None:
        super().__init__(
            f"El proveedor {proveedor} tiene contratos de compra en proceso: "
            "complételos o anúlelos antes de desactivarlo.",
            detalles={"proveedor": proveedor},
        )
