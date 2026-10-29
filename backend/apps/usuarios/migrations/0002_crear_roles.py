"""
Crea los cinco roles del sistema.

Es una migración de datos y no parte de seed_demo porque los roles no son
datos de demostración: el sistema no funciona sin ellos, y createsuperuser
necesita que ADMINISTRADOR exista. Así quedan creados en cualquier base,
incluida producción, con solo correr migrate.

La lista se copia aquí en lugar de importar NombreRol a propósito: una
migración describe la base en un momento dado. Si el enum cambia en el
futuro, esta migración debe seguir haciendo exactamente lo mismo.
"""

from django.db import migrations

ROLES = [
    ("ADMINISTRADOR", "Acceso total, incluida la administración de usuarios."),
    ("GERENTE", "Supervisa la operación comercial de la agencia."),
    ("AGENTE", "Agente de ventas: atiende su propia cartera de clientes."),
    ("CONTABILIDAD", "Registra y consulta pagos, cobros e información financiera."),
    ("CONSULTA", "Acceso de solo lectura."),
]


def crear_roles(apps, schema_editor):
    # apps.get_model da la versión histórica del modelo, la que corresponde a
    # este punto de las migraciones, y no la versión actual de models.py.
    Rol = apps.get_model("usuarios", "Rol")
    for nombre, descripcion in ROLES:
        Rol.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})


def eliminar_roles(apps, schema_editor):
    """Permite revertir la migración (migrate usuarios 0001)."""
    Rol = apps.get_model("usuarios", "Rol")
    Rol.objects.filter(nombre__in=[nombre for nombre, _ in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_roles, eliminar_roles),
    ]
