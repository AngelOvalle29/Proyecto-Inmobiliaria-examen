"""Pruebas de normalizar_documento (spec 004, regla 7)."""

import pytest

from apps.core.normalizacion import normalizar_documento


@pytest.mark.parametrize(
    ("escrito", "guardado"),
    [
        ("1234567890101", "1234567890101"),
        ("1234 56789 0101", "1234567890101"),
        ("1234-56789-0101", "1234567890101"),
        (" 1234567-k ", "1234567K"),
        ("12\t34", "1234"),
    ],
)
def test_quita_espacios_y_guiones_y_pasa_a_mayusculas(escrito, guardado):
    assert normalizar_documento(escrito) == guardado


@pytest.mark.parametrize("escrito", ["", "-", " - - ", "\t"])
def test_un_documento_solo_de_separadores_queda_vacio(escrito):
    """Quien llama decide si vacío es válido: el serializador de crm lo rechaza."""
    assert normalizar_documento(escrito) == ""
