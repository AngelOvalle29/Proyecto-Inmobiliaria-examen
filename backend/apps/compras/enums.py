"""Enumeraciones de compras: estados, tipos y demás valores fijos."""

from django.db import models


class TipoProveedor(models.TextChoices):
    """Quién le vende la propiedad a la agencia (spec 006, regla 1)."""

    PROPIETARIO_PARTICULAR = "PROPIETARIO_PARTICULAR", "Propietario particular"
    INMOBILIARIA = "INMOBILIARIA", "Inmobiliaria"
    BANCO = "BANCO", "Banco"
    GOBIERNO = "GOBIERNO", "Gobierno"
    OTRO = "OTRO", "Otro"


class EstadoContratoCompra(models.TextChoices):
    """Ciclo de vida de un contrato de compra (spec 017, reglas 1, 6 y 7)."""

    EN_PROCESO = "EN_PROCESO", "En proceso"
    COMPLETADO = "COMPLETADO", "Completado"
    ANULADO = "ANULADO", "Anulado"
