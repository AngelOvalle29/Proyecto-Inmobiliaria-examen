"""Registro de los modelos de catálogo en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import Propiedad, TipoPropiedad, Unidad


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
