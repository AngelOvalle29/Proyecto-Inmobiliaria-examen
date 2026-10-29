"""Enumeraciones de ventas: estados, tipos y demás valores fijos."""

from django.db import models


class ModalidadVenta(models.TextChoices):
    """Spec 007, regla 11."""

    CONTADO = "CONTADO", "Contado"
    FINANCIADO = "FINANCIADO", "Financiado"


class EstadoContrato(models.TextChoices):
    """Spec 007, reglas 11, 15 y 18."""

    VIGENTE = "VIGENTE", "Vigente"
    LIQUIDADO = "LIQUIDADO", "Liquidado"
    ANULADO = "ANULADO", "Anulado"


class EstadoCuota(models.TextChoices):
    """
    Spec 007, regla 16. La mora no es un estado: se calcula con la fecha
    (CuotaPago.en_mora, regla 17).
    """

    PENDIENTE = "PENDIENTE", "Pendiente"
    PARCIAL = "PARCIAL", "Pago parcial"
    PAGADA = "PAGADA", "Pagada"
