"""Rutas de compras, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AnularContratoCompraView,
    CompletarContratoCompraView,
    ContratoCompraDetalleView,
    ContratosCompraView,
    ProveedorDetalleView,
    ProveedoresView,
)

urlpatterns = [
    path("proveedores/", ProveedoresView.as_view(), name="proveedores"),
    path(
        "proveedores/<int:pk>/",
        ProveedorDetalleView.as_view(),
        name="proveedor-detalle",
    ),
    path("contratos-compra/", ContratosCompraView.as_view(), name="contratos-compra"),
    path(
        "contratos-compra/<int:pk>/",
        ContratoCompraDetalleView.as_view(),
        name="contrato-compra-detalle",
    ),
    path(
        "contratos-compra/<int:pk>/completar/",
        CompletarContratoCompraView.as_view(),
        name="contrato-compra-completar",
    ),
    path(
        "contratos-compra/<int:pk>/anular/",
        AnularContratoCompraView.as_view(),
        name="contrato-compra-anular",
    ),
]
