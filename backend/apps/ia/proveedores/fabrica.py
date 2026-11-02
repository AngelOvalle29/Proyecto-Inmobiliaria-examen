"""Elige la implementación de ProveedorIA según IA_PROVEEDOR."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import ProveedorIA, ProveedorIANoDisponible
from .gemini import ProveedorGemini


def obtener_proveedor() -> ProveedorIA:
    if settings.IA_PROVEEDOR != "gemini":
        raise ImproperlyConfigured(
            f"IA_PROVEEDOR desconocido: {settings.IA_PROVEEDOR!r}. "
            "El único disponible es 'gemini'."
        )
    if not settings.IA_API_KEY:
        # Sin llave el agente no funciona, pero el resto del sistema sí: se
        # avisa con el mismo error que una caída de Gemini (503, no 500).
        raise ProveedorIANoDisponible("IA_API_KEY no está configurada.")

    return ProveedorGemini(
        api_key=settings.IA_API_KEY,
        modelo=settings.IA_MODELO,
        modelo_embeddings=settings.IA_MODELO_EMBEDDINGS,
        dimension_embeddings=settings.IA_DIMENSION_EMBEDDINGS,
        max_tokens_respuesta=settings.IA_MAX_TOKENS_RESPUESTA,
    )
