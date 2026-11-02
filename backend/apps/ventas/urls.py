"""Rutas de ventas, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AnularContratoView,
    ContratosVentaView,
    ContratoVentaDetalleView,
    DocumentoContratoView,
    PagarCuotaView,
)

urlpatterns = [
    path("contratos-venta/", ContratosVentaView.as_view(), name="contratos-venta"),
    path(
        "contratos-venta/<int:pk>/",
        ContratoVentaDetalleView.as_view(),
        name="contrato-venta-detalle",
    ),
    path(
        "contratos-venta/<int:pk>/anular/",
        AnularContratoView.as_view(),
        name="contrato-venta-anular",
    ),
    path(
        "contratos-venta/<int:pk>/documento/",
        DocumentoContratoView.as_view(),
        name="contrato-venta-documento",
    ),
    path("cuotas/<int:pk>/pagos/", PagarCuotaView.as_view(), name="cuota-pagar"),
]
