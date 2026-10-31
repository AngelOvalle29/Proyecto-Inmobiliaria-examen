"""Enumeraciones de arrendamientos: estados, tipos y demás valores fijos."""

from django.db import models


class EstadoArrendamiento(models.TextChoices):
    """Spec 008, reglas 9 a 11."""

    VIGENTE = "VIGENTE", "Vigente"
    VENCIDO = "VENCIDO", "Vencido"
    RESCINDIDO = "RESCINDIDO", "Rescindido"
    RENOVADO = "RENOVADO", "Renovado"


class EstadoPagoRenta(models.TextChoices):
    """
    Spec 008, reglas 6 y 10. La mora no es un estado: se calcula con la fecha
    (PagoRenta.en_mora, regla 8).
    """

    PENDIENTE = "PENDIENTE", "Pendiente"
    PAGADO = "PAGADO", "Pagado"
    CANCELADO = "CANCELADO", "Cancelado"
