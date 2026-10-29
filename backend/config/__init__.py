"""
Paquete de configuración del proyecto.

Se importa la aplicación de Celery al cargar Django, como indica la
documentación de Celery, para que las tareas queden registradas también cuando
se encolan desde la API y no solo dentro del worker.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
