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
