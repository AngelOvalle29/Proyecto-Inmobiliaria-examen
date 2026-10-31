"""
Producción: un servicio web de Render detrás de su proxy (spec 002, §5.2).

SECRET_KEY y DATABASE_URL ya son obligatorias desde base.py.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *

# Fijo, no leído del entorno: una variable mal puesta no debe poder activar la
# depuración en producción y exponer trazas de error.
DEBUG = False


# ---------- Clave secreta ----------

# SECRET_KEY firma también los tokens JWT. Una clave corta los firmaría de
# forma débil (el algoritmo HS256 pide al menos 32 bytes), así que producción
# no arranca con menos de 50 caracteres, el mínimo que recomienda Django.
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "SECRET_KEY es demasiado corta: use al menos 50 caracteres aleatorios."
    )


# ---------- Hosts ----------

# Render expone el dominio del servicio (<servicio>.onrender.com) en
# RENDER_EXTERNAL_HOSTNAME, y llama a la ruta de salud con ese host. Se agrega
# siempre que exista, así no hay que copiarlo a mano en ALLOWED_HOSTS. La
# variable ALLOWED_HOSTS queda para un dominio propio.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Con la lista vacía Django rechazaría todas las peticiones con un error 400 y
# sin explicar por qué. Es mejor no arrancar y decirlo.
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS está vacía: defina ALLOWED_HOSTS o despliegue en Render, "
        "que aporta RENDER_EXTERNAL_HOSTNAME."
    )


# ---------- HTTPS detrás del proxy ----------

# Render atiende HTTPS en su proxy y le pasa la petición a Django por HTTP,
# avisando el protocolo original en X-Forwarded-Proto. Sin esto Django cree que
# la conexión no es segura, y el CSRF del panel y las cookies seguras fallan.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Las cookies de sesión y CSRF solo viajan por HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# No se activa SECURE_SSL_REDIRECT, porque Render ya redirige a HTTPS en su
# proxy, ni HSTS, porque un error de configuración de HSTS no se puede
# deshacer desde el servidor (spec 002, §5.2). Se silencian sus dos avisos de
# "check --deploy" para que el chequeo quede limpio y un aviso nuevo se note.
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]


# ---------- Celery ----------

# Obligatoria, como SECRET_KEY: sin ella el worker intentaría conectarse a un
# RabbitMQ local que en Render no existe, y las tareas se perderían sin que
# nadie lo note. Se rechaza también vacía, que es como queda si en el panel de
# Render se crea la variable y se olvida su valor.
CELERY_BROKER_URL = env("RABBITMQ_URL", default="")
if not CELERY_BROKER_URL:
    raise ImproperlyConfigured("RABBITMQ_URL es obligatoria en producción.")


# ---------- Base de datos ----------

# Reutiliza cada conexión hasta 60 segundos en lugar de abrir una nueva por
# petición: cada conexión nueva a Neon cuesta tiempo. CONN_HEALTH_CHECKS
# comprueba que la conexión siga viva antes de reutilizarla, porque Neon la
# corta cuando se duerme.
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True


# ---------- Archivos estáticos ----------

# WhiteNoise con manifiesto: collectstatic agrega un hash al nombre de cada
# archivo (base.abc123.css), así el navegador puede guardarlo en caché por
# mucho tiempo sin riesgo de usar una versión vieja. Solo en producción: el
# manifiesto exige haber corrido collectstatic, y en desarrollo y en las
# pruebas no se corre.
# Solo se cambia el almacenamiento de los estáticos: el de los archivos subidos
# lo decide base.py según STORAGE_BACKEND (spec 011, §6). En producción debe ser
# "s3"; con "local" los documentos se perderían en cada despliegue de Render.
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}


# ---------- Registro de errores ----------

# Con DEBUG = False, Django no imprime en la consola las trazas de los errores
# 500. Sin esto, un error en producción no dejaría rastro en los registros de
# Render. El cliente sigue sin ver la traza: solo va a la salida estándar.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "consola": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["consola"], "level": "INFO"},
}
