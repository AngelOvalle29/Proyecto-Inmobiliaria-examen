"""Enumeraciones de IA: estados, tipos y demás valores fijos."""

from django.db import models


class TipoDocumentoRAG(models.TextChoices):
    POLITICA = "POLITICA", "Política de la agencia"
    MANUAL = "MANUAL", "Manual de procesos"
    LEGAL = "LEGAL", "Requisito legal"
    PLANTILLA = "PLANTILLA", "Plantilla"
    FICHA_PROPIEDAD = "FICHA_PROPIEDAD", "Ficha de propiedad"


class EstadoIndexacion(models.TextChoices):
    """Spec 020, regla 11. PENDIENTE: su versión actual todavía no se indexó."""

    PENDIENTE = "PENDIENTE", "Pendiente"
    INDEXADO = "INDEXADO", "Indexado"
    ERROR = "ERROR", "Error"
