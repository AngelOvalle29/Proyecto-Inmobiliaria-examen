"""Registro de los modelos de arrendamientos en el panel de Django.

Sin reglas de negocio. Solo lectura, como en crm y ventas: toda escritura pasa
por los servicios, que cambian el estado del bien, generan los pagos y
registran la auditoría.
"""

from django.contrib import admin

from apps.crm.admin import AdminSoloLectura

from .models import ContratoArrendamiento, PagoRenta


class PagoEnLinea(admin.TabularInline):
    model = PagoRenta
    extra = 0
    can_delete = False
    fields = ["fecha_vencimiento", "monto", "estado", "fecha_pago", "mora_aplicada"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ContratoArrendamiento)
class ContratoArrendamientoAdmin(AdminSoloLectura):
    list_display = [
        "codigo",
        "cliente",
        "fecha_inicio",
        "fecha_fin",
        "renta_mensual",
        "estado",
    ]
    list_filter = ["estado"]
    search_fields = ["codigo", "cliente__codigo"]
    list_select_related = ["cliente", "moneda"]
    inlines = [PagoEnLinea]
