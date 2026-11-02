"""Registro de los modelos de construcción en el panel de Django.

Sin reglas de negocio.
"""

from django.contrib import admin

from .models import Constructora, PagoConstructora, ProyectoConstruccion


class AdminSoloLectura(admin.ModelAdmin):
    """
    El panel solo consulta constructoras, proyectos y pagos; no crea, edita ni
    borra.

    Toda escritura de construcción pasa por los servicios de la API, que
    aplican las reglas de la spec 006 (código generado, NIT normalizado,
    borrado lógico) y registran la auditoría. El panel de Django no pasa por
    ellos: si permitiera escribir, sería una puerta trasera sin reglas ni
    bitácora (mismo criterio que crm y catalogo).
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Constructora)
class ConstructoraAdmin(AdminSoloLectura):
    list_display = ("codigo", "nombre", "nit", "pais", "calificacion", "activo")
    list_filter = ("pais", "calificacion", "activo")
    search_fields = ("codigo", "nombre", "nit")


@admin.register(ProyectoConstruccion)
class ProyectoConstruccionAdmin(AdminSoloLectura):
    list_display = (
        "codigo",
        "nombre",
        "propiedad",
        "constructora",
        "estado",
        "porcentaje_avance",
    )
    list_filter = ("estado",)
    search_fields = ("codigo", "nombre")


@admin.register(PagoConstructora)
class PagoConstructoraAdmin(AdminSoloLectura):
    list_display = ("codigo", "proyecto", "tipo", "monto", "estado", "fecha_pago")
    list_filter = ("estado", "tipo")
    search_fields = ("codigo", "referencia_pago")
