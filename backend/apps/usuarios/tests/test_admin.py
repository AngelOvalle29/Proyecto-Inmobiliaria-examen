"""Pruebas del panel de usuarios: que respete la regla 3 al editar."""

import pytest

from apps.usuarios.admin import UsuarioEdicionForm
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


def test_el_panel_no_guarda_un_superusuario_sin_rol_administrador():
    usuario = UsuarioFactory()
    agente = Rol.objects.get(nombre=NombreRol.AGENTE)
    datos = {
        "email": usuario.email,
        "nombre_completo": usuario.nombre_completo,
        "rol": agente.pk,
        "is_active": True,
        "is_superuser": True,
        "date_joined": "2026-10-14 10:00:00",
    }

    formulario = UsuarioEdicionForm(data=datos, instance=usuario)

    assert not formulario.is_valid()
    assert "rol" in formulario.errors
