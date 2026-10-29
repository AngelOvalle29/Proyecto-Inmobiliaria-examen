"""Rutas de core, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    EstadoServicioView,
    ListarCiudadesView,
    ListarMonedasView,
    ListarPaisesView,
    ListarTiposCambioView,
)

urlpatterns = [
    path("health/", EstadoServicioView.as_view(), name="health"),
    path("monedas/", ListarMonedasView.as_view(), name="monedas"),
    path("paises/", ListarPaisesView.as_view(), name="paises"),
    path("ciudades/", ListarCiudadesView.as_view(), name="ciudades"),
    path("tipos-cambio/", ListarTiposCambioView.as_view(), name="tipos-cambio"),
]
