"""
Pruebas del administrador inicial (spec 002, §5.8): el servicio
asegurar_administrador_inicial y el comando asegurar_administrador.
"""

from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Usuario
from apps.usuarios.services import asegurar_administrador_inicial

pytestmark = pytest.mark.django_db

DATOS = {
    "email": "admin@demo.test",
    "nombre_completo": "Administrador Demo",
    "password": "una-clave-de-prueba-larga",
}


@pytest.fixture
def variables_del_administrador(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", DATOS["email"])
    monkeypatch.setenv("DJANGO_SUPERUSER_NOMBRE_COMPLETO", DATOS["nombre_completo"])
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", DATOS["password"])


# ---------- servicio ----------


def test_crea_el_administrador_inicial_y_lo_audita():
    usuario = asegurar_administrador_inicial(**DATOS)

    assert usuario.is_superuser
    assert usuario.rol.nombre == NombreRol.ADMINISTRADOR
    assert usuario.check_password(DATOS["password"])
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.usuario is None
    assert registro.entidad_id == usuario.pk


def test_no_crea_otro_si_ya_existe_un_superusuario():
    """Idempotente: el arranque lo llama en cada despliegue."""
    asegurar_administrador_inicial(**DATOS)

    resultado = asegurar_administrador_inicial(
        email="otro@demo.test",
        nombre_completo="Otro Administrador",
        password="otra-clave-de-prueba-larga",
    )

    assert resultado is None
    assert Usuario.objects.filter(is_superuser=True).count() == 1


def test_rechaza_una_contrasena_debil():
    """Mismos validadores que el panel: no se crea con una contraseña corta."""
    with pytest.raises(ValidationError):
        asegurar_administrador_inicial(
            email="admin@demo.test",
            nombre_completo="Administrador Demo",
            password="corta",
        )

    assert not Usuario.objects.exists()


# ---------- comando ----------


def test_el_comando_crea_el_administrador_con_las_variables(
    variables_del_administrador,
):
    salida = StringIO()

    call_command("asegurar_administrador", stdout=salida)

    assert "Administrador inicial creado: admin@demo.test" in salida.getvalue()
    assert Usuario.objects.get(email="admin@demo.test").is_superuser


def test_el_comando_dos_veces_no_duplica(variables_del_administrador):
    call_command("asegurar_administrador", stdout=StringIO())
    salida = StringIO()

    call_command("asegurar_administrador", stdout=salida)

    assert "Ya existe un superusuario" in salida.getvalue()
    assert Usuario.objects.count() == 1


def test_sin_variables_el_comando_no_crea_nada(monkeypatch):
    """En desarrollo no existen: el administrador se crea con createsuperuser."""
    for nombre in (
        "DJANGO_SUPERUSER_EMAIL",
        "DJANGO_SUPERUSER_NOMBRE_COMPLETO",
        "DJANGO_SUPERUSER_PASSWORD",
    ):
        monkeypatch.delenv(nombre, raising=False)
    salida = StringIO()

    call_command("asegurar_administrador", stdout=salida)

    assert "no configurado" in salida.getvalue()
    assert not Usuario.objects.exists()
