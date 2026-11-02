"""
python manage.py cargar_demo_construccion

Carga las constructoras de demostración. Es una cáscara delgada: llama al
servicio. Normalmente lo invoca seed_demo (COMANDOS_DE_DEMO), después de cargar
los países de core.
"""

from django.core.management.base import BaseCommand

from apps.construccion.services import cargar_demo_construccion


class Command(BaseCommand):
    help = "Carga constructoras de demostración sin duplicar."

    def handle(self, *args, **options):
        creadas = cargar_demo_construccion()

        self.stdout.write(self.style.SUCCESS("Construcción de demostración cargada."))
        for entidad, cantidad in creadas.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevas")
