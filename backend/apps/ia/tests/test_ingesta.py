"""Pruebas de la ingesta por la cola de RabbitMQ (spec 020).

Las pruebas corren Celery en modo eager (config/settings/test.py): la tarea se
ejecuta en el mismo proceso, sin RabbitMQ. Nunca llaman a Gemini.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.auditoria.models import LogAuditoria
from apps.ia.enums import EstadoIndexacion
from apps.ia.exceptions import ArchivoRAGNoPermitido
from apps.ia.models import DocumentoRAG, FragmentoRAG
from apps.ia.services import (
    ENTIDAD_DOCUMENTO,
    TAMANO_MAXIMO_MARKDOWN,
    crear_documento_rag,
    desactivar_documento_rag,
    indexar_documento,
    reemplazar_documento_rag,
    reindexar_documento_rag,
    subir_documento_rag,
)
from apps.ia.tasks import REINTENTOS, indexar_documento_tarea
from apps.usuarios.tests.factories import UsuarioFactory
from config.celery import app

pytestmark = pytest.mark.django_db

TEXTO = "## Requisitos\nDPI vigente.\n\n## Pagos\nTransferencia."
OTRO_TEXTO = "## Requisitos\nDPI y pasaporte.\n\n## Pagos\nCheque."


def archivo(texto=TEXTO, nombre="politica.md"):
    return SimpleUploadedFile(
        nombre, texto.encode("utf-8"), content_type="text/markdown"
    )


def subir(autor, titulo="Política de comisiones", texto=TEXTO):
    return subir_documento_rag(
        archivo=archivo(texto),
        titulo=titulo,
        tipo="POLITICA",
        pais=None,
        autor=autor,
        ip="10.0.0.1",
    )


@pytest.fixture
def autor():
    return UsuarioFactory()


@pytest.fixture
def encolados(monkeypatch):
    """Anota los ids encolados en vez de ejecutar la tarea."""
    ids: list[int] = []
    monkeypatch.setattr(indexar_documento_tarea, "delay", ids.append)
    return ids


# ---------- Subir y reemplazar ----------


def test_subir_deja_pendiente_y_encola_despues_del_commit(
    autor, encolados, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=False) as pendientes:
        documento = subir(autor)

    assert documento.estado_indexacion == EstadoIndexacion.PENDIENTE
    # Regla 4: nada se encola hasta que la transacción se confirma.
    assert encolados == []
    assert len(pendientes) == 1
    pendientes[0]()
    assert encolados == [documento.id]


def test_si_la_transaccion_se_revierte_no_encola(
    autor, encolados, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            subir(autor)
            raise RuntimeError("falla después de subir")

    assert encolados == []
    assert not DocumentoRAG.objects.exists()


def test_subir_con_el_worker_indexa_el_documento(
    autor, proveedor_falso, django_capture_on_commit_callbacks
):
    """El flujo completo: subir, encolar y la tarea (en modo eager) indexa."""
    with django_capture_on_commit_callbacks(execute=True):
        documento = subir(autor)

    documento.refresh_from_db()
    assert documento.estado_indexacion == EstadoIndexacion.INDEXADO
    assert documento.fragmentos.count() == 2


def test_subir_audita_con_la_ip(autor, encolados):
    documento = subir(autor)

    registro = LogAuditoria.objects.get(
        entidad=ENTIDAD_DOCUMENTO, entidad_id=documento.id
    )
    assert registro.ip == "10.0.0.1"
    assert registro.usuario == autor


@pytest.mark.parametrize(
    ("nombre", "contenido", "motivo"),
    [
        ("politica.txt", TEXTO.encode(), "Markdown"),
        ("politica.md", "á".encode("latin-1"), "UTF-8"),
        ("politica.md", b"   \n", "vacío"),
        ("politica.md", b"#" * (TAMANO_MAXIMO_MARKDOWN + 1), "200 KB"),
    ],
    ids=["extension", "no-utf8", "vacio", "muy-grande"],
)
def test_un_archivo_que_no_es_markdown_utf8_se_rechaza(
    autor, encolados, nombre, contenido, motivo
):
    with pytest.raises(ArchivoRAGNoPermitido) as error:
        subir_documento_rag(
            archivo=SimpleUploadedFile(nombre, contenido),
            titulo="Política",
            tipo="POLITICA",
            pais=None,
            autor=autor,
            ip=None,
        )

    assert motivo in error.value.mensaje
    assert error.value.codigo == "ARCHIVO_NO_PERMITIDO"
    assert encolados == []


def test_reemplazar_con_otro_texto_sube_la_version_y_encola(
    autor, encolados, django_capture_on_commit_callbacks
):
    documento = subir(autor)
    encolados.clear()

    with django_capture_on_commit_callbacks(execute=True):
        actual = reemplazar_documento_rag(
            documento=documento, archivo=archivo(OTRO_TEXTO), autor=autor, ip=None
        )

    assert actual.version == 2
    assert actual.estado_indexacion == EstadoIndexacion.PENDIENTE
    assert encolados == [documento.id]


def test_reemplazar_con_el_mismo_texto_no_encola(
    autor, encolados, django_capture_on_commit_callbacks
):
    documento = subir(autor)
    encolados.clear()

    with django_capture_on_commit_callbacks(execute=True):
        actual = reemplazar_documento_rag(
            documento=documento, archivo=archivo(TEXTO), autor=autor, ip=None
        )

    assert actual.version == 1
    assert encolados == []


# ---------- Reindexar y desactivar ----------


def test_reindexar_un_pendiente_lo_vuelve_a_encolar(
    autor, encolados, django_capture_on_commit_callbacks
):
    """Regla 12: un PENDIENTE sin mensaje en la cola (cargar_demo_ia sin
    llave) no queda atascado."""
    documento = crear_documento_rag(
        titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO
    )

    with django_capture_on_commit_callbacks(execute=True):
        reindexar_documento_rag(documento=documento, autor=autor, ip=None)

    assert encolados == [documento.id]


def test_reindexar_un_error_lo_deja_pendiente_y_lo_audita(
    autor, encolados, django_capture_on_commit_callbacks
):
    documento = subir(autor)
    DocumentoRAG.objects.filter(pk=documento.pk).update(
        estado_indexacion=EstadoIndexacion.ERROR, error_indexacion="falla"
    )

    with django_capture_on_commit_callbacks(execute=True):
        actual = reindexar_documento_rag(documento=documento, autor=autor, ip=None)

    assert actual.estado_indexacion == EstadoIndexacion.PENDIENTE
    assert actual.error_indexacion == ""
    ultimo = LogAuditoria.objects.filter(entidad_id=documento.id).latest("id")
    assert ultimo.valores_anteriores == {"estado_indexacion": "ERROR"}


def test_desactivar_conserva_los_fragmentos(autor, proveedor_falso):
    documento = crear_documento_rag(
        titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO
    )
    indexar_documento(documento_id=documento.id)

    desactivar_documento_rag(documento=documento, autor=autor, ip=None)

    documento.refresh_from_db()
    assert not documento.activo
    assert documento.fragmentos.count() == 2


# ---------- La tarea ----------


def nuevo_documento():
    return crear_documento_rag(titulo="Manual", tipo="MANUAL", contenido_fuente=TEXTO)


def test_la_tarea_indexa_y_deja_indexado(proveedor_falso):
    documento = nuevo_documento()

    indexar_documento_tarea.apply(args=[documento.id])

    documento.refresh_from_db()
    assert documento.estado_indexacion == EstadoIndexacion.INDEXADO
    assert documento.fecha_indexacion is not None


class Reintento(Exception):
    """Lo que lanza el retry falso: la prueba solo comprueba que se pidió."""


def test_con_gemini_caido_la_tarea_reintenta_con_espera_creciente(
    proveedor_falso, monkeypatch
):
    proveedor_falso.falla = True
    documento = nuevo_documento()
    pedidos: list[int] = []

    def retry(*, exc, countdown):
        pedidos.append(countdown)
        return Reintento()

    monkeypatch.setattr(indexar_documento_tarea, "retry", retry)

    for intento in range(REINTENTOS):
        with pytest.raises(Reintento):
            indexar_documento_tarea.apply(
                args=[documento.id], retries=intento, throw=True
            )

    # Regla 6: 1, 2 y 4 minutos.
    assert pedidos == [60, 120, 240]
    documento.refresh_from_db()
    assert documento.estado_indexacion == EstadoIndexacion.PENDIENTE


def test_al_agotar_los_reintentos_queda_en_error_y_conserva_los_fragmentos(
    proveedor_falso,
):
    documento = nuevo_documento()
    indexar_documento(documento_id=documento.id)
    proveedor_falso.falla = True

    indexar_documento_tarea.apply(args=[documento.id], retries=REINTENTOS)

    documento.refresh_from_db()
    assert documento.estado_indexacion == EstadoIndexacion.ERROR
    assert "falla simulada" in documento.error_indexacion
    # Regla 7: los fragmentos anteriores siguen sirviendo.
    assert documento.fragmentos.count() == 2
    registro = LogAuditoria.objects.filter(entidad_id=documento.id).latest("id")
    assert registro.usuario is None
    assert registro.valores_nuevos["estado_indexacion"] == "ERROR"


def test_si_el_documento_cambio_durante_la_indexacion_no_reintenta(
    proveedor_falso, monkeypatch
):
    documento = nuevo_documento()
    proveedor_falso.mientras_genera = lambda: DocumentoRAG.objects.filter(
        pk=documento.pk
    ).update(version=99)
    monkeypatch.setattr(
        indexar_documento_tarea,
        "retry",
        lambda **_: pytest.fail("no debe reintentar"),
    )

    indexar_documento_tarea.apply(args=[documento.id], throw=True)

    assert not FragmentoRAG.objects.filter(documento=documento).exists()


def test_la_tarea_omite_un_documento_inexistente_o_desactivado(proveedor_falso, autor):
    indexar_documento_tarea.apply(args=[999_999], throw=True)

    documento = nuevo_documento()
    desactivar_documento_rag(documento=documento, autor=autor, ip=None)
    indexar_documento_tarea.apply(args=[documento.id], throw=True)

    assert proveedor_falso.llamadas_embeddings == []


def test_la_tarea_va_a_la_cola_documentos():
    """El worker consume "documentos" (scripts/iniciar.sh): si la ruta se
    pierde, la tarea iría a otra cola y nadie lo notaría en las pruebas eager."""
    ruta = app.amqp.router.route({}, indexar_documento_tarea.name)

    assert ruta["queue"].name == "documentos"
