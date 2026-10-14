"""Enumeraciones de usuarios: estados, tipos y demás valores fijos."""

from django.db import models


class NombreRol(models.TextChoices):
    """Los cinco roles del sistema (docs/arquitectura.md §9)."""

    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    GERENTE = "GERENTE", "Gerente"
    AGENTE = "AGENTE", "Agente de ventas"
    CONTABILIDAD = "CONTABILIDAD", "Contabilidad"
    CONSULTA = "CONSULTA", "Consulta"
