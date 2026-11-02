"""Rutas de IA, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    ConsultaAgenteView,
    DocumentoAgenteDetalleView,
    DocumentosAgenteView,
    ReindexarDocumentoAgenteView,
)

urlpatterns = [
    path("agente/consultas/", ConsultaAgenteView.as_view(), name="agente-consulta"),
    path(
        "documentos-agente/", DocumentosAgenteView.as_view(), name="documentos-agente"
    ),
    path(
        "documentos-agente/<int:pk>/",
        DocumentoAgenteDetalleView.as_view(),
        name="documento-agente",
    ),
    path(
        "documentos-agente/<int:pk>/reindexar/",
        ReindexarDocumentoAgenteView.as_view(),
        name="documento-agente-reindexar",
    ),
]
