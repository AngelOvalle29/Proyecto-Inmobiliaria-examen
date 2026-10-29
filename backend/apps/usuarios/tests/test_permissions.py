"""
Pruebas de TieneRol (spec 004, §9).

Usan una vista de prueba que solo existe aquí, para probar el permiso sin
depender de los endpoints de ninguna app.
"""

import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.permissions import TieneRol

from .factories import UsuarioFactory

pytestmark = pytest.mark.django_db

fabrica = APIRequestFactory()


class VistaDePrueba(APIView):
    """Todos leen; solo administrador y gerente crean. DELETE no se declara."""

    permission_classes = [TieneRol]
    roles_por_metodo = {"POST": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]}

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})

    def delete(self, request):
        return Response({"ok": True})


class VistaSinDeclarar(APIView):
    """No declara roles_por_metodo: solo se puede leer."""

    permission_classes = [TieneRol]

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})


def usuario_con_rol(nombre: NombreRol):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


def llamar(vista, metodo: str, usuario=None):
    peticion = getattr(fabrica, metodo)("/prueba/")
    if usuario is not None:
        force_authenticate(peticion, user=usuario)
    return vista.as_view()(peticion)


@pytest.mark.parametrize("rol", [NombreRol.ADMINISTRADOR, NombreRol.GERENTE])
def test_permite_la_escritura_a_los_roles_declarados(rol):
    respuesta = llamar(VistaDePrueba, "post", usuario_con_rol(rol))

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "rol", [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]
)
def test_rechaza_la_escritura_a_los_roles_no_declarados(rol):
    respuesta = llamar(VistaDePrueba, "post", usuario_con_rol(rol))

    assert respuesta.status_code == 403
    assert respuesta.data["error"]["codigo"] == "SIN_PERMISO"


def test_un_get_no_declarado_queda_para_cualquier_autenticado():
    """CONSULTA es el rol con menos privilegios: si él puede leer, todos pueden."""
    respuesta = llamar(VistaDePrueba, "get", usuario_con_rol(NombreRol.CONSULTA))

    assert respuesta.status_code == 200


def test_una_escritura_no_declarada_se_rechaza_aunque_sea_administrador():
    """
    La vista solo declara POST. Olvidar DELETE lo deja cerrado para todos,
    incluido el administrador: cerrado por defecto, no abierto.
    """
    respuesta = llamar(
        VistaDePrueba, "delete", usuario_con_rol(NombreRol.ADMINISTRADOR)
    )

    assert respuesta.status_code == 403


def test_una_vista_sin_roles_declarados_solo_permite_leer():
    administrador = usuario_con_rol(NombreRol.ADMINISTRADOR)

    assert llamar(VistaSinDeclarar, "get", administrador).status_code == 200
    assert llamar(VistaSinDeclarar, "post", administrador).status_code == 403


def test_sin_autenticar_responde_401_y_no_403():
    """401 dice "identifíquese"; 403 diría "ya sé quién es y no puede"."""
    respuesta = llamar(VistaDePrueba, "get")

    assert respuesta.status_code == 401
    assert respuesta.data["error"]["codigo"] == "NO_AUTENTICADO"
