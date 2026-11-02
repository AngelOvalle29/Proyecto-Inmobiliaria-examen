"""Pruebas de los endpoints de contratos de compra (spec 017, §9, nivel API).

Las reglas ya están probadas en los servicios (test_contratos.py). Aquí se
prueba lo que solo existe en la capa HTTP: la matriz de permisos, un caso feliz
por acción, la validación de entrada y el formato de los errores.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.compras.enums import EstadoContratoCompra
from apps.core.tests.factories import MonedaFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ProveedorFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/contratos-compra/"
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
NO_ESCRIBEN = [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]


def cliente_http(rol=NombreRol.GERENTE):
    http = APIClient()
    http.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return http


def datos(**cambios):
    base = {
        "proveedor": ProveedorFactory().pk,
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.EN_NEGOCIACION).pk,
        "fecha_compra": timezone.localdate().isoformat(),
        "monto": "850000.00",
        "gastos_legales": "12000.00",
        "impuestos": "25500.00",
        "moneda": MonedaFactory(codigo="USD").pk,
    }
    base.update(cambios)
    return base


def registrar(http=None, **cambios):
    return (http or cliente_http()).post(URL, datos(**cambios), format="json")


def test_sin_token_responde_401():
    assert APIClient().get(URL).status_code == 401


@pytest.mark.parametrize("rol", ESCRIBEN)
def test_administracion_y_gerencia_registran(rol):
    respuesta = registrar(cliente_http(rol))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["codigo"].startswith("CC-")
    assert cuerpo["estado"] == EstadoContratoCompra.EN_PROCESO
    assert Decimal(cuerpo["costo_total"]) == Decimal("887500.00")
    assert cuerpo["proveedor"]["codigo"]
    assert cuerpo["moneda"]["codigo"] == "USD"


@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_leen_pero_no_registran(rol):
    http = cliente_http(rol)
    assert http.get(URL).status_code == 200
    assert registrar(http).status_code == 403


def test_costo_total_no_se_recibe_lo_calcula_el_sistema():
    respuesta = registrar(costo_total="1.00")
    assert Decimal(respuesta.json()["costo_total"]) == Decimal("887500.00")


def test_un_monto_cero_responde_400_junto_al_campo():
    respuesta = registrar(monto="0")

    assert respuesta.status_code == 400
    assert "monto" in respuesta.json()["error"]["detalles"]


def test_un_proveedor_desactivado_responde_400():
    """Regla 1: solo se compra a un proveedor activo."""
    proveedor = ProveedorFactory(activo=False)
    assert registrar(proveedor=proveedor.pk).status_code == 400


def test_una_propiedad_que_no_esta_en_negociacion_responde_409():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)

    respuesta = registrar(propiedad=propiedad.pk)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROPIEDAD_NO_DISPONIBLE"


def test_un_segundo_contrato_sobre_la_misma_propiedad_responde_409():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.EN_NEGOCIACION)
    registrar(propiedad=propiedad.pk)

    respuesta = registrar(propiedad=propiedad.pk)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROPIEDAD_CON_CONTRATO"


def test_completar_responde_el_contrato_completado():
    http = cliente_http()
    contrato = registrar(http).json()

    respuesta = http.post(f"{URL}{contrato['id']}/completar/")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoContratoCompra.COMPLETADO


def test_completar_otra_vez_responde_409():
    http = cliente_http()
    contrato = registrar(http).json()
    http.post(f"{URL}{contrato['id']}/completar/")

    respuesta = http.post(f"{URL}{contrato['id']}/completar/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TRANSICION_INVALIDA"


def test_anular_sin_motivo_responde_400():
    http = cliente_http()
    contrato = registrar(http).json()

    respuesta = http.post(f"{URL}{contrato['id']}/anular/", {}, format="json")

    assert respuesta.status_code == 400
    assert "motivo" in respuesta.json()["error"]["detalles"]


def test_anular_con_motivo_responde_el_contrato_anulado():
    http = cliente_http()
    contrato = registrar(http).json()

    respuesta = http.post(
        f"{URL}{contrato['id']}/anular/", {"motivo": "Error en el monto"}, format="json"
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoContratoCompra.ANULADO


@pytest.mark.parametrize("accion", ["completar", "anular"])
@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_no_completan_ni_anulan(rol, accion):
    contrato = registrar().json()

    respuesta = cliente_http(rol).post(
        f"{URL}{contrato['id']}/{accion}/", {"motivo": "x"}, format="json"
    )

    assert respuesta.status_code == 403


def test_detalle_y_filtro_por_estado():
    http = cliente_http()
    en_proceso = registrar(http).json()
    completado = registrar(http).json()
    http.post(f"{URL}{completado['id']}/completar/")

    assert (
        http.get(f"{URL}{en_proceso['id']}/").json()["codigo"] == en_proceso["codigo"]
    )
    ids = [c["id"] for c in http.get(URL, {"estado": "COMPLETADO"}).json()["results"]]
    assert ids == [completado["id"]]


def test_desactivar_un_proveedor_con_un_contrato_en_proceso_responde_409():
    """Regla 22, por la API de proveedores de la spec 006."""
    http = cliente_http()
    contrato = registrar(http).json()

    respuesta = http.delete(f"/api/v1/proveedores/{contrato['proveedor']['id']}/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROVEEDOR_CON_CONTRATOS"
