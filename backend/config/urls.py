"""
Rutas raíz del proyecto.

La API vivirá bajo /api/v1/ (docs/arquitectura.md §4); cada app aporta sus
rutas en los incrementos siguientes.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
