"""Registro de los modelos de catálogo en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import Avaluo, DocumentoOficial, Propiedad, TipoPropiedad, Unidad


class AdminSoloLectura(admin.ModelAdmin):
    """
    El panel solo consulta las entidades de catálogo. Se escriben por la API,
    que pasa por los servicios y deja registro en la bitácora (CLAUDE.md §8).
    Si el panel pudiera editarlas, esas escrituras no quedarían auditadas.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TipoPropiedad)
class TipoPropiedadAdmin(AdminSoloLectura):
    list_display = ["nombre", "requiere_unidades", "activo"]


@admin.register(Propiedad)
class PropiedadAdmin(AdminSoloLectura):
    list_display = [
        "codigo",
        "nombre",
        "tipo",
        "ciudad",
        "estado",
        "precio_lista",
        "moneda",
        "activo",
    ]
    list_filter = ["estado", "tipo", "es_publica", "activo"]
    search_fields = ["codigo", "nombre", "direccion"]
    list_select_related = ["tipo", "ciudad", "moneda"]


@admin.register(Unidad)
class UnidadAdmin(AdminSoloLectura):
    list_display = [
        "propiedad",
        "codigo",
        "nivel",
        "estado",
        "precio_lista",
        "moneda",
        "activo",
    ]
    list_filter = ["estado", "activo"]
    list_select_related = ["propiedad", "moneda"]


@admin.register(DocumentoOficial)
class DocumentoOficialAdmin(AdminSoloLectura):
    list_display = [
        "propiedad",
        "tipo",
        "nombre",
        "fecha_emision",
        "fecha_vencimiento",
        "activo",
    ]
    list_filter = ["tipo", "activo"]
    search_fields = ["nombre", "emisor", "propiedad__codigo"]
    list_select_related = ["propiedad"]


@admin.register(Avaluo)
class AvaluoAdmin(AdminSoloLectura):
    list_display = ["propiedad", "fecha", "valor", "moneda", "perito", "activo"]
    list_filter = ["moneda", "activo"]
    search_fields = ["perito", "propiedad__codigo"]
    list_select_related = ["propiedad", "moneda"]
