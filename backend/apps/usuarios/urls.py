"""Rutas de usuarios, montadas bajo /api/v1/."""

from django.urls import path

from .views import (
    CambiarContrasenaView,
    DesactivarUsuarioView,
    ListarUsuariosView,
    LoginView,
    ReactivarUsuarioView,
    RenovarTokenView,
    RestablecerContrasenaView,
    UsuarioActualView,
    UsuarioDetalleView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RenovarTokenView.as_view(), name="renovar-token"),
    path("auth/yo/", UsuarioActualView.as_view(), name="usuario-actual"),
    path(
        "auth/cambiar-contrasena/",
        CambiarContrasenaView.as_view(),
        name="cambiar-contrasena",
    ),
    path("usuarios/", ListarUsuariosView.as_view(), name="usuarios"),
    path("usuarios/<int:pk>/", UsuarioDetalleView.as_view(), name="usuario"),
    path(
        "usuarios/<int:pk>/desactivar/",
        DesactivarUsuarioView.as_view(),
        name="usuario-desactivar",
    ),
    path(
        "usuarios/<int:pk>/reactivar/",
        ReactivarUsuarioView.as_view(),
        name="usuario-reactivar",
    ),
    path(
        "usuarios/<int:pk>/restablecer-contrasena/",
        RestablecerContrasenaView.as_view(),
        name="usuario-restablecer-contrasena",
    ),
]
