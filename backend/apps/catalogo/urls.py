"""Rutas de catálogo, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AvaluoDetalleView,
    AvaluosDePropiedadView,
    CambiarEstadoPropiedadView,
    CambiarEstadoUnidadView,
    DocumentoDescargaView,
    DocumentoDetalleView,
    DocumentosDePropiedadView,
    PropiedadDetalleView,
    PropiedadesView,
    TipoPropiedadDetalleView,
    TiposPropiedadView,
    UnidadDetalleView,
    UnidadesDePropiedadView,
)

urlpatterns = [
    path("tipos-propiedad/", TiposPropiedadView.as_view(), name="tipos-propiedad"),
    path(
        "tipos-propiedad/<int:pk>/",
        TipoPropiedadDetalleView.as_view(),
        name="tipo-propiedad",
    ),
    path("propiedades/", PropiedadesView.as_view(), name="propiedades"),
    path("propiedades/<int:pk>/", PropiedadDetalleView.as_view(), name="propiedad"),
    path(
        "propiedades/<int:pk>/cambiar-estado/",
        CambiarEstadoPropiedadView.as_view(),
        name="propiedad-cambiar-estado",
    ),
    path(
        "propiedades/<int:pk>/unidades/",
        UnidadesDePropiedadView.as_view(),
        name="propiedad-unidades",
    ),
    path("unidades/<int:pk>/", UnidadDetalleView.as_view(), name="unidad"),
    path(
        "unidades/<int:pk>/cambiar-estado/",
        CambiarEstadoUnidadView.as_view(),
        name="unidad-cambiar-estado",
    ),
    path(
        "propiedades/<int:pk>/avaluos/",
        AvaluosDePropiedadView.as_view(),
        name="propiedad-avaluos",
    ),
    path("avaluos/<int:pk>/", AvaluoDetalleView.as_view(), name="avaluo"),
    path(
        "propiedades/<int:pk>/documentos/",
        DocumentosDePropiedadView.as_view(),
        name="propiedad-documentos",
    ),
    path(
        "documentos/<int:pk>/descarga/",
        DocumentoDescargaView.as_view(),
        name="documento-descarga",
    ),
    path("documentos/<int:pk>/", DocumentoDetalleView.as_view(), name="documento"),
]
