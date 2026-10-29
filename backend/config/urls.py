"""
Rutas raíz del proyecto.

Toda la API vive bajo /api/v1/ (docs/arquitectura.md §4); cada app aporta
sus rutas en su propio urls.py. La documentación queda fuera de la versión
porque describe la API completa, no una versión de un recurso.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.usuarios.urls")),
    path("api/v1/", include("apps.catalogo.urls")),
    path("api/v1/", include("apps.crm.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="esquema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="esquema"), name="docs"),
]
