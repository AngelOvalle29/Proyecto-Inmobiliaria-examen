"""Enumeraciones de construcción: estados, tipos y demás valores fijos."""

from django.db import models


class EstadoProyecto(models.TextChoices):
    """Ciclo de vida de un proyecto de construcción (spec 017, reglas 9 a 16)."""

    PLANIFICADO = "PLANIFICADO", "Planificado"
    EN_EJECUCION = "EN_EJECUCION", "En ejecución"
    SUSPENDIDO = "SUSPENDIDO", "Suspendido"
    FINALIZADO = "FINALIZADO", "Finalizado"
    CANCELADO = "CANCELADO", "Cancelado"


# Regla 10: un proyecto "activo" es el que todavía puede avanzar. Una propiedad
# tiene como máximo uno, y una constructora con alguno no se desactiva (regla 23).
ESTADOS_ACTIVOS = [
    EstadoProyecto.PLANIFICADO,
    EstadoProyecto.EN_EJECUCION,
    EstadoProyecto.SUSPENDIDO,
]
