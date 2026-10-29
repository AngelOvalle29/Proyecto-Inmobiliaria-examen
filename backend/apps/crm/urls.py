"""Rutas de CRM, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AgenteDetalleView,
    AgentesView,
    ClienteDetalleView,
    ClientesView,
    ReasignarClienteView,
)

urlpatterns = [
    path("agentes/", AgentesView.as_view(), name="agentes"),
    path("agentes/<int:pk>/", AgenteDetalleView.as_view(), name="agente-detalle"),
    path("clientes/", ClientesView.as_view(), name="clientes"),
    path("clientes/<int:pk>/", ClienteDetalleView.as_view(), name="cliente-detalle"),
    path(
        "clientes/<int:pk>/reasignar/",
        ReasignarClienteView.as_view(),
        name="cliente-reasignar",
    ),
]
