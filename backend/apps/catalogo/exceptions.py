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


class PropiedadNoDisponible(ErrorDominio):
    """
    La propiedad o unidad no está en el estado que la operación exige, por
    ejemplo aprobar una cotización sobre una propiedad ya reservada (spec 007,
    regla 5). Lo lanza cambiar_estado_* cuando recibe estado_requerido.
    """

    codigo = "PROPIEDAD_NO_DISPONIBLE"
    estado_http = 409

    def __init__(
        self, *, codigo: str, estado_actual: str, estado_requerido: str
    ) -> None:
        super().__init__(
            f"{codigo} está {estado_actual} y la operación exige {estado_requerido}.",
            detalles={
                "propiedad": codigo,
                "estado_actual": estado_actual,
                "estado_requerido": estado_requerido,
            },
        )


class FechaAvaluoFutura(ErrorDominio):
    """
    Regla 2 de la spec 011: un avalúo no puede tener fecha futura.

    Se responde como un error de validación del campo, igual que
    EngancheFueraDeRango en ventas, para no inventar un código fuera del
    contrato de la API.
    """

    codigo = "VALIDACION"
    estado_http = 400

    def __init__(self) -> None:
        super().__init__(
            "Los datos enviados no son válidos.",
            detalles={"fecha": ["No puede ser futura."]},
        )


class DocumentoDeOtraPropiedad(ErrorDominio):
    """Regla 4 de la spec 011: el documento debe ser de la misma propiedad."""

    codigo = "DOCUMENTO_DE_OTRA_PROPIEDAD"
    estado_http = 409

    def __init__(
        self, *, documento: str, propiedad: str, propiedad_documento: str
    ) -> None:
        super().__init__(
            f"El documento {documento} pertenece a la propiedad "
            f"{propiedad_documento}, no a {propiedad}.",
            detalles={
                "documento": documento,
                "propiedad": propiedad,
                "propiedad_documento": propiedad_documento,
            },
        )


class ArchivoNoPermitido(ErrorDominio):
    """
    Regla 6 de la spec 011 (PDF, JPG o PNG de hasta 10 MB) y regla 1 de la 019
    (JPG o PNG de hasta 5 MB): el archivo no es de un tipo aceptado o pesa más.
    """

    codigo = "ARCHIVO_NO_PERMITIDO"
    estado_http = 400

    def __init__(self, *, motivo: str) -> None:
        super().__init__(motivo, detalles={"archivo": [motivo]})


class DocumentoEnUso(ErrorDominio):
    """Regla 9 de la spec 011: un documento que respalda un avalúo activo."""

    codigo = "DOCUMENTO_EN_USO"
    estado_http = 409

    def __init__(self, *, documento: str) -> None:
        super().__init__(
            f"El documento {documento} respalda un avalúo activo: "
            "desactive el avalúo primero.",
            detalles={"documento": documento},
        )


class LimiteImagenes(ErrorDominio):
    """Regla 2 de la spec 019: hasta 10 imágenes activas por propiedad."""

    codigo = "LIMITE_IMAGENES"
    estado_http = 409

    def __init__(self, *, propiedad: str, maximo: int) -> None:
        super().__init__(
            f"La propiedad {propiedad} ya tiene {maximo} imágenes: "
            "desactive una para subir otra.",
            detalles={"propiedad": propiedad, "maximo": maximo},
        )
