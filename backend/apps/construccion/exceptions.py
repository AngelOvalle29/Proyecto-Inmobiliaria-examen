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


class PropiedadConProyecto(ErrorDominio):
    """Una propiedad tiene como máximo un proyecto activo (spec 017, regla 10)."""

    codigo = "PROPIEDAD_CON_PROYECTO"
    estado_http = 409

    def __init__(self, *, propiedad: str) -> None:
        super().__init__(
            f"La propiedad {propiedad} ya tiene un proyecto de construcción activo.",
            detalles={"propiedad": propiedad},
        )


class TransicionInvalida(ErrorDominio):
    """
    La acción no es posible en el estado actual del proyecto: iniciar uno que
    ya empezó, reanudar uno que no está suspendido, editar uno cancelado
    (spec 017, reglas 12 a 17).
    """

    codigo = "TRANSICION_INVALIDA"
    estado_http = 409

    def __init__(self, *, codigo: str, estado: str, accion: str) -> None:
        super().__init__(
            f"{codigo} está {estado}: no se puede {accion}.",
            detalles={"codigo": codigo, "estado": estado, "accion": accion},
        )


class AvanceInvalido(ErrorDominio):
    """
    El avance baja, pasa de 100, o se finaliza sin llegar a 100 (spec 017,
    reglas 13 y 15).
    """

    codigo = "AVANCE_INVALIDO"
    estado_http = 400

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, detalles={"porcentaje": [mensaje]})


class FechaInvalida(ErrorDominio):
    """La fecha de fin estimada es anterior a la de inicio (spec 017, regla 11)."""

    codigo = "FECHA_INVALIDA"
    estado_http = 400

    def __init__(self, *, campo: str, mensaje: str) -> None:
        # Por campo, para que el formulario lo muestre junto a él.
        super().__init__(mensaje, detalles={campo: [mensaje]})


class ConstructoraConProyectos(ErrorDominio):
    """Una constructora con un proyecto activo no se desactiva (spec 017, regla 23)."""

    codigo = "CONSTRUCTORA_CON_PROYECTOS"
    estado_http = 409

    def __init__(self, *, constructora: str) -> None:
        super().__init__(
            f"La constructora {constructora} tiene proyectos activos: "
            "finalícelos o cancélelos antes de desactivarla.",
            detalles={"constructora": constructora},
        )
