"""
python manage.py asegurar_administrador

Crea el administrador inicial con las variables DJANGO_SUPERUSER_EMAIL,
DJANGO_SUPERUSER_NOMBRE_COMPLETO y DJANGO_SUPERUSER_PASSWORD, si todavía no
existe ningún superusuario (spec 002, §5.8). Lo llama el script de arranque
del contenedor, porque en Render no hay terminal para usar createsuperuser.

Como una tarea de Celery, es una cáscara: lee el entorno y llama al servicio.
"""

import os

from django.core.management.base import BaseCommand

from apps.usuarios.services import asegurar_administrador_inicial

VARIABLES = (
    "DJANGO_SUPERUSER_EMAIL",
    "DJANGO_SUPERUSER_NOMBRE_COMPLETO",
    "DJANGO_SUPERUSER_PASSWORD",
)


class Command(BaseCommand):
    help = "Crea el administrador inicial desde variables de entorno, una sola vez."

    def handle(self, *args, **options):
        faltan = [nombre for nombre in VARIABLES if not os.environ.get(nombre)]
        if faltan:
            # No es un error: en desarrollo el administrador se crea con
            # createsuperuser y estas variables no existen.
            self.stdout.write(
                "Administrador inicial no configurado; faltan: " + ", ".join(faltan)
            )
            return

        usuario = asegurar_administrador_inicial(
            email=os.environ["DJANGO_SUPERUSER_EMAIL"],
            nombre_completo=os.environ["DJANGO_SUPERUSER_NOMBRE_COMPLETO"],
            password=os.environ["DJANGO_SUPERUSER_PASSWORD"],
        )
        if usuario is None:
            self.stdout.write("Ya existe un superusuario; no se creó otro.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Administrador inicial creado: {usuario.email}")
            )
