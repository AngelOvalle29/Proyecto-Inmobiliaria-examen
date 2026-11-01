"""Registro de los modelos de compras en el panel de Django.

Sin reglas de negocio. El panel sirve para consultar y para reactivar un
proveedor desactivado (spec 006, §2); el código no se edita nunca.
"""

from django.contrib import admin

from .models import Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "nit", "pais", "activo")
    list_filter = ("tipo", "pais", "activo")
    search_fields = ("codigo", "nombre", "nit")
    readonly_fields = ("codigo",)
