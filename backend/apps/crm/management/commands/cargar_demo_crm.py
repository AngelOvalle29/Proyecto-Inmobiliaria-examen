"""
python manage.py cargar_demo_crm

Carga los agentes y clientes de demostración. Es una cáscara delgada: lee el
entorno y llama al servicio. Normalmente no se corre solo: lo invoca seed_demo
(COMANDOS_DE_DEMO), después de cargar los países y ciudades de core.

DEMO_AGENTES_PASSWORD es opcional: sin ella, los agentes de demostración no
pueden iniciar sesión (spec 004, §6).
"""

import os

from django.core.management.base import BaseCommand

from apps.crm.services import cargar_demo_crm


class Command(BaseCommand):
    help = "Carga agentes y clientes de demostración sin duplicar."

    def handle(self, *args, **options):
        # Vacía cuenta como no definida: así una variable creada en el panel
        # de Render y dejada sin valor no se convierte en una contraseña vacía.
        password = os.environ.get("DEMO_AGENTES_PASSWORD") or None
        creados = cargar_demo_crm(password_agentes=password)

        self.stdout.write(self.style.SUCCESS("CRM de demostración cargado."))
        for entidad, cantidad in creados.items():
            self.stdout.write(f"  {entidad}: {cantidad} nuevos")
