"""
python manage.py cargar_demo_ia

Carga e indexa los documentos de demostración del agente (spec 005, §6). Como
una tarea de Celery, es una cáscara: decide si se puede indexar y llama a la
carga.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ia.datos_demo import cargar_demo_ia
from apps.ia.proveedores.base import ProveedorIANoDisponible


class Command(BaseCommand):
    help = "Carga e indexa los documentos de demostración del agente de IA."

    def handle(self, *args, **options):
        indexar = bool(settings.IA_API_KEY)
        if not indexar:
            self.stdout.write(
                "IA_API_KEY no está configurada: los documentos se cargan sin "
                "indexar y el agente responderá 503 hasta que se configure."
            )
        try:
            resumen = cargar_demo_ia(indexar=indexar)
        except ProveedorIANoDisponible as error:
            # No es un error del arranque: si Gemini está saturado, el
            # contenedor debe levantar igual. Lo pendiente se indexa la próxima
            # vez que corra el comando.
            self.stderr.write(f"No se pudo indexar con Gemini: {error}")
            return

        self.stdout.write(self.style.SUCCESS("Documentos del agente cargados."))
        for clave, cantidad in resumen.items():
            self.stdout.write(f"  {clave}: {cantidad}")
