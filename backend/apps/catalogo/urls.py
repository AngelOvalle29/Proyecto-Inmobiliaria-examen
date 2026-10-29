"""Rutas de catálogo, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    CambiarEstadoPropiedadView,
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
]
