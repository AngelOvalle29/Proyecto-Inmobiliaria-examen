"""Pruebas de los endpoints de constructoras (spec 006, §9, nivel API)."""

import pytest
from rest_framework.test import APIClient

from apps.core.tests.factories import PaisFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/constructoras/"
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
NO_ESCRIBEN = [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]


def cliente_http(rol=None):
    http = APIClient()
    if rol is not None:
        http.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return http


def datos(pais, **cambios):
    base = {"nombre": "Constructora Demo", "nit": "8000001-1", "pais": pais.pk}
    base.update(cambios)
    return base


def test_sin_token_responde_401():
    assert cliente_http().get(URL).status_code == 401


@pytest.mark.parametrize("rol", ESCRIBEN)
def test_administracion_y_gerencia_crean(rol):
    respuesta = cliente_http(rol).post(URL, datos(PaisFactory()), format="json")

    assert respuesta.status_code == 201
    assert respuesta.json()["codigo"].startswith("CST-")
    assert respuesta.json()["calificacion"] is None


@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_no_escriben_y_solo_contabilidad_lee(rol):
    constructora = ConstructoraFactory()
    http = cliente_http(rol)
    # Spec 024, regla 1: de los que no escriben, solo contabilidad lee.
    lectura = 200 if rol == NombreRol.CONTABILIDAD else 403

    assert http.get(URL).status_code == lectura
    assert http.get(f"{URL}{constructora.pk}/").status_code == lectura
    assert http.post(URL, datos(PaisFactory()), format="json").status_code == 403
    assert http.patch(f"{URL}{constructora.pk}/", {"nombre": "X"}).status_code == 403
    assert http.delete(f"{URL}{constructora.pk}/").status_code == 403


@pytest.mark.parametrize("calificacion", [0, 6])
def test_una_calificacion_fuera_de_rango_responde_400(calificacion):
    respuesta = cliente_http(NombreRol.GERENTE).post(
        URL, datos(PaisFactory(), calificacion=calificacion), format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_sin_nit_responde_400():
    respuesta = cliente_http(NombreRol.GERENTE).post(
        URL, datos(PaisFactory(), nit=""), format="json"
    )

    assert respuesta.status_code == 400


def test_un_nit_repetido_responde_409():
    pais = PaisFactory()
    http = cliente_http(NombreRol.GERENTE)
    http.post(URL, datos(pais), format="json")

    respuesta = http.post(URL, datos(pais), format="json")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CONSTRUCTORA_DUPLICADA"


def test_delete_desactiva_y_deja_de_listarse():
    constructora = ConstructoraFactory()
    http = cliente_http(NombreRol.ADMINISTRADOR)

    assert http.delete(f"{URL}{constructora.pk}/").status_code == 204
    assert http.get(f"{URL}{constructora.pk}/").status_code == 404


def test_filtros_por_calificacion_minima_y_busqueda():
    buena = ConstructoraFactory(calificacion=5, nombre="Obras Buenas")
    ConstructoraFactory(calificacion=2)
    ConstructoraFactory(calificacion=None)
    http = cliente_http(NombreRol.CONTABILIDAD)

    def ids(parametros):
        return [c["id"] for c in http.get(URL, parametros).json()["results"]]

    assert ids({"calificacion_min": 4}) == [buena.pk]
    assert ids({"buscar": "obras buenas"}) == [buena.pk]
