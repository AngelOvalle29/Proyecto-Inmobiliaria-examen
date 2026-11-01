"""Rutas de IA, montadas bajo /api/v1/."""

from django.urls import path

from .views import ConsultaAgenteView

urlpatterns = [
    path("agente/consultas/", ConsultaAgenteView.as_view(), name="agente-consulta"),
]
