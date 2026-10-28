"""Enumeraciones de CRM: estados, tipos y demás valores fijos."""

from django.db import models


class TipoCliente(models.TextChoices):
    """Regla 6 de la spec 004: cada tipo exige datos distintos."""

    PERSONA = "PERSONA", "Persona"
    EMPRESA = "EMPRESA", "Empresa"
