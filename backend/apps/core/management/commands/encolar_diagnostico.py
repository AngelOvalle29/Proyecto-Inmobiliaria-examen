"""
python manage.py encolar_diagnostico

Encola la tarea de diagnóstico del worker (spec 002, §5.5). Lo llama el script
de arranque del contenedor, porque en Render no hay terminal para hacerlo a
mano.
"""

from django.core.management.base import BaseCommand

from apps.core.tasks import verificar_worker


class Command(BaseCommand):
    help = "Encola la tarea de diagnóstico para comprobar que el worker consume."

    def handle(self, *args, **options):
        # Si RabbitMQ no responde, se avisa y se sigue: el script de arranque no
        # debe dejar la API caída solo porque el diagnóstico no pudo encolarse.
        # El aviso queda en los registros, que es donde se busca el diagnóstico.
        try:
            verificar_worker.delay()
        except Exception as error:
            self.stderr.write(
                self.style.WARNING(f"No se pudo encolar el diagnóstico: {error}")
            )
            return
        self.stdout.write(self.style.SUCCESS("Tarea de diagnóstico encolada."))
