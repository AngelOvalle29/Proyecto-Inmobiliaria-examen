"""Pruebas del modelo de usuario, su manager y los roles (spec 001, reglas 1 a 3)."""

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CONTRASENA = "contrasena-de-prueba-123"


@pytest.fixture
def rol_agente():
    return Rol.objects.get(nombre=NombreRol.AGENTE)


def test_los_cinco_roles_existen_despues_de_migrar():
    """La migración de datos los crea; no hace falta ningún paso manual."""
    nombres = set(Rol.objects.values_list("nombre", flat=True))

    assert nombres == set(NombreRol.values)


def test_el_usuario_inicia_sesion_con_su_correo(rol_agente):
    """Regla 1."""
    usuario = Usuario.objects.create_user(
        email="agente@demo.test",
        password=CONTRASENA,
        nombre_completo="Agente Demo",
        rol=rol_agente,
    )

    autenticado = authenticate(email="agente@demo.test", password=CONTRASENA)

    assert autenticado == usuario


def test_el_correo_es_obligatorio(rol_agente):
    with pytest.raises(ValueError):
        Usuario.objects.create_user(
            email="", password=CONTRASENA, nombre_completo="Sin Correo", rol=rol_agente
        )


def test_el_rol_es_obligatorio():
    """Regla 2: exactamente un rol, nunca ninguno."""
    with pytest.raises(ValueError):
        Usuario.objects.create_user(
            email="sinrol@demo.test", password=CONTRASENA, nombre_completo="Sin Rol"
        )


def test_un_rol_con_usuarios_no_se_puede_borrar(rol_agente):
    """Regla 2."""
    Usuario.objects.create_user(
        email="agente@demo.test",
        password=CONTRASENA,
        nombre_completo="Agente Demo",
        rol=rol_agente,
    )

    with pytest.raises(ProtectedError):
        rol_agente.delete()


def test_create_superuser_asigna_el_rol_administrador():
    """Regla 3."""
    usuario = Usuario.objects.create_superuser(
        email="admin@demo.test", password=CONTRASENA, nombre_completo="Admin Demo"
    )

    assert usuario.rol.nombre == NombreRol.ADMINISTRADOR
    assert usuario.is_superuser
    assert usuario.is_staff


def test_create_superuser_ignora_un_rol_distinto(rol_agente):
    """Regla 3: aunque se pida otro rol, un superusuario es ADMINISTRADOR."""
    usuario = Usuario.objects.create_superuser(
        email="admin@demo.test",
        password=CONTRASENA,
        nombre_completo="Admin Demo",
        rol=rol_agente,
    )

    assert usuario.rol.nombre == NombreRol.ADMINISTRADOR


def test_el_comando_createsuperuser_funciona_sin_nombre_de_usuario():
    """Criterio de aceptación: pide correo y nombre completo, no username."""
    call_command(
        "createsuperuser",
        interactive=False,
        email="admin@demo.test",
        nombre_completo="Admin Demo",
        verbosity=0,
    )

    usuario = Usuario.objects.get(email="admin@demo.test")
    assert usuario.rol.nombre == NombreRol.ADMINISTRADOR


def test_una_contrasena_de_menos_de_diez_caracteres_se_rechaza():
    """
    arquitectura.md §9. validate_password es lo que usan createsuperuser y el
    formulario del panel antes de guardar una contraseña.
    """
    with pytest.raises(ValidationError):
        validate_password("Corta-9ch")

    validate_password("Diez-chars")  # 10 caracteres: se acepta


def test_el_correo_se_guarda_en_minusculas(rol_agente):
    """Regla 1: Ana@Demo.test y ana@demo.test son el mismo correo."""
    usuario = Usuario.objects.create_user(
        email="Ana@Demo.Test",
        password=CONTRASENA,
        nombre_completo="Agente Demo",
        rol=rol_agente,
    )

    assert usuario.email == "ana@demo.test"


def test_el_login_no_distingue_mayusculas_en_el_correo(rol_agente):
    usuario = Usuario.objects.create_user(
        email="agente@demo.test",
        password=CONTRASENA,
        nombre_completo="Agente Demo",
        rol=rol_agente,
    )

    autenticado = authenticate(email="AGENTE@demo.test", password=CONTRASENA)

    assert autenticado == usuario


def test_la_base_rechaza_el_mismo_correo_con_otras_mayusculas(rol_agente):
    """
    Aunque alguien salte el manager (un script, un update), la base no acepta
    dos cuentas con el mismo correo escrito distinto.
    """
    Usuario.objects.create_user(
        email="agente@demo.test",
        password=CONTRASENA,
        nombre_completo="Agente Demo",
        rol=rol_agente,
    )

    with pytest.raises(IntegrityError):
        Usuario(
            email="Agente@demo.test", nombre_completo="Copia", rol=rol_agente
        ).save()
