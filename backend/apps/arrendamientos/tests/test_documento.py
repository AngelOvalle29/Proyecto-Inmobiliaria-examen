"""Pruebas del documento de un arrendamiento (spec 008, reglas 17 y 18)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.arrendamientos.enums import EstadoArrendamiento
from apps.arrendamientos.models import ContratoArrendamiento
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

pytestmark = pytest.mark.django_db

CONTRATOS = "/api/v1/contratos-arrendamiento/"
HOY = timezone.localdate()


def http(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def datos_contrato(cliente, propiedad, **cambios):
    datos = {
        "cliente": cliente.pk,
        "propiedad": propiedad.pk,
        "fecha_inicio": (HOY + timedelta(days=1)).isoformat(),
        "duracion_meses": 6,
        "renta_mensual": "1000.00",
        "moneda": MonedaFactory(codigo="USD").pk,
        "dia_cobro": 5,
        "dias_gracia": 3,
        "porcentaje_mora": "5.00",
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def arrendamiento():
    """Un contrato firmado por la API, con su agente y su propiedad."""
    cliente = ClienteFactory()
    agente = cliente.agente_asignado.usuario
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)
    respuesta = http(agente).post(
        CONTRATOS, datos_contrato(cliente, propiedad), format="json"
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
        datos_contrato(cliente, propiedad, documento=documento.pk),
        format="json",
    )

    assert respuesta.status_code == 201, respuesta.json()
    assert respuesta.json()["documento"]["id"] == documento.pk


def test_un_documento_de_otra_propiedad_no_firma_ni_cambia_el_bien():
    cliente = ClienteFactory()
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)

    respuesta = http(cliente.agente_asignado.usuario).post(
        CONTRATOS,
        datos_contrato(cliente, propiedad, documento=DocumentoOficialFactory().pk),
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DOCUMENTO_DE_OTRA_PROPIEDAD"
    assert not ContratoArrendamiento.objects.exists()
    assert Propiedad.objects.get(pk=propiedad.pk).estado == EstadoPropiedad.DISPONIBLE


def test_una_unidad_acepta_el_documento_de_su_edificio():
    cliente = ClienteFactory()
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)
    documento = DocumentoOficialFactory(propiedad=unidad.propiedad)
    datos = datos_contrato(cliente, unidad.propiedad, documento=documento.pk)
    del datos["propiedad"]
    datos["unidad"] = unidad.pk

    respuesta = http(cliente.agente_asignado.usuario).post(
        CONTRATOS, datos, format="json"
    )

    assert respuesta.status_code == 201, respuesta.json()


def test_se_vincula_despues_y_queda_auditado(arrendamiento):
    contrato, agente, propiedad = arrendamiento
    documento = DocumentoOficialFactory(propiedad=propiedad)

    respuesta = vincular(agente, contrato["id"], documento.pk)

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["documento"]["id"] == documento.pk
    registro = LogAuditoria.objects.filter(
        entidad=ContratoArrendamiento._meta.db_table,
        accion=AccionAuditoria.ACTUALIZAR,
    ).latest("id")
    assert registro.valores_nuevos == {"documento": documento.pk}


def test_se_puede_cambiar_pero_no_quitar(arrendamiento):
    contrato, agente, propiedad = arrendamiento
    primero = DocumentoOficialFactory(propiedad=propiedad)
    segundo = DocumentoOficialFactory(propiedad=propiedad)
    vincular(agente, contrato["id"], primero.pk)

    assert vincular(agente, contrato["id"], segundo.pk).status_code == 200
    assert vincular(agente, contrato["id"], None).status_code == 400
    assert (
        ContratoArrendamiento.objects.get(pk=contrato["id"]).documento_id == segundo.pk
    )


def test_un_contrato_terminado_tambien_acepta_su_documento(arrendamiento):
    contrato, agente, propiedad = arrendamiento
    ContratoArrendamiento.objects.filter(pk=contrato["id"]).update(
        estado=EstadoArrendamiento.VENCIDO
    )
    documento = DocumentoOficialFactory(propiedad=propiedad)

    assert vincular(agente, contrato["id"], documento.pk).status_code == 200


def test_renovar_no_copia_el_documento(arrendamiento):
    contrato, agente, propiedad = arrendamiento
    documento = DocumentoOficialFactory(propiedad=propiedad)
    vincular(agente, contrato["id"], documento.pk)

    respuesta = http(agente).post(
        f"{CONTRATOS}{contrato['id']}/renovar/",
        {"renta_mensual": "1100.00", "duracion_meses": 6},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["documento"] is None


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_contabilidad_y_consulta_no_vinculan(arrendamiento, rol):
    contrato, _, propiedad = arrendamiento
    usuario = UsuarioFactory(rol=Rol.objects.get(nombre=rol))
    documento = DocumentoOficialFactory(propiedad=propiedad)

    assert vincular(usuario, contrato["id"], documento.pk).status_code == 403


def test_un_agente_no_vincula_en_un_contrato_ajeno(arrendamiento):
    contrato, _, propiedad = arrendamiento
    otro = ClienteFactory().agente_asignado.usuario
    documento = DocumentoOficialFactory(propiedad=propiedad)

    assert vincular(otro, contrato["id"], documento.pk).status_code == 404
