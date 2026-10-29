"""
Aplicación de Celery del proyecto (spec 002, §5.5).

Lee su configuración de los settings de Django, de las variables que empiezan
con CELERY_, y busca las tareas en el tasks.py de cada app instalada.
"""

import os

from celery import Celery

# Igual que manage.py: sin otra indicación, los settings de desarrollo. En
# producción DJANGO_SETTINGS_MODULE lo define Render.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
