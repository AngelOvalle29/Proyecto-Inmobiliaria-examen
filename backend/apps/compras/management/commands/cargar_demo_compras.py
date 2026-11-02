"""
python manage.py cargar_demo_compras

Carga los proveedores y contratos de compra de demostración. Es una cáscara
delgada: llama al servicio. Normalmente lo invoca seed_demo
(COMANDOS_DE_DEMO), después de core y del catálogo.
"""

from django.core.management.base import BaseCommand

from apps.compras.services import cargar_demo_compras


class Command(BaseCommand):
    help = "Carga proveedores y contratos de compra de demostración sin duplicar."

    def handle(self, *args, **options):
        creados = cargar_demo_compras()

        self.stdout.write(self.style.SUCCESS("Compras de demostración cargadas."))
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
