"""Rutas de construcción, montadas bajo /api/v1/."""

from django.urls import path

from .views import ConstructoraDetalleView, ConstructorasView

urlpatterns = [
    path("constructoras/", ConstructorasView.as_view(), name="constructoras"),
    path(
        "constructoras/<int:pk>/",
        ConstructoraDetalleView.as_view(),
        name="constructora-detalle",
    ),
]
