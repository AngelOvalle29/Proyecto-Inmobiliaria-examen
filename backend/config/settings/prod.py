"""
Producción. La completa la spec 002 (proxy de Railway, archivos estáticos).

SECRET_KEY y DATABASE_URL ya son obligatorias desde base.py.
"""

from .base import *

# Fijo, no leído del entorno: una variable mal puesta no debe poder activar la
# depuración en producción y exponer trazas de error.
DEBUG = False

# Obligatoria: sin ella Django rechazaría todas las peticiones.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Las cookies de sesión y CSRF solo viajan por HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
