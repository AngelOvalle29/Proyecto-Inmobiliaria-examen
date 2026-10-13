"""
Pruebas de la configuración del proyecto, que no pertenecen a ninguna app.

Protegen reglas de CLAUDE.md que un cambio descuidado en settings podría
romper sin que ninguna otra prueba lo note.
"""

from django.conf import settings


def test_la_base_de_datos_es_postgresql():
    """SQLite está prohibido en todos los entornos, incluidas las pruebas."""
    motor = settings.DATABASES["default"]["ENGINE"]

    assert motor == "django.db.backends.postgresql"


def test_las_fechas_se_guardan_con_zona_horaria():
    """Con USE_TZ las fechas se guardan en UTC y se convierten al mostrarse."""
    assert settings.USE_TZ is True


def test_las_contrasenas_exigen_al_menos_diez_caracteres():
    validador = next(
        v
        for v in settings.AUTH_PASSWORD_VALIDATORS
        if v["NAME"].endswith("MinimumLengthValidator")
    )

    assert validador["OPTIONS"]["min_length"] == 10
