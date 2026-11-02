"""Pruebas del documento de un contrato de venta (spec 007, reglas 23 y 24)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.models import Propiedad
from apps.catalogo.tests.factories import (
    DocumentoOficialFactory,
    PropiedadFactory,
    UnidadFactory,
)
from apps.core.tests.factories import MonedaFactory
from apps.crm.tests.factories import ClienteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory
from apps.ventas.enums import EstadoContrato
from apps.ventas.models import ContratoVenta

pytestmark = pytest.mark.django_db

CONTRATOS = "/api/v1/contratos-venta/"
HOY = timezone.localdate()


def http(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def datos_venta(cliente, propiedad, **cambios):
    datos = {
        "cliente": cliente.pk,
        "propiedad": propiedad.pk,
        "monto_total": "120000.00",
        "moneda": MonedaFactory(codigo="USD").pk,
        "fecha_firma": HOY.isoformat(),
        "modalidad": "FINANCIADO",
        "numero_cuotas": 12,
        "tasa_interes_anual": "9.00",
        "fecha_primera_cuota": (HOY + timedelta(days=30)).isoformat(),
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def venta():
    """Un contrato firmado por la API, con su agente y su propiedad."""
    cliente = ClienteFactory()
    agente = cliente.agente_asignado.usuario
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)
    respuesta = http(agente).post(
        CONTRATOS, datos_venta(cliente, propiedad), format="json"
    )
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json(), agente, propiedad


def vincular(usuario, contrato_id, documento_id):
    return http(usuario).post(
        f"{CONTRATOS}{contrato_id}/documento/",
        {"documento": documento_id},
        format="json",
    )


def test_se_firma_con_un_documento_de_la_misma_propiedad():
    cliente = ClienteFactory()
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)
    documento = DocumentoOficialFactory(propiedad=propiedad)

    respuesta = http(cliente.agente_asignado.usuario).post(
        CONTRATOS,
        datos_venta(cliente, propiedad, documento=documento.pk),
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.json()
    assert respuesta.json()["documento"]["id"] == documento.pk


def test_sin_documento_el_contrato_se_firma_igual(venta):
    contrato, _, _ = venta
    assert contrato["documento"] is None


def test_un_documento_de_otra_propiedad_no_firma_ni_cambia_el_bien():
    cliente = ClienteFactory()
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)
    ajeno = DocumentoOficialFactory()

    respuesta = http(cliente.agente_asignado.usuario).post(
        CONTRATOS, datos_venta(cliente, propiedad, documento=ajeno.pk), format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DOCUMENTO_DE_OTRA_PROPIEDAD"
    assert not ContratoVenta.objects.exists()
    assert Propiedad.objects.get(pk=propiedad.pk).estado == EstadoPropiedad.DISPONIBLE


def test_una_unidad_acepta_el_documento_de_su_edificio():
    cliente = ClienteFactory()
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)
    documento = DocumentoOficialFactory(propiedad=unidad.propiedad)
    datos = datos_venta(cliente, unidad.propiedad, documento=documento.pk)
    del datos["propiedad"]
    datos["unidad"] = unidad.pk

    respuesta = http(cliente.agente_asignado.usuario).post(
        CONTRATOS, datos, format="json"
    )

    assert respuesta.status_code == 201, respuesta.json()
    assert respuesta.json()["documento"]["id"] == documento.pk


def test_se_vincula_despues_de_firmar_y_queda_auditado(venta):
    contrato, agente, propiedad = venta
    documento = DocumentoOficialFactory(propiedad=propiedad)

    respuesta = vincular(agente, contrato["id"], documento.pk)

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["documento"]["nombre"] == documento.nombre
    registro = LogAuditoria.objects.filter(
        entidad=ContratoVenta._meta.db_table, accion=AccionAuditoria.ACTUALIZAR
    ).latest("id")
    assert registro.valores_anteriores == {"documento": None}
    assert registro.valores_nuevos == {"documento": documento.pk}


def test_se_puede_cambiar_por_otro_documento(venta):
    contrato, agente, propiedad = venta
    primero = DocumentoOficialFactory(propiedad=propiedad)
    segundo = DocumentoOficialFactory(propiedad=propiedad)
    vincular(agente, contrato["id"], primero.pk)

    respuesta = vincular(agente, contrato["id"], segundo.pk)

    assert respuesta.json()["documento"]["id"] == segundo.pk


def test_el_mismo_documento_no_se_audita_otra_vez(venta):
    contrato, agente, propiedad = venta
    documento = DocumentoOficialFactory(propiedad=propiedad)
    vincular(agente, contrato["id"], documento.pk)
    registros = LogAuditoria.objects.count()

    respuesta = vincular(agente, contrato["id"], documento.pk)

    assert respuesta.status_code == 200
    assert LogAuditoria.objects.count() == registros


def test_no_se_puede_quitar_el_documento(venta):
    contrato, agente, propiedad = venta
    documento = DocumentoOficialFactory(propiedad=propiedad)
    vincular(agente, contrato["id"], documento.pk)

    respuesta = vincular(agente, contrato["id"], None)

    assert respuesta.status_code == 400
    assert ContratoVenta.objects.get(pk=contrato["id"]).documento_id == documento.pk


def test_un_documento_desactivado_no_se_vincula(venta):
    contrato, agente, propiedad = venta
    documento = DocumentoOficialFactory(propiedad=propiedad, activo=False)

    assert vincular(agente, contrato["id"], documento.pk).status_code == 400


def test_un_documento_de_otra_propiedad_no_se_vincula(venta):
    contrato, agente, _ = venta

    respuesta = vincular(agente, contrato["id"], DocumentoOficialFactory().pk)

    assert respuesta.status_code == 409


def test_un_contrato_anulado_no_cambia_y_uno_liquidado_si(venta):
    contrato, agente, propiedad = venta
    documento = DocumentoOficialFactory(propiedad=propiedad)
    guardado = ContratoVenta.objects.get(pk=contrato["id"])

    guardado.estado = EstadoContrato.ANULADO
    guardado.save(update_fields=["estado"])
    respuesta = vincular(agente, contrato["id"], documento.pk)
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CONTRATO_NO_VIGENTE"

    guardado.estado = EstadoContrato.LIQUIDADO
    guardado.save(update_fields=["estado"])
    assert vincular(agente, contrato["id"], documento.pk).status_code == 200


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_contabilidad_y_consulta_no_vinculan(venta, rol):
    contrato, _, propiedad = venta
    usuario = UsuarioFactory(rol=Rol.objects.get(nombre=rol))
    documento = DocumentoOficialFactory(propiedad=propiedad)

    assert vincular(usuario, contrato["id"], documento.pk).status_code == 403


def test_un_agente_no_vincula_en_un_contrato_ajeno(venta):
    contrato, _, propiedad = venta
    otro = ClienteFactory().agente_asignado.usuario
    documento = DocumentoOficialFactory(propiedad=propiedad)

    assert vincular(otro, contrato["id"], documento.pk).status_code == 404
