"""
Crea los siete tipos de propiedad (spec 003, §4).

Es una migración de datos y no parte de los datos de demostración porque el
sistema no funciona sin ellos: deben existir en producción con solo correr
migrate. Mismo criterio que los roles de la spec 001.

La lista se copia aquí a propósito: una migración describe la base en un
momento dado y no debe cambiar si el código cambia después.
"""

from django.db import migrations

# (nombre, descripción, requiere_unidades)
TIPOS = [
    ("Apartamentos", "Edificio con apartamentos o locales.", True),
    ("Terreno", "Terreno sin construcción.", False),
    ("Casa", "Vivienda unifamiliar.", False),
    ("Hotel", "Hotel con habitaciones o suites.", True),
    ("Bodega", "Bodega o nave industrial.", False),
    ("Restaurante", "Local de restaurante.", False),
    ("Gasolinera", "Estación de servicio.", False),
]


def crear_tipos(apps, schema_editor):
    TipoPropiedad = apps.get_model("catalogo", "TipoPropiedad")
    for nombre, descripcion, requiere_unidades in TIPOS:
        TipoPropiedad.objects.get_or_create(
            nombre=nombre,
            defaults={
                "descripcion": descripcion,
                "requiere_unidades": requiere_unidades,
            },
        )


def eliminar_tipos(apps, schema_editor):
    TipoPropiedad = apps.get_model("catalogo", "TipoPropiedad")
    TipoPropiedad.objects.filter(nombre__in=[nombre for nombre, _, _ in TIPOS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_tipos, eliminar_tipos),
    ]
