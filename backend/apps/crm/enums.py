"""Enumeraciones de CRM: estados, tipos y demás valores fijos."""

from django.db import models


class TipoCliente(models.TextChoices):
    """Regla 6 de la spec 004: cada tipo exige datos distintos."""

    PERSONA = "PERSONA", "Persona"
    EMPRESA = "EMPRESA", "Empresa"


class EstadoCotizacion(models.TextChoices):
    """
    Spec 007, regla 4. Vencida no es un estado: se calcula con la fecha
    (Cotizacion.esta_vencida).
    """

    BORRADOR = "BORRADOR", "Borrador"
    ENVIADA = "ENVIADA", "Enviada"
    APROBADA = "APROBADA", "Aprobada"
    RECHAZADA = "RECHAZADA", "Rechazada"
