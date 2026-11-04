"""Pruebas del listado de usuarios, GET /api/v1/usuarios/ (spec 013)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.tests.factories import PaisFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol

from .factories import UsuarioFactory

pytestmark = pytest.mark.django_db

USUARIOS = "/api/v1/usuarios/"


def usuario_con_rol(rol: str, **campos):
    return UsuarioFactory(rol=Rol.objects.get(nombre=rol), **campos)


def cliente_con_rol(rol: str) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(usuario_con_rol(rol))
    return cliente


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


def correos(respuesta) -> list[str]:
    return [usuario["email"] for usuario in respuesta.json()["results"]]


# ---------- Permisos (regla 1) ----------


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [
        (NombreRol.ADMINISTRADOR, 200),
        (NombreRol.GERENTE, 200),
        (NombreRol.AGENTE, 403),
        (NombreRol.CONTABILIDAD, 403),
        (NombreRol.CONSULTA, 403),
    ],
)
def test_solo_administracion_y_gerencia_ven_el_listado(rol, esperado):
    assert cliente_con_rol(rol).get(USUARIOS).status_code == esperado


def test_sin_sesion_responde_401():
    assert APIClient().get(USUARIOS).status_code == 401


# ---------- Contenido (reglas 2 y 3) ----------


def test_omite_los_usuarios_desactivados(gerente):
    usuario_con_rol(NombreRol.AGENTE, email="activo@demo.test")
    usuario_con_rol(NombreRol.AGENTE, email="baja@demo.test", is_active=False)

    respuesta = gerente.get(USUARIOS, {"rol": "AGENTE"})

    assert correos(respuesta) == ["activo@demo.test"]


def test_devuelve_solo_los_datos_minimos(gerente):
    respuesta = gerente.get(USUARIOS)

    usuario = respuesta.json()["results"][0]
    # Sin teléfono ni último acceso; activo lo agregó la spec 026.
    assert set(usuario) == {"id", "email", "nombre_completo", "rol", "pais", "activo"}


def test_el_pais_puede_venir_nulo(gerente):
    usuario_con_rol(NombreRol.AGENTE, email="sin-pais@demo.test", pais=None)
    usuario_con_rol(
        NombreRol.AGENTE,
        email="con-pais@demo.test",
        pais=PaisFactory(nombre="Guatemala"),
    )

    respuesta = gerente.get(USUARIOS, {"rol": "AGENTE"})

    paises = {u["email"]: u["pais"] for u in respuesta.json()["results"]}
    assert paises["sin-pais@demo.test"] is None
    assert paises["con-pais@demo.test"]["nombre"] == "Guatemala"


# ---------- Filtros (regla 4) ----------


def test_filtra_por_rol(gerente):
    usuario_con_rol(NombreRol.AGENTE, email="agente@demo.test")
    usuario_con_rol(NombreRol.CONTABILIDAD, email="conta@demo.test")

    respuesta = gerente.get(USUARIOS, {"rol": "AGENTE"})

    assert correos(respuesta) == ["agente@demo.test"]


def test_un_rol_que_no_existe_responde_400(gerente):
    respuesta = gerente.get(USUARIOS, {"rol": "AGENT"})

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_busca_por_nombre_o_correo_sin_distinguir_mayusculas(gerente):
    usuario_con_rol(
        NombreRol.AGENTE, email="ana@demo.test", nombre_completo="Ana Demo Ventas"
    )
    usuario_con_rol(
        NombreRol.AGENTE, email="luis.ventas@demo.test", nombre_completo="Luis Demo"
    )
    usuario_con_rol(NombreRol.AGENTE, email="otro@demo.test", nombre_completo="Otro")

    respuesta = gerente.get(USUARIOS, {"rol": "AGENTE", "buscar": "VENTAS"})

    assert sorted(correos(respuesta)) == ["ana@demo.test", "luis.ventas@demo.test"]


def test_ordena_por_nombre_completo(gerente):
    usuario_con_rol(NombreRol.AGENTE, email="b@demo.test", nombre_completo="Beatriz")
    usuario_con_rol(NombreRol.AGENTE, email="a@demo.test", nombre_completo="Alberto")

    respuesta = gerente.get(USUARIOS, {"rol": "AGENTE"})

    assert correos(respuesta) == ["a@demo.test", "b@demo.test"]


# ---------- Consultas ----------


def test_el_listado_no_hace_una_consulta_por_usuario(gerente):
    """Rol y país vienen en la misma consulta (select_related)."""

    def consultas_del_listado() -> int:
        with CaptureQueriesContext(connection) as consultas:
            assert gerente.get(USUARIOS).status_code == 200
        return len(consultas)

    usuario_con_rol(NombreRol.AGENTE, pais=PaisFactory())
    con_pocos = consultas_del_listado()
    for _ in range(5):
        usuario_con_rol(NombreRol.AGENTE, pais=PaisFactory())

    assert consultas_del_listado() == con_pocos
