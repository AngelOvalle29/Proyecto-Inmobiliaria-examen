"""Registro de los modelos de IA en el panel de Django.

Sin reglas de negocio. Los dos modelos son de solo lectura en el panel:
crearlos o editarlos ahí saltaría los servicios y la auditoría (spec 005, §7).
"""

from django.contrib import admin

from .models import DocumentoRAG, FragmentoRAG


class SoloLecturaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentoRAG)
class DocumentoRAGAdmin(SoloLecturaAdmin):
    list_display = ("titulo", "tipo", "pais", "version", "fecha_indexacion", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("titulo",)


@admin.register(FragmentoRAG)
class FragmentoRAGAdmin(SoloLecturaAdmin):
    list_display = ("documento", "orden", "seccion", "tokens")
    list_filter = ("documento",)
    search_fields = ("seccion", "contenido")
    # El vector son 768 números: en pantalla no le dicen nada a nadie.
    exclude = ("embedding",)
