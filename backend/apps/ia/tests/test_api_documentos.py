"""Pruebas de /api/v1/documentos-agente/ (spec 020, §5).

La tarea no se ejecuta: se anota qué documentos se encolaron.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests.factories import PaisFactory
from apps.ia.enums import EstadoIndexacion
from apps.ia.models import DocumentoRAG
from apps.ia.services import crear_documento_rag, indexar_documento
from apps.ia.tasks import indexar_documento_tarea
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

DOCUMENTOS = "/api/v1/documentos-agente/"
TEXTO = "## Requisitos\nDPI vigente.\n\n## Pagos\nTransferencia."


class ClienteQueConfirma(APIClient):
    """En las pruebas la transacción nunca se confirma, así que los on_commit
    quedan esperando. Este cliente los ejecuta al terminar cada petición, como
    pasaría en producción con el commit real."""

    def request(self, **kwargs):
        with TestCase.captureOnCommitCallbacks(execute=True):
            return super().request(**kwargs)


def cliente_con_rol(rol: str) -> APIClient:
    cliente = ClienteQueConfirma()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return cliente


def archivo(texto=TEXTO, nombre="politica.md"):
    return SimpleUploadedFile(
        nombre, texto.encode("utf-8"), content_type="text/markdown"
    )


def datos(**cambios):
    base = {
        "archivo": archivo(),
        "titulo": "Política de comisiones",
        "tipo": "POLITICA",
    }
    base.update(cambios)
    return base


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


@pytest.fixture
def encolados(monkeypatch):
    """Anota los ids encolados en vez de ejecutar la tarea."""
    ids: list[int] = []
    monkeypatch.setattr(indexar_documento_tarea, "delay", ids.append)
    return ids


def test_subir_responde_201_pendiente_y_encola(gerente, encolados):
    respuesta = gerente.post(DOCUMENTOS, datos(), format="multipart")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado_indexacion"] == "PENDIENTE"
    assert cuerpo["version"] == 1
    assert cuerpo["fragmentos"] == 0
    assert cuerpo["pais"] is None
    assert encolados == [cuerpo["id"]]


def test_subir_con_pais(gerente, encolados):
    pais = PaisFactory()

    respuesta = gerente.post(DOCUMENTOS, datos(pais=pais.id), format="multipart")

    assert respuesta.status_code == 201
    assert respuesta.json()["pais"] == {"id": pais.id, "nombre": pais.nombre}


def test_un_archivo_que_no_es_markdown_responde_400(gerente, encolados):
    respuesta = gerente.post(
        DOCUMENTOS, datos(archivo=archivo(nombre="politica.pdf")), format="multipart"
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ARCHIVO_NO_PERMITIDO"
    assert encolados == []


def test_un_titulo_repetido_responde_409(gerente, encolados):
    gerente.post(DOCUMENTOS, datos(), format="multipart")

    respuesta = gerente.post(DOCUMENTOS, datos(), format="multipart")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "DOCUMENTO_RAG_DUPLICADO"


def test_la_lista_trae_el_estado_y_los_fragmentos(gerente, proveedor_falso):
    indexado = crear_documento_rag(
        titulo="A indexado", tipo="MANUAL", contenido_fuente=TEXTO
    )
    indexar_documento(documento_id=indexado.id)
    crear_documento_rag(titulo="B pendiente", tipo="MANUAL", contenido_fuente=TEXTO)

    respuesta = gerente.get(DOCUMENTOS)

    filas = respuesta.json()["results"]
    assert [(f["titulo"], f["estado_indexacion"], f["fragmentos"]) for f in filas] == [
        ("A indexado", "INDEXADO", 2),
        ("B pendiente", "PENDIENTE", 0),
    ]


def test_filtrar_por_estado(gerente):
    crear_documento_rag(titulo="Pendiente", tipo="MANUAL", contenido_fuente=TEXTO)
    error = crear_documento_rag(
        titulo="Con error", tipo="MANUAL", contenido_fuente=TEXTO
    )
    DocumentoRAG.objects.filter(pk=error.pk).update(
        estado_indexacion=EstadoIndexacion.ERROR
    )

    respuesta = gerente.get(DOCUMENTOS, {"estado_indexacion": "ERROR"})

    assert [f["titulo"] for f in respuesta.json()["results"]] == ["Con error"]


def test_reemplazar_sube_la_version_y_encola(gerente, encolados):
    documento = gerente.post(DOCUMENTOS, datos(), format="multipart").json()
    encolados.clear()

    respuesta = gerente.patch(
        f"{DOCUMENTOS}{documento['id']}/",
        {"archivo": archivo("## Otra\nVersión nueva.")},
        format="multipart",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["version"] == 2
    assert encolados == [documento["id"]]


def test_reindexar_responde_202_en_cualquier_estado(gerente, encolados):
    documento = crear_documento_rag(
        titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO
    )

    respuesta = gerente.post(f"{DOCUMENTOS}{documento.id}/reindexar/")

    assert respuesta.status_code == 202
    assert respuesta.json()["estado_indexacion"] == "PENDIENTE"
    assert encolados == [documento.id]


def test_desactivar_lo_saca_de_la_lista(gerente, encolados):
    documento = crear_documento_rag(
        titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO
    )

    respuesta = gerente.delete(f"{DOCUMENTOS}{documento.id}/")

    assert respuesta.status_code == 204
    assert gerente.get(DOCUMENTOS).json()["count"] == 0
    assert gerente.get(f"{DOCUMENTOS}{documento.id}/").status_code == 404


@pytest.mark.parametrize(
    "rol", [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]
)
def test_los_demas_roles_no_leen_ni_escriben(rol, encolados):
    """Regla 14: solo administración y gerencia, también para leer."""
    cliente = cliente_con_rol(rol)
    documento = crear_documento_rag(
        titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO
    )

    assert cliente.get(DOCUMENTOS).status_code == 403
    assert cliente.post(DOCUMENTOS, datos(), format="multipart").status_code == 403
    assert cliente.post(f"{DOCUMENTOS}{documento.id}/reindexar/").status_code == 403
    assert cliente.delete(f"{DOCUMENTOS}{documento.id}/").status_code == 403
    assert encolados == []


def test_sin_sesion_responde_401():
    assert APIClient().get(DOCUMENTOS).status_code == 401
