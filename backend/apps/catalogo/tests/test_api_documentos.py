"""Pruebas de los endpoints de documentos oficiales (spec 011)."""

from datetime import date

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import TipoDocumento
from apps.catalogo.models import TAMANO_MAXIMO_DOCUMENTO, DocumentoOficial
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import AvaluoFactory, DocumentoOficialFactory, PropiedadFactory

pytestmark = pytest.mark.django_db

PROPIEDADES = "/api/v1/propiedades/"
DOCUMENTOS = "/api/v1/documentos/"


def cliente_con_rol(rol: str) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return cliente


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


def archivo_pdf(
    nombre: str = "escritura.pdf", contenido: bytes = b"%PDF-1.4 demo"
) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


def datos_documento(**cambios) -> dict:
    datos = {
        "tipo": TipoDocumento.ESCRITURA,
        "nombre": "Escritura de la propiedad",
        "fecha_emision": "2025-01-10",
        "emisor": "Registro ficticio",
    }
    return {**datos, **cambios}


def subir(cliente: APIClient, propiedad, **cambios):
    datos = datos_documento(**cambios)
    datos["archivo"] = cambios.pop("archivo", archivo_pdf())
    return cliente.post(
        f"{PROPIEDADES}{propiedad.pk}/documentos/", datos, format="multipart"
    )


def test_sin_sesion_responde_401():
    documento = DocumentoOficialFactory()

    assert APIClient().get(f"{DOCUMENTOS}{documento.pk}/").status_code == 401


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
def test_subir_documento_por_rol(rol, esperado):
    propiedad = PropiedadFactory()

    respuesta = subir(cliente_con_rol(rol), propiedad)

    assert respuesta.status_code == esperado


@pytest.mark.parametrize("rol", list(NombreRol))
def test_todos_los_roles_leen_y_descargan_documentos(rol):
    documento = DocumentoOficialFactory()
    cliente = cliente_con_rol(rol)

    assert (
        cliente.get(f"{PROPIEDADES}{documento.propiedad.pk}/documentos/").status_code
        == 200
    )
    assert cliente.get(f"{DOCUMENTOS}{documento.pk}/").status_code == 200
    assert cliente.get(f"{DOCUMENTOS}{documento.pk}/descarga/").status_code == 200


@pytest.mark.parametrize(
    "rol", [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]
)
def test_los_roles_de_lectura_no_editan_ni_desactivan(rol):
    documento = DocumentoOficialFactory()
    cliente = cliente_con_rol(rol)

    assert (
        cliente.patch(
            f"{DOCUMENTOS}{documento.pk}/", {"nombre": "Otro"}, format="json"
        ).status_code
        == 403
    )
    assert cliente.delete(f"{DOCUMENTOS}{documento.pk}/").status_code == 403
    documento.refresh_from_db()
    assert documento.activo is True


def test_subir_y_listar_documentos_de_una_propiedad(gerente):
    propiedad = PropiedadFactory()
    contenido = b"%PDF-1.4 demo"

    creado = subir(gerente, propiedad, archivo=archivo_pdf(contenido=contenido))
    listado = gerente.get(f"{PROPIEDADES}{propiedad.pk}/documentos/")

    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["propiedad"] == {"id": propiedad.pk, "codigo": propiedad.codigo}
    assert cuerpo["tipo"] == TipoDocumento.ESCRITURA
    assert cuerpo["nombre_original"] == "escritura.pdf"
    assert cuerpo["tipo_contenido"] == "application/pdf"
    assert cuerpo["tamano_bytes"] == len(contenido)
    assert [d["id"] for d in listado.json()["results"]] == [cuerpo["id"]]
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.CREAR)
    assert registro.entidad == "catalogo_documentooficial"


def test_descarga_devuelve_url_y_cinco_minutos(gerente):
    documento = DocumentoOficialFactory()

    respuesta = gerente.get(f"{DOCUMENTOS}{documento.pk}/descarga/")

    assert respuesta.status_code == 200
    assert respuesta.json()["url"].startswith("http://testserver/media/")
    assert documento.archivo.name in respuesta.json()["url"]
    assert respuesta.json()["vence_en_segundos"] == 300


def test_un_ejecutable_renombrado_responde_400(gerente):
    datos = datos_documento()
    datos["archivo"] = SimpleUploadedFile("virus.pdf", b"MZ\x90\x00")

    respuesta = gerente.post(
        f"{PROPIEDADES}{PropiedadFactory().pk}/documentos/",
        datos,
        format="multipart",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ARCHIVO_NO_PERMITIDO"
    assert not DocumentoOficial.objects.exists()


def test_un_archivo_de_mas_de_diez_megas_responde_400(gerente):
    datos = datos_documento()
    datos["archivo"] = SimpleUploadedFile(
        "grande.pdf", b"x" * (TAMANO_MAXIMO_DOCUMENTO + 1)
    )

    respuesta = gerente.post(
        f"{PROPIEDADES}{PropiedadFactory().pk}/documentos/",
        datos,
        format="multipart",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ARCHIVO_NO_PERMITIDO"


def test_sin_archivo_responde_400(gerente):
    respuesta = gerente.post(
        f"{PROPIEDADES}{PropiedadFactory().pk}/documentos/",
        datos_documento(),
        format="multipart",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert "archivo" in respuesta.json()["error"]["detalles"]


def test_patch_solo_cambia_los_datos_editables(gerente):
    documento = DocumentoOficialFactory()

    respuesta = gerente.patch(
        f"{DOCUMENTOS}{documento.pk}/",
        {
            "nombre": "Escritura corregida",
            "emisor": "Notaría ficticia",
            "tipo": TipoDocumento.PLANO,
        },
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Escritura corregida"
    assert respuesta.json()["emisor"] == "Notaría ficticia"
    assert respuesta.json()["tipo"] == TipoDocumento.ESCRITURA
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ACTUALIZAR)
    assert set(registro.valores_nuevos) == {"nombre", "emisor"}


def test_patch_con_vencimiento_anterior_a_la_emision_responde_400(gerente):
    documento = DocumentoOficialFactory()

    respuesta = gerente.patch(
        f"{DOCUMENTOS}{documento.pk}/",
        {"fecha_emision": "2026-01-10", "fecha_vencimiento": "2026-01-09"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"
    assert "fecha_vencimiento" in respuesta.json()["error"]["detalles"]


def test_delete_desactiva_y_conserva_el_archivo(gerente):
    documento = subir(gerente, PropiedadFactory()).json()
    guardado = DocumentoOficial.objects.get(pk=documento["id"])
    ruta = guardado.archivo.name

    respuesta = gerente.delete(f"{DOCUMENTOS}{guardado.pk}/")

    assert respuesta.status_code == 204
    guardado.refresh_from_db()
    assert guardado.activo is False
    assert gerente.get(f"{DOCUMENTOS}{guardado.pk}/").status_code == 404
    assert default_storage.exists(ruta)
    registro = LogAuditoria.objects.get(
        accion=AccionAuditoria.ELIMINAR, entidad="catalogo_documentooficial"
    )
    assert registro.valores_nuevos == {"activo": False}


def test_no_se_desactiva_un_documento_en_uso(gerente):
    documento = DocumentoOficialFactory()
    AvaluoFactory(propiedad=documento.propiedad, documento=documento)

    respuesta = gerente.delete(f"{DOCUMENTOS}{documento.pk}/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DOCUMENTO_EN_USO"
    documento.refresh_from_db()
    assert documento.activo is True


def test_filtros_por_tipo_y_vencimiento(gerente):
    propiedad = PropiedadFactory()
    escritura = DocumentoOficialFactory(propiedad=propiedad)
    licencia = DocumentoOficialFactory(
        propiedad=propiedad,
        tipo=TipoDocumento.LICENCIA,
        fecha_vencimiento=date(2025, 12, 31),
    )
    sin_vencimiento = DocumentoOficialFactory(
        propiedad=propiedad, tipo=TipoDocumento.PLANO
    )

    def ids(parametros: str) -> list[int]:
        respuesta = gerente.get(f"{PROPIEDADES}{propiedad.pk}/documentos/{parametros}")
        return [d["id"] for d in respuesta.json()["results"]]

    assert ids("?tipo=LICENCIA") == [licencia.pk]
    assert ids("?vence_antes=2026-01-01") == [licencia.pk]
    assert set(ids("")) == {escritura.pk, licencia.pk, sin_vencimiento.pk}

    invalido = gerente.get(f"{PROPIEDADES}{propiedad.pk}/documentos/?tipo=INVENTADO")
    assert invalido.status_code == 400
    assert invalido.json()["error"]["codigo"] == "VALIDACION"
