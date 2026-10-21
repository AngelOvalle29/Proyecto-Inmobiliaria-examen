"""
Pruebas de los settings de producción (spec 002, §5.2).

Django carga los settings una sola vez por proceso, y las pruebas ya corren con
config.settings.test. Por eso prod.py se carga en un proceso aparte, con las
variables de entorno de cada caso, y ese proceso imprime lo que la prueba
necesita revisar.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

LEER_SETTINGS = """
import json
import django
from django.conf import settings

django.setup()
print(json.dumps({
    "DEBUG": settings.DEBUG,
    "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
    "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
    "STATICFILES": settings.STORAGES["staticfiles"]["BACKEND"],
    "CONN_MAX_AGE": settings.DATABASES["default"]["CONN_MAX_AGE"],
}))
"""


def cargar_settings_prod(**variables: str) -> subprocess.CompletedProcess:
    entorno = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "clave-solo-para-pruebas",
        "DATABASE_URL": "postgresql://usuario:clave@localhost:5432/prueba",
        # Vacías por defecto: si no, se leerían del .env local de cada
        # integrante y la prueba dependería de su máquina.
        "ALLOWED_HOSTS": "",
        "RENDER_EXTERNAL_HOSTNAME": "",
        **variables,
    }
    return subprocess.run(
        [sys.executable, "-c", LEER_SETTINGS],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )


def test_agrega_el_dominio_que_expone_render():
    """Render llama a la ruta de salud con este host (spec 002, §5.1)."""
    resultado = cargar_settings_prod(RENDER_EXTERNAL_HOSTNAME="api-demo.onrender.com")

    assert resultado.returncode == 0, resultado.stderr
    settings = json.loads(resultado.stdout)
    assert settings["ALLOWED_HOSTS"] == ["api-demo.onrender.com"]


def test_sin_ningun_host_no_arranca():
    """Con la lista vacía, Django rechazaría todo sin explicar por qué."""
    resultado = cargar_settings_prod()

    assert resultado.returncode != 0
    assert "ALLOWED_HOSTS está vacía" in resultado.stderr


def test_queda_configurado_para_correr_detras_del_proxy():
    resultado = cargar_settings_prod(RENDER_EXTERNAL_HOSTNAME="api-demo.onrender.com")

    settings = json.loads(resultado.stdout)
    assert settings["DEBUG"] is False
    assert settings["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert settings["STATICFILES"].startswith("whitenoise.")
    assert settings["CONN_MAX_AGE"] == 60
