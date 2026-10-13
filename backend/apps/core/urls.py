"""Rutas de core, montadas bajo /api/v1/."""

from django.urls import path

from .views import EstadoServicioView

urlpatterns = [
    path("health/", EstadoServicioView.as_view(), name="health"),
]
