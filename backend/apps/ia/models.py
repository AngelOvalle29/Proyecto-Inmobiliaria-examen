"""Modelos de IA: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.core.models import ModeloBase

from .enums import TipoDocumentoRAG

# Tamaño de los vectores guardados. Fijo aquí y no leído de los settings:
# cambiarlo exige una migración y reindexar todo (spec 005, §10). El servicio
# de indexación comprueba que el proveedor devuelva exactamente este tamaño.
DIMENSION_EMBEDDINGS = 768


class DocumentoRAG(ModeloBase):
    """Un documento de la agencia que el agente puede consultar (spec 005, §4).

    Guarda el Markdown completo en contenido_fuente: así se puede reindexar
    sin depender de dónde se almacenen los archivos en producción.
    """

    titulo = models.CharField(max_length=200, unique=True)
    tipo = models.CharField(max_length=20, choices=TipoDocumentoRAG.choices)
    # Vacío si el documento aplica a todos los países.
    pais = models.ForeignKey(
        "core.Pais",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos_rag",
    )
    contenido_fuente = models.TextField()
    # Sube cada vez que cambia el contenido; la auditoría guarda el cambio.
    version = models.PositiveIntegerField(default=1)
    # Nulo hasta la primera indexación.
    fecha_indexacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ia_documento_rag"
        ordering = ["titulo"]
        verbose_name = "documento del agente"
        verbose_name_plural = "documentos del agente"

    def __str__(self) -> str:
        return self.titulo


class FragmentoRAG(models.Model):
    """Un pedazo de un documento con su vector (spec 005, §4).

    No hereda ModeloBase: es un dato derivado que se regenera desde el
    documento, no lo edita ninguna persona y no se borra lógicamente. Por eso
    se borra en cascada con su documento y se reemplaza al reindexar.
    """

    documento = models.ForeignKey(
        DocumentoRAG, on_delete=models.CASCADE, related_name="fragmentos"
    )
    orden = models.PositiveIntegerField()
    # Texto del encabezado ## al que pertenece; es lo que se cita.
    seccion = models.CharField(max_length=255)
    contenido = models.TextField()
    # Estimado (caracteres / 4): sirve para medir cuánto texto se le envía al
    # modelo, no para cobrar.
    tokens = models.PositiveIntegerField()
    embedding = VectorField(dimensions=DIMENSION_EMBEDDINGS)

    class Meta:
        db_table = "ia_fragmento_rag"
        ordering = ["documento", "orden"]
        verbose_name = "fragmento de documento"
        verbose_name_plural = "fragmentos de documentos"
        constraints = [
            models.UniqueConstraint(
                fields=["documento", "orden"], name="ia_fragmento_orden_unico"
            ),
        ]
        indexes = [
            # HNSW y no IVFFlat: se puede crear con la tabla vacía y no necesita
            # datos para entrenarse. vector_cosine_ops porque la búsqueda usa
            # distancia de coseno (spec 005, §10).
            HnswIndex(
                name="ia_fragmento_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.documento} · {self.seccion} ({self.orden})"
