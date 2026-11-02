"""Enumeraciones de auditoría: estados, tipos y demás valores fijos."""

from django.db import models


class AccionAuditoria(models.TextChoices):
    """Qué se hizo sobre la entidad (docs/arquitectura.md §5)."""

    CREAR = "CREAR", "Crear"
    ACTUALIZAR = "ACTUALIZAR", "Actualizar"
    ELIMINAR = "ELIMINAR", "Eliminar"
    APROBAR = "APROBAR", "Aprobar"
    ANULAR = "ANULAR", "Anular"
    INICIAR_SESION = "INICIAR_SESION", "Iniciar sesión"
    LOGIN_FALLIDO = "LOGIN_FALLIDO", "Inicio de sesión fallido"


class ModoAgente(models.TextChoices):
    """Contexto de una consulta; no habilita por sí mismo el modo interno."""

    PUBLICO = "PUBLICO", "Público"
    INTERNO = "INTERNO", "Interno"
