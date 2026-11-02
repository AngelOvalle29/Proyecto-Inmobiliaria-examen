"""Registro de los modelos de compras en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import ContratoCompra, Proveedor


class AdminSoloLectura(admin.ModelAdmin):
    """
    El panel solo consulta proveedores y contratos; no crea, edita ni borra.

    Toda escritura de compras pasa por los servicios de la API, que aplican las
    reglas de la spec 006 (código generado, NIT normalizado, borrado lógico) y
    registran la auditoría. El panel de Django no pasa por ellos: si permitiera
    escribir, sería una puerta trasera sin reglas ni bitácora (mismo criterio
    que crm y catalogo).
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Proveedor)
class ProveedorAdmin(AdminSoloLectura):
    list_display = ("codigo", "nombre", "tipo", "nit", "pais", "activo")
    list_filter = ("tipo", "pais", "activo")
    search_fields = ("codigo", "nombre", "nit")


@admin.register(ContratoCompra)
class ContratoCompraAdmin(AdminSoloLectura):
    list_display = ("codigo", "proveedor", "propiedad", "fecha_compra", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo",)
