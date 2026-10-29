"""Excepciones de dominio de catálogo.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class TipoSinUnidades(ErrorDominio):
    """Regla 2: solo los tipos que requieren unidades las admiten."""

    codigo = "TIPO_SIN_UNIDADES"
    estado_http = 409

    def __init__(self, *, tipo: str) -> None:
        super().__init__(
            f"Las propiedades de tipo {tipo} no admiten unidades.",
            detalles={"tipo": tipo},
        )


class UnidadDuplicada(ErrorDominio):
    """Regla 3: el código de una unidad es único dentro de su propiedad."""

    codigo = "UNIDAD_DUPLICADA"
    estado_http = 409

    def __init__(self, *, propiedad: str, unidad: str) -> None:
        super().__init__(
            f"La propiedad {propiedad} ya tiene una unidad {unidad}.",
            detalles={"propiedad": propiedad, "unidad": unidad},
        )


class PropiedadConUnidades(ErrorDominio):
    """Regla 6: una propiedad con unidades activas no se desactiva."""

    codigo = "PROPIEDAD_CON_UNIDADES"
    estado_http = 409

    def __init__(self, *, propiedad: str, unidades_activas: int) -> None:
        super().__init__(
            f"La propiedad {propiedad} tiene {unidades_activas} unidades activas: "
            "desactívelas primero.",
            detalles={"propiedad": propiedad, "unidades_activas": unidades_activas},
        )
