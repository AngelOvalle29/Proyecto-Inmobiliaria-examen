"""
python manage.py seed_demo

Carga los datos de demostración. Como una tarea de Celery, es una cáscara
delgada: llama al servicio y muestra el resultado; la lógica vive en
apps/core/services.py.

Cada spec que agregue entidades con datos de demostración suma aquí la
llamada a su propio servicio de carga.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.services import cargar_catalogos_demo


class Command(BaseCommand):
    help = "Carga datos de demostración. Se puede correr varias veces sin duplicar."

    def handle(self, *args, **options):
        # Fecha local de la agencia (TIME_ZONE), no la fecha UTC: a las 8 p. m.
        # del 31 en Guatemala, en UTC ya es el día 1 del mes siguiente.
        creados = cargar_catalogos_demo(hasta=timezone.localdate())

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        for catalogo, cantidad in creados.items():
            self.stdout.write(f"  {catalogo}: {cantidad} nuevos")
