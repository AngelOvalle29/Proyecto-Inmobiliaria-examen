"""
python manage.py cargar_demo_catalogo

Carga las propiedades y unidades de demostración. Es una cáscara delgada:
llama al servicio y muestra el resultado. Normalmente no se corre solo: lo
invoca seed_demo, después de cargar las ciudades y monedas de core.
"""

from django.core.management.base import BaseCommand

from apps.catalogo.services import cargar_demo_catalogo


class Command(BaseCommand):
    help = "Carga propiedades y unidades de demostración sin duplicar."

    def handle(self, *args, **options):
        creados = cargar_demo_catalogo()

        self.stdout.write(self.style.SUCCESS("Catálogo de demostración cargado."))
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
