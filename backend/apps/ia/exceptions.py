"""Excepciones de dominio de IA.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class DocumentoRAGDuplicado(ErrorDominio):
    """Ya existe un documento con ese título (el título es único)."""

    codigo = "DOCUMENTO_RAG_DUPLICADO"
    estado_http = 409

    def __init__(self, titulo: str) -> None:
        super().__init__(
            f"Ya existe un documento con el título «{titulo}».",
            detalles={"titulo": titulo},
        )


class EmbeddingConDimensionIncorrecta(Exception):
    """El proveedor devolvió vectores de otro tamaño que el campo de la base.

    No hereda de ErrorDominio porque no es una regla de negocio que incumpla
    el usuario: es un error de configuración (IA_DIMENSION_EMBEDDINGS no
    coincide con el campo vector). Debe verse como error y detener la
    indexación antes de guardar nada.
    """


class DocumentoModificadoDuranteIndexacion(Exception):
    """El texto del documento cambió mientras se generaban sus vectores.

    Los vectores que llegaron son del texto anterior: guardarlos dejaría el
    documento marcado como indexado con fragmentos viejos (revisión del PR #62).
    No se guarda nada; el documento queda pendiente y se indexa de nuevo con su
    texto actual (la tarea de la cola reintenta, y cargar_demo_ia lo toma en la
    siguiente corrida).
    """


class AgenteNoDisponible(ErrorDominio):
    """Gemini no respondió tras los reintentos, o falta la llave (regla 9).

    Se responde 503 y no 500: no es un error del programa, es un servicio
    externo caído, y el usuario puede volver a intentar en un momento.
    """

    codigo = "AGENTE_NO_DISPONIBLE"
    estado_http = 503

    def __init__(self) -> None:
        super().__init__(
            "El asistente no está disponible en este momento. "
            "Intenta de nuevo en unos minutos."
        )


class ArchivoRAGNoPermitido(ErrorDominio):
    """El archivo subido no es Markdown UTF-8 o pasa de 200 KB (spec 020, regla 1).

    Mismo código que la del catálogo (spec 011), pero propia de ia: importar la
    de catalogo crearía una dependencia ia → catalogo que no existe.
    """

    codigo = "ARCHIVO_NO_PERMITIDO"
    estado_http = 400

    def __init__(self, *, motivo: str) -> None:
        super().__init__(motivo, detalles={"archivo": [motivo]})
