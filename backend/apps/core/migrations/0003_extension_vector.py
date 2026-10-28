"""
Habilita la extensión vector (pgvector) en PostgreSQL (spec 002, §5.6).

Va en core y no en ia porque es infraestructura de la base, no un modelo: así
la extensión ya existe cuando el rol C cree los modelos con vectores del RAG, y
el primer despliegue comprueba que Neon la soporta. Al ser una migración, nadie
tiene que habilitarla a mano en ningún entorno.

CreateExtension usa CREATE EXTENSION IF NOT EXISTS, así que no falla si la
extensión ya estaba habilitada.
"""

from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_tabla_cache"),
    ]

    operations = [
        CreateExtension("vector"),
    ]
