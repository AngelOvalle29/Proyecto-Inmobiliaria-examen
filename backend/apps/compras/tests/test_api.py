"""Pruebas de los endpoints de proveedores (spec 006, §9, nivel API).

Las reglas ya están probadas en los servicios. Aquí se prueba lo que solo
existe en la capa HTTP: quién puede llamar a qué, los filtros, el 404 de un
proveedor desactivado y el formato de los errores.
"""

import pytest
from rest_framework.test import APIClient

from apps.compras.enums import TipoProveedor
from apps.core.tests.factories import PaisFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ProveedorFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/proveedores/"
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
NO_ESCRIBEN = [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]


def cliente_http(rol=None):
    http = APIClient()
    if rol is not None:
        http.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return http


def datos_banco(pais, **cambios):
    datos = {
        "tipo": TipoProveedor.BANCO,
        "nombre": "Banco Demo",
        "nit": "1234567-8",
        "pais": pais.pk,
    }
    datos.update(cambios)
    return datos


def test_sin_token_responde_401():
    assert cliente_http().get(URL).status_code == 401


@pytest.mark.parametrize("rol", ESCRIBEN)
def test_administracion_y_gerencia_crean(rol):
    respuesta = cliente_http(rol).post(URL, datos_banco(PaisFactory()), format="json")

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["codigo"].startswith("PRV-")
    assert datos["nit"] == "12345678"
    assert datos["pais"]["nombre"]
    assert datos["ciudad"] is None


@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_leen_pero_no_escriben(rol):
    proveedor = ProveedorFactory()
    http = cliente_http(rol)

    assert http.get(URL).status_code == 200
    assert http.get(f"{URL}{proveedor.pk}/").status_code == 200
    assert http.post(URL, datos_banco(PaisFactory()), format="json").status_code == 403
    assert http.patch(f"{URL}{proveedor.pk}/", {"nombre": "X"}).status_code == 403
    assert http.delete(f"{URL}{proveedor.pk}/").status_code == 403


def test_un_banco_sin_nit_responde_400():
    respuesta = cliente_http(NombreRol.GERENTE).post(
        URL, datos_banco(PaisFactory(), nit=""), format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "NIT_OBLIGATORIO"


def test_un_nit_repetido_responde_409():
    pais = PaisFactory()
    http = cliente_http(NombreRol.GERENTE)
    http.post(URL, datos_banco(pais), format="json")

    respuesta = http.post(URL, datos_banco(pais, nit="12345678"), format="json")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROVEEDOR_DUPLICADO"


def test_patch_edita_y_no_cambia_el_codigo():
    proveedor = ProveedorFactory(codigo="PRV-0099")

    respuesta = cliente_http(NombreRol.GERENTE).patch(
        f"{URL}{proveedor.pk}/",
        {"nombre": "Nuevo nombre", "codigo": "PRV-9999"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Nuevo nombre"
    assert respuesta.json()["codigo"] == "PRV-0099"


def test_delete_desactiva_y_deja_de_listarse():
    proveedor = ProveedorFactory()
    http = cliente_http(NombreRol.ADMINISTRADOR)

    assert http.delete(f"{URL}{proveedor.pk}/").status_code == 204
    assert http.get(f"{URL}{proveedor.pk}/").status_code == 404
    assert http.get(URL).json()["count"] == 0


def test_filtros_por_tipo_pais_y_busqueda():
    pais = PaisFactory()
    banco = ProveedorFactory(pais=pais, nombre="Banco Uno", nit="1234567K")
    ProveedorFactory(tipo=TipoProveedor.GOBIERNO, nombre="Municipalidad")
    http = cliente_http(NombreRol.CONSULTA)

    def ids(parametros):
        return [p["id"] for p in http.get(URL, parametros).json()["results"]]

    assert ids({"tipo": "BANCO"}) == [banco.pk]
    assert ids({"pais": pais.pk}) == [banco.pk]
    assert ids({"buscar": "banco uno"}) == [banco.pk]
    # El NIT se busca normalizado: con guion y en minúscula también lo encuentra.
    assert ids({"buscar": "1234567-k"}) == [banco.pk]
