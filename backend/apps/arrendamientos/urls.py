"""Rutas de arrendamientos, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    ArrendamientoDetalleView,
    ArrendamientosView,
    DocumentoArrendamientoView,
    FinalizarArrendamientoView,
    PagarRentaView,
    RenovarArrendamientoView,
    RescindirArrendamientoView,
)

BASE = "contratos-arrendamiento/"

urlpatterns = [
    path(BASE, ArrendamientosView.as_view(), name="arrendamientos"),
    path(
        f"{BASE}<int:pk>/",
        ArrendamientoDetalleView.as_view(),
        name="arrendamiento-detalle",
    ),
    path(
        f"{BASE}<int:pk>/renovar/",
        RenovarArrendamientoView.as_view(),
        name="arrendamiento-renovar",
    ),
    path(
        f"{BASE}<int:pk>/rescindir/",
        RescindirArrendamientoView.as_view(),
        name="arrendamiento-rescindir",
    ),
    path(
        f"{BASE}<int:pk>/finalizar/",
        FinalizarArrendamientoView.as_view(),
        name="arrendamiento-finalizar",
    ),
    path(
        f"{BASE}<int:pk>/documento/",
        DocumentoArrendamientoView.as_view(),
        name="arrendamiento-documento",
    ),
    path("pagos-renta/<int:pk>/pagar/", PagarRentaView.as_view(), name="renta-pagar"),
]
