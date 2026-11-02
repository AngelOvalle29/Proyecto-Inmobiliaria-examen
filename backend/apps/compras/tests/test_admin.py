"""El panel de Django solo consulta: no es una puerta trasera sin reglas ni
bitácora (revisión del PR #63)."""

from django.contrib import admin

from apps.compras.models import Proveedor


def test_el_panel_no_permite_crear_editar_ni_borrar():
    modelo_admin = admin.site._registry[Proveedor]

    assert modelo_admin.has_add_permission(request=None) is False
    assert modelo_admin.has_change_permission(request=None) is False
    assert modelo_admin.has_delete_permission(request=None) is False
