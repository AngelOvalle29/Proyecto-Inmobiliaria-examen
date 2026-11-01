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
