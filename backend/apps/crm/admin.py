"""Registro de los modelos de CRM en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import Agente, Cliente, Cotizacion


class AdminSoloLectura(admin.ModelAdmin):
    """
    El panel solo consulta agentes y clientes; no crea, edita ni borra.

    Toda escritura de CRM pasa por los servicios de la API, que aplican las
    reglas de la spec 004 (código generado, cartera, normalización del
    documento) y registran la auditoría. El panel de Django no pasa por ellos:
    si permitiera escribir, sería una puerta trasera sin reglas ni bitácora.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Agente)
class AgenteAdmin(AdminSoloLectura):
    list_display = ["codigo", "usuario", "porcentaje_comision", "activo"]
    list_filter = ["activo"]
    search_fields = ["codigo", "usuario__email", "usuario__nombre_completo"]
    list_select_related = ["usuario"]


@admin.register(Cliente)
class ClienteAdmin(AdminSoloLectura):
    list_display = ["codigo", "nombre_mostrado", "tipo", "pais", "agente_asignado"]
    list_filter = ["tipo", "activo", "pais"]
    search_fields = [
        "codigo",
        "nombre",
        "apellidos",
        "razon_social",
        "documento_identidad",
        "nit",
    ]
    list_select_related = ["pais", "agente_asignado__usuario"]


@admin.register(Cotizacion)
class CotizacionAdmin(AdminSoloLectura):
    list_display = ["codigo", "cliente", "fecha_emision", "total", "moneda", "estado"]
    list_filter = ["estado"]
    search_fields = ["codigo", "cliente__codigo"]
    list_select_related = ["cliente", "moneda"]
