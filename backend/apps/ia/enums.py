"""Enumeraciones de IA: estados, tipos y demás valores fijos."""

from django.db import models


class TipoDocumentoRAG(models.TextChoices):
    POLITICA = "POLITICA", "Política de la agencia"
    MANUAL = "MANUAL", "Manual de procesos"
    LEGAL = "LEGAL", "Requisito legal"
    PLANTILLA = "PLANTILLA", "Plantilla"
    FICHA_PROPIEDAD = "FICHA_PROPIEDAD", "Ficha de propiedad"
