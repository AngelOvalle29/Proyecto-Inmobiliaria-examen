"""
Punto de entrada WSGI. Lo usa gunicorn en el contenedor de producción.

Por defecto carga los settings de producción; DJANGO_SETTINGS_MODULE lo
sobrescribe si está definida.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
