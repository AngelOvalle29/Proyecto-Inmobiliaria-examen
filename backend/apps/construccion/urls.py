"""Rutas de construcción, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    AvanceProyectoView,
    CancelarProyectoView,
    ConstructoraDetalleView,
    ConstructorasView,
    FinalizarProyectoView,
    IniciarProyectoView,
    ProyectoDetalleView,
    ProyectosView,
    ReanudarProyectoView,
    SuspenderProyectoView,
)

PROYECTO = "proyectos-construccion/<int:pk>/"

urlpatterns = [
    path("constructoras/", ConstructorasView.as_view(), name="constructoras"),
    path(
        "constructoras/<int:pk>/",
        ConstructoraDetalleView.as_view(),
        name="constructora-detalle",
    ),
    path("proyectos-construccion/", ProyectosView.as_view(), name="proyectos"),
    path(PROYECTO, ProyectoDetalleView.as_view(), name="proyecto-detalle"),
    path(f"{PROYECTO}iniciar/", IniciarProyectoView.as_view(), name="proyecto-iniciar"),
    path(f"{PROYECTO}avance/", AvanceProyectoView.as_view(), name="proyecto-avance"),
    path(
        f"{PROYECTO}suspender/",
        SuspenderProyectoView.as_view(),
        name="proyecto-suspender",
    ),
    path(
        f"{PROYECTO}reanudar/",
        ReanudarProyectoView.as_view(),
        name="proyecto-reanudar",
    ),
    path(
        f"{PROYECTO}finalizar/",
        FinalizarProyectoView.as_view(),
        name="proyecto-finalizar",
    ),
    path(
        f"{PROYECTO}cancelar/",
        CancelarProyectoView.as_view(),
        name="proyecto-cancelar",
    ),
]
