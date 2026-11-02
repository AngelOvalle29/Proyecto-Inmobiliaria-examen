"""
python manage.py cargar_demo_arrendamientos

Carga contratos de arrendamiento de demostración. Es una cáscara delgada:
llama al servicio y muestra el resultado. Lo invoca seed_demo
(COMANDOS_DE_DEMO), después del catálogo, el CRM y ventas.
"""

from django.core.management.base import BaseCommand

from apps.arrendamientos.services import cargar_demo_arrendamientos


class Command(BaseCommand):
    help = "Carga contratos de arrendamiento de demostración sin duplicar."

    def handle(self, *args, **options):
        creados = cargar_demo_arrendamientos()

        self.stdout.write(
            self.style.SUCCESS("Arrendamientos de demostración cargados.")
        )
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
