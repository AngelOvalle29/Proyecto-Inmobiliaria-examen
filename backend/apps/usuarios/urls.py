"""Rutas de usuarios, montadas bajo /api/v1/."""

from django.urls import path

from .views import LoginView, RenovarTokenView, UsuarioActualView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RenovarTokenView.as_view(), name="renovar-token"),
    path("auth/yo/", UsuarioActualView.as_view(), name="usuario-actual"),
]
