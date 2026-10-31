"""Pruebas de los endpoints de avalúos (spec 011)."""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.models import Avaluo
from apps.core.tests.factories import MonedaFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import AvaluoFactory, DocumentoOficialFactory, PropiedadFactory

pytestmark = pytest.mark.django_db

PROPIEDADES = "/api/v1/propiedades/"
AVALUOS = "/api/v1/avaluos/"


def cliente_con_rol(rol: str) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return cliente


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


def datos_avaluo(**cambios) -> dict:
    datos = {
        "fecha": "2025-05-01",
        "valor": "250000.00",
        "moneda_id": MonedaFactory(codigo="USD").pk,
        "perito": "Perito de prueba",
        "metodologia": "Comparativo de mercado",
        "observaciones": "Avalúo de prueba.",
    }
    return {**datos, **cambios}


def test_sin_sesion_responde_401():
    avaluo = AvaluoFactory()

    assert APIClient().get(f"{AVALUOS}{avaluo.pk}/").status_code == 401


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [
        (NombreRol.ADMINISTRADOR, 201),
        (NombreRol.GERENTE, 201),
        (NombreRol.AGENTE, 403),
        (NombreRol.CONTABILIDAD, 403),
        (NombreRol.CONSULTA, 403),
    ],
)
def test_registrar_avaluo_por_rol(rol, esperado):
    propiedad = PropiedadFactory()

    respuesta = cliente_con_rol(rol).post(
        f"{PROPIEDADES}{propiedad.pk}/avaluos/", datos_avaluo(), format="json"
    )

    assert respuesta.status_code == esperado


@pytest.mark.parametrize("rol", list(NombreRol))
def test_todos_los_roles_leen_avaluos(rol):
    avaluo = AvaluoFactory()
    cliente = cliente_con_rol(rol)

    assert (
        cliente.get(f"{PROPIEDADES}{avaluo.propiedad.pk}/avaluos/").status_code == 200
    )
    assert cliente.get(f"{AVALUOS}{avaluo.pk}/").status_code == 200


def test_registrar_y_listar_avaluos_de_una_propiedad(gerente):
    propiedad = PropiedadFactory()
    url = f"{PROPIEDADES}{propiedad.pk}/avaluos/"

    creado = gerente.post(url, datos_avaluo(), format="json")
    listado = gerente.get(url)

    assert creado.status_code == 201
    assert creado.json()["propiedad"] == {
        "id": propiedad.pk,
        "codigo": propiedad.codigo,
    }
    assert creado.json()["valor"] == "250000.00"
    assert [a["id"] for a in listado.json()["results"]] == [creado.json()["id"]]
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.entidad == "catalogo_avaluo"


def test_el_historial_va_del_mas_reciente_al_mas_antiguo(gerente):
    propiedad = PropiedadFactory()
    viejo = AvaluoFactory(propiedad=propiedad, fecha=date(2025, 1, 10))
    nuevo = AvaluoFactory(propiedad=propiedad, fecha=date(2026, 1, 10))

    respuesta = gerente.get(f"{PROPIEDADES}{propiedad.pk}/avaluos/")

    assert [a["id"] for a in respuesta.json()["results"]] == [nuevo.pk, viejo.pk]


def test_una_fecha_futura_responde_400(gerente):
    propiedad = PropiedadFactory()

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/avaluos/",
        datos_avaluo(fecha="2999-01-01"),
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert "fecha" in respuesta.json()["error"]["detalles"]
    assert not Avaluo.objects.exists()


def test_un_valor_cero_responde_400(gerente):
    propiedad = PropiedadFactory()

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/avaluos/",
        datos_avaluo(valor="0.00"),
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert "valor" in respuesta.json()["error"]["detalles"]
    assert not Avaluo.objects.exists()


def test_un_documento_de_otra_propiedad_responde_409(gerente):
    propiedad = PropiedadFactory()
    documento = DocumentoOficialFactory(propiedad=PropiedadFactory())

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/avaluos/",
        datos_avaluo(documento_id=documento.pk),
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DOCUMENTO_DE_OTRA_PROPIEDAD"
    assert not Avaluo.objects.exists()


def test_un_documento_de_la_misma_propiedad_se_acepta(gerente):
    propiedad = PropiedadFactory()
    documento = DocumentoOficialFactory(propiedad=propiedad)

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/avaluos/",
        datos_avaluo(documento_id=documento.pk),
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["documento"] == {
        "id": documento.pk,
        "nombre": documento.nombre,
        "tipo": documento.tipo,
    }


def test_un_avaluo_no_se_edita(gerente):
    """La ruta solo expone GET y DELETE: PATCH y PUT quedan sin permiso."""
    avaluo = AvaluoFactory()

    assert (
        gerente.patch(
            f"{AVALUOS}{avaluo.pk}/", {"valor": "1.00"}, format="json"
        ).status_code
        == 403
    )
    assert (
        gerente.put(f"{AVALUOS}{avaluo.pk}/", datos_avaluo(), format="json").status_code
        == 403
    )


def test_delete_desactiva_el_avaluo(gerente):
    avaluo = AvaluoFactory()

    respuesta = gerente.delete(f"{AVALUOS}{avaluo.pk}/")

    assert respuesta.status_code == 204
    avaluo.refresh_from_db()
    assert avaluo.activo is False
    assert gerente.get(f"{AVALUOS}{avaluo.pk}/").status_code == 404
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ELIMINAR)
    assert registro.valores_anteriores == {"activo": True}
    assert registro.valores_nuevos == {"activo": False}


def test_avaluos_de_una_propiedad_inexistente_responde_404(gerente):
    assert gerente.get(f"{PROPIEDADES}999999/avaluos/").status_code == 404
