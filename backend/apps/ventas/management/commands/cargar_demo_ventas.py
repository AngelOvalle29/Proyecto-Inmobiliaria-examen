"""
python manage.py cargar_demo_ventas

Carga contratos de venta y cotizaciones de demostración. Es una cáscara
delgada: llama al servicio y muestra el resultado. Normalmente no se corre
solo: lo invoca seed_demo (COMANDOS_DE_DEMO), después del catálogo y del CRM,
de los que depende.
"""

from django.core.management.base import BaseCommand

from apps.ventas.services import cargar_demo_ventas


class Command(BaseCommand):
    help = "Carga contratos de venta y cotizaciones de demostración sin duplicar."

    def handle(self, *args, **options):
        creados = cargar_demo_ventas()

        self.stdout.write(self.style.SUCCESS("Ventas de demostración cargadas."))
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
