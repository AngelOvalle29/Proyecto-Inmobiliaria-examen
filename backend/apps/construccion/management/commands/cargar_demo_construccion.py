"""
python manage.py cargar_demo_construccion

Carga las constructoras, proyectos y pagos de demostración. Es una cáscara
delgada: llama al servicio. Normalmente lo invoca seed_demo
(COMANDOS_DE_DEMO), después de core y del catálogo.
"""

from django.core.management.base import BaseCommand

from apps.construccion.services import cargar_demo_construccion


class Command(BaseCommand):
    help = "Carga constructoras, proyectos y pagos de demostración sin duplicar."

    def handle(self, *args, **options):
        creados = cargar_demo_construccion()

        self.stdout.write(self.style.SUCCESS("Construcción de demostración cargada."))
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
