"""Registro de los modelos de ventas en el panel de Django.

Sin reglas de negocio. Solo lectura, como en crm (spec 004, §10): toda
escritura pasa por los servicios, que cambian el estado de la propiedad,
generan las cuotas y registran la auditoría.
"""

from django.contrib import admin

from apps.crm.admin import AdminSoloLectura

from .models import ContratoVenta, CuotaPago


class CuotaEnLinea(admin.TabularInline):
    model = CuotaPago
    extra = 0
    can_delete = False
    fields = ["numero", "fecha_vencimiento", "monto_total", "monto_pagado", "estado"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ContratoVenta)
class ContratoVentaAdmin(AdminSoloLectura):
    list_display = [
        "codigo",
        "cliente",
        "fecha_firma",
        "monto_total",
        "moneda",
        "estado",
    ]
    list_filter = ["estado", "modalidad"]
    search_fields = ["codigo", "cliente__codigo"]
    list_select_related = ["cliente", "moneda"]
    inlines = [CuotaEnLinea]
