"""Excepciones de dominio de construcción.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class ConstructoraDuplicada(ErrorDominio):
    """Ya hay una constructora con ese NIT en ese país (spec 006, regla 5)."""

    codigo = "CONSTRUCTORA_DUPLICADA"
    estado_http = 409

    def __init__(self, *, nit: str, pais: str) -> None:
        super().__init__(
            f"Ya existe una constructora con el NIT {nit} en {pais}.",
            detalles={"nit": nit, "pais": pais},
        )


class NitObligatorio(ErrorDominio):
    """Una constructora siempre es una empresa y siempre tiene NIT (regla 4).

    Llega aquí cuando el NIT enviado queda vacío al normalizarlo ("-").
    """

    codigo = "NIT_OBLIGATORIO"
    estado_http = 400

    def __init__(self) -> None:
        super().__init__(
            "El NIT de la constructora es obligatorio.",
            detalles={"nit": ["El NIT de la constructora es obligatorio."]},
        )
