"""Rutas de CRM, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AgenteDetalleView,
    AgentesView,
    AprobarCotizacionView,
    ClienteDetalleView,
    ClientesView,
    CotizacionDetalleView,
    CotizacionesView,
    EnviarCotizacionView,
    ReasignarClienteView,
    RechazarCotizacionView,
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
    path("cotizaciones/", CotizacionesView.as_view(), name="cotizaciones"),
    path(
        "cotizaciones/<int:pk>/",
        CotizacionDetalleView.as_view(),
        name="cotizacion-detalle",
    ),
    path(
        "cotizaciones/<int:pk>/enviar/",
        EnviarCotizacionView.as_view(),
        name="cotizacion-enviar",
    ),
    path(
        "cotizaciones/<int:pk>/aprobar/",
        AprobarCotizacionView.as_view(),
        name="cotizacion-aprobar",
    ),
    path(
        "cotizaciones/<int:pk>/rechazar/",
        RechazarCotizacionView.as_view(),
        name="cotizacion-rechazar",
    ),
]
