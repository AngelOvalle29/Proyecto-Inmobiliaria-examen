"""
Pruebas automáticas, locales y de la integración continua.

Usa la misma PostgreSQL que desarrollo: pytest-django crea una base aparte
(test_<nombre>) y la destruye al terminar.
"""

from .base import *

DEBUG = False

# El algoritmo por defecto es lento a propósito, para resistir ataques de
# fuerza bruta. En pruebas no hay nada que proteger y cada usuario creado
# costaría tiempo, así que se usa uno rápido. Nunca en otro entorno.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Con DEBUG en False, WhiteNoise escanea la carpeta de collectstatic al arrancar,
# y en las pruebas esa carpeta no existe: avisaría en cada petición. En este
# modo busca los archivos al pedirlos, igual que en desarrollo.
WHITENOISE_AUTOREFRESH = True

# Las tareas de Celery se ejecutan en el mismo proceso, al momento de
# encolarlas: las pruebas no necesitan RabbitMQ ni un worker. EAGER_PROPAGATES
# hace que un error dentro de la tarea falle la prueba en vez de perderse.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
