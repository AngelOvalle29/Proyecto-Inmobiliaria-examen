"""Enumeraciones de catálogo: estados, tipos y demás valores fijos."""

from django.db import models


class EstadoPropiedad(models.TextChoices):
    """
    Ciclo de vida de una propiedad o de una unidad (docs/modelo-datos.md §2).

    Solo cambia con el servicio cambiar_estado_propiedad (spec 003, regla 7).
    Las reglas de qué estado puede seguir a cuál las define cada spec que causa
    el cambio: ventas, arrendamientos, compras y construcción.
    """

    EN_NEGOCIACION = "EN_NEGOCIACION", "En negociación"
    ADQUIRIDA = "ADQUIRIDA", "Adquirida"
    EN_CONSTRUCCION = "EN_CONSTRUCCION", "En construcción"
    DISPONIBLE = "DISPONIBLE", "Disponible"
    RESERVADA = "RESERVADA", "Reservada"
    VENDIDA = "VENDIDA", "Vendida"
    ARRENDADA = "ARRENDADA", "Arrendada"
    BAJA = "BAJA", "Baja"


class TipoDocumento(models.TextChoices):
    """Clases de documento oficial que se adjuntan a una propiedad (spec 011)."""

    ESCRITURA = "ESCRITURA", "Escritura"
    LICENCIA = "LICENCIA", "Licencia"
    PLANO = "PLANO", "Plano"
    CERTIFICACION = "CERTIFICACION", "Certificación"
    AVALUO = "AVALUO", "Avalúo"
    CONTRATO = "CONTRATO", "Contrato"
    OTRO = "OTRO", "Otro"
