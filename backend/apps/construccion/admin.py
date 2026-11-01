"""Registro de los modelos de construcción en el panel de Django.

Sin reglas de negocio. El panel sirve para consultar y para reactivar una
constructora desactivada (spec 006, §2); el código no se edita nunca.
"""

from django.contrib import admin

from .models import Constructora


@admin.register(Constructora)
class ConstructoraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "nit", "pais", "calificacion", "activo")
    list_filter = ("pais", "calificacion", "activo")
    search_fields = ("codigo", "nombre", "nit")
    readonly_fields = ("codigo",)
