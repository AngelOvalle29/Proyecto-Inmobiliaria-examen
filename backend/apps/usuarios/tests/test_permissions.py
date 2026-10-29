"""Pruebas de TieneRol (spec 004, §9)."""

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.permissions import TieneRol

from .factories import UsuarioFactory

pytestmark = pytest.mark.django_db

fabrica = APIRequestFactory()


class VistaDePrueba(APIView):
    """Solo declara POST, como una vista que crea pero no borra."""

    roles_por_metodo = {"POST": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]}


def _permite(metodo: str, rol: str | None) -> bool:
    peticion = getattr(fabrica, metodo.lower())("/")
    if rol is None:
        peticion.user = AnonymousUser()
    else:
        peticion.user = UsuarioFactory(rol=Rol.objects.get(nombre=rol))
    return TieneRol().has_permission(peticion, VistaDePrueba())


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [
        (NombreRol.ADMINISTRADOR, True),
        (NombreRol.GERENTE, True),
        (NombreRol.AGENTE, False),
        (NombreRol.CONTABILIDAD, False),
        (NombreRol.CONSULTA, False),
    ],
)
def test_metodo_declarado_solo_para_sus_roles(rol, esperado):
    assert _permite("POST", rol) is esperado


def test_get_no_declarado_queda_para_cualquier_autenticado():
    assert _permite("GET", NombreRol.CONSULTA)


def test_escritura_no_declarada_se_rechaza_aunque_sea_administrador():
    assert not _permite("DELETE", NombreRol.ADMINISTRADOR)


def test_sin_sesion_se_rechaza():
    assert not _permite("GET", None)
