"""
Punto de entrada ASGI. No se usa todavía (producción corre con gunicorn y
WSGI); se conserva porque es parte del esqueleto estándar de Django.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
