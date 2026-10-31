"""
python manage.py seed_demo

Carga los datos de demostración. Como una tarea de Celery, es una cáscara
delgada: llama al servicio y muestra el resultado; la lógica vive en
apps/core/services.py.

Primero carga los catálogos de core (monedas, países, ciudades y tipos de
cambio), de los que dependen las demás apps. Luego llama, en orden, al comando
de carga de cada app de dominio.

Esos comandos se llaman por su nombre, con call_command, y no importando sus
servicios: core no importa a ninguna app (docs/arquitectura.md §3). Para que
una app tenga datos de demostración:

1. Crea apps/<app>/management/commands/cargar_demo_<app>.py, que llama al
   servicio cargar_demo_<app>() de su services.py.
2. Agrega el nombre del comando a COMANDOS_DE_DEMO, después de los comandos de
   las apps de las que depende.

Un comando de la lista que todavía no existe se omite con un aviso: así la
lista se puede preparar antes de que la app esté lista.
"""

from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.services import cargar_catalogos_demo

# En orden de dependencia: crm no depende del catálogo, pero ventas y
# arrendamientos dependerán de los dos.
COMANDOS_DE_DEMO = [
    "cargar_demo_catalogo",
    "cargar_demo_crm",
    "cargar_demo_ventas",
    "cargar_demo_arrendamientos",
]


class Command(BaseCommand):
    help = "Carga datos de demostración. Se puede correr varias veces sin duplicar."

    def handle(self, *args, **options):
        # Fecha local de la agencia (TIME_ZONE), no la fecha UTC: a las 8 p. m.
        # del 31 en Guatemala, en UTC ya es el día 1 del mes siguiente.
        creados = cargar_catalogos_demo(hasta=timezone.localdate())

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        for catalogo, cantidad in creados.items():
            self.stdout.write(f"  {catalogo}: {cantidad} nuevos")

        # get_commands() lista los comandos de todas las apps instaladas.
        disponibles = get_commands()
        for comando in COMANDOS_DE_DEMO:
            if comando not in disponibles:
                self.stdout.write(
                    self.style.WARNING(f"Se omite {comando}: todavía no existe.")
                )
                continue
            call_command(comando, stdout=self.stdout, stderr=self.stderr)
