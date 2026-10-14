"""Registro de los modelos de core en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import Ciudad, Moneda, Pais, TipoCambio


class AdminSinBorrado(admin.ModelAdmin):
    """
    Los catálogos no se borran físicamente (spec 001, regla 10): se desactivan
    con el campo activo. Sin permiso de borrado, el panel oculta tanto el botón
    "Eliminar" como la acción masiva "Eliminar seleccionados".
    """

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Moneda)
class MonedaAdmin(AdminSinBorrado):
    list_display = ["codigo", "nombre", "simbolo", "activo"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre"]


@admin.register(Pais)
class PaisAdmin(AdminSinBorrado):
    list_display = ["nombre", "codigo_iso", "moneda_principal", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre", "codigo_iso"]


@admin.register(Ciudad)
class CiudadAdmin(AdminSinBorrado):
    list_display = ["nombre", "pais", "region", "activo"]
    list_filter = ["activo", "pais"]
    search_fields = ["nombre", "region"]
    list_select_related = ["pais"]


@admin.register(TipoCambio)
class TipoCambioAdmin(AdminSinBorrado):
    list_display = ["fecha", "moneda_origen", "moneda_destino", "tasa"]
    list_filter = ["moneda_origen", "moneda_destino"]
    date_hierarchy = "fecha"
    list_select_related = ["moneda_origen", "moneda_destino"]
