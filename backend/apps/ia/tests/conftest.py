"""Accesorios de las pruebas de IA."""

import pytest

from .proveedor_falso import ProveedorFalso


@pytest.fixture
def proveedor_falso(monkeypatch):
    """Reemplaza al proveedor real dentro de los servicios de IA."""
    proveedor = ProveedorFalso()
    monkeypatch.setattr("apps.ia.services.obtener_proveedor", lambda: proveedor)
    return proveedor
