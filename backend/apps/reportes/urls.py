"""Rutas de reportes, montadas bajo /api/v1/."""

from django.urls import path

from .views import CatalogoReportesView, ExportarReporteView, ReporteView

urlpatterns = [
    path("reportes/", CatalogoReportesView.as_view(), name="reportes-catalogo"),
    path("reportes/<slug:slug>/", ReporteView.as_view(), name="reportes-detalle"),
    path(
        "reportes/<slug:slug>/excel/",
        ExportarReporteView.as_view(formato="excel"),
        name="reportes-excel",
    ),
    path(
        "reportes/<slug:slug>/pdf/",
        ExportarReporteView.as_view(formato="pdf"),
        name="reportes-pdf",
    ),
]
