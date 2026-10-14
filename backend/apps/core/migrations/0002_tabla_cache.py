"""
Crea la tabla de la caché de Django en PostgreSQL (CACHES en settings/base.py).

Django crea esa tabla con el comando createcachetable, no con migrate. Se
llama desde esta migración para que migrate sea el único paso necesario en
todos los entornos: el Dockerfile de producción solo corre migrate, y nadie
tiene que acordarse de un comando extra.

createcachetable no hace nada si la tabla ya existe, así que es seguro
correrla varias veces.
"""

from django.core.management import call_command
from django.db import migrations


def crear_tabla_cache(apps, schema_editor):
    call_command("createcachetable", verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        # Al revertir no se borra la tabla: solo guarda datos temporales y
        # borrarla no aporta nada.
        migrations.RunPython(crear_tabla_cache, migrations.RunPython.noop),
    ]
