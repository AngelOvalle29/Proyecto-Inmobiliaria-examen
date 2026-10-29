"""Pruebas del panel de Django para los catálogos de core."""

import pytest
from django.contrib import admin

from apps.core.models import Ciudad, Moneda, Pais, TipoCambio


@pytest.mark.parametrize("modelo", [Moneda, Pais, Ciudad, TipoCambio])
def test_el_panel_no_permite_borrar_catalogos(modelo):
    """Regla 10: los catálogos se desactivan, no se borran."""
    modelo_admin = admin.site._registry[modelo]

    assert modelo_admin.has_delete_permission(request=None) is False
