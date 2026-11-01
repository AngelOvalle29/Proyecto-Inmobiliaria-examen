"""Rutas de compras, montadas bajo /api/v1/."""

from django.urls import path

from .views import ProveedorDetalleView, ProveedoresView

urlpatterns = [
    path("proveedores/", ProveedoresView.as_view(), name="proveedores"),
    path(
        "proveedores/<int:pk>/",
        ProveedorDetalleView.as_view(),
        name="proveedor-detalle",
    ),
]
