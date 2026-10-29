"""
Normalización de datos que llegan escritos de varias formas.

Funciones puras: no consultan la base ni importan ninguna app. Las usan crm,
compras y construccion, que no deben depender entre sí (spec 004, revisión
de #39 y #35).
"""

import re

# Espacios de cualquier tipo y guiones.
SEPARADORES = re.compile(r"[\s-]")


def normalizar_documento(valor: str) -> str:
    """
    Documento de identidad o NIT tal como se guarda y se compara.

    Quita espacios y guiones y pasa a mayúsculas, para que "1234 56789-0101" y
    "1234567890101", o "1234567-k" y "1234567K", sean el mismo documento al
    buscar duplicados. Un valor formado solo por separadores ("-") queda vacío:
    quien llama decide si eso es válido.
    """
    return SEPARADORES.sub("", valor).upper()
