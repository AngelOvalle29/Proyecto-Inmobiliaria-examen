"""Pruebas de los servicios de IA: documentos e indexación (spec 005)."""

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.ia.exceptions import (
    DocumentoModificadoDuranteIndexacion,
    DocumentoRAGDuplicado,
    EmbeddingConDimensionIncorrecta,
)
from apps.ia.models import DIMENSION_EMBEDDINGS, DocumentoRAG, FragmentoRAG
from apps.ia.proveedores.base import ProveedorIANoDisponible, TareaEmbedding
from apps.ia.services import (
    ENTIDAD_DOCUMENTO,
    actualizar_contenido_documento,
    crear_documento_rag,
    indexar_documento,
)

pytestmark = pytest.mark.django_db

TEXTO = "## Requisitos\nDPI vigente.\n\n## Pagos\nTransferencia.\n\n## Plazos\n30 días."


def crear(titulo="Manual de prueba", contenido=TEXTO):
    return crear_documento_rag(titulo=titulo, tipo="MANUAL", contenido_fuente=contenido)


def registros_del(documento):
    return LogAuditoria.objects.filter(
        entidad=ENTIDAD_DOCUMENTO, entidad_id=documento.id
    ).order_by("id")


# ---------- Documentos ----------


def test_crear_documento_queda_en_version_1_sin_indexar_y_auditado():
    documento = crear()

    assert documento.version == 1
    assert documento.fecha_indexacion is None
    assert documento.fragmentos.count() == 0
    registro = registros_del(documento).get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["titulo"] == "Manual de prueba"


def test_no_hay_dos_documentos_con_el_mismo_titulo():
    crear()
    with pytest.raises(DocumentoRAGDuplicado):
        crear()


def test_cambiar_el_contenido_sube_la_version_y_lo_audita():
    documento = crear()

    actualizar_contenido_documento(documento=documento, contenido_fuente="## Nuevo\nX")

    documento.refresh_from_db()
    assert documento.version == 2
    registro = registros_del(documento).last()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"version": 1}
    assert registro.valores_nuevos == {"version": 2}


def test_guardar_el_mismo_contenido_no_cambia_nada():
    documento = crear()

    actualizar_contenido_documento(documento=documento, contenido_fuente=TEXTO)

    documento.refresh_from_db()
    assert documento.version == 1
    assert registros_del(documento).count() == 1


# ---------- Indexación ----------


def test_indexar_crea_un_fragmento_por_seccion_con_su_vector(proveedor_falso):
    documento = crear()

    cantidad = indexar_documento(documento_id=documento.id)

    assert cantidad == 3
    fragmentos = list(documento.fragmentos.order_by("orden"))
    assert [f.seccion for f in fragmentos] == ["Requisitos", "Pagos", "Plazos"]
    assert [f.orden for f in fragmentos] == [0, 1, 2]
    assert fragmentos[0].contenido == "DPI vigente."
    assert all(len(f.embedding) == DIMENSION_EMBEDDINGS for f in fragmentos)
    documento.refresh_from_db()
    assert documento.fecha_indexacion is not None


def test_indexar_vectoriza_con_titulo_y_seccion_como_documento(proveedor_falso):
    documento = crear()

    indexar_documento(documento_id=documento.id)

    llamada = proveedor_falso.llamadas_embeddings[0]
    assert llamada["tarea"] == TareaEmbedding.DOCUMENTO
    assert llamada["textos"][0] == "Manual de prueba · Requisitos\n\nDPI vigente."


def test_indexar_queda_en_la_auditoria(proveedor_falso):
    documento = crear()

    indexar_documento(documento_id=documento.id)

    registro = registros_del(documento).last()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.usuario is None
    assert registro.valores_anteriores == {"fragmentos": 0}
    assert registro.valores_nuevos == {"fragmentos": 3, "version": 1}


def test_reindexar_reemplaza_todos_los_fragmentos(proveedor_falso):
    documento = crear()
    indexar_documento(documento_id=documento.id)
    actualizar_contenido_documento(
        documento=documento, contenido_fuente="## Única\nTexto nuevo."
    )

    cantidad = indexar_documento(documento_id=documento.id)

    assert cantidad == 1
    assert list(documento.fragmentos.values_list("seccion", flat=True)) == ["Única"]


def test_si_el_proveedor_falla_quedan_los_fragmentos_anteriores(proveedor_falso):
    documento = crear()
    indexar_documento(documento_id=documento.id)
    actualizar_contenido_documento(documento=documento, contenido_fuente="## Otra\nX")
    proveedor_falso.falla = True

    with pytest.raises(ProveedorIANoDisponible):
        indexar_documento(documento_id=documento.id)

    secciones = list(documento.fragmentos.values_list("seccion", flat=True))
    assert secciones == ["Requisitos", "Pagos", "Plazos"]


def test_un_vector_de_otro_tamano_detiene_la_indexacion(proveedor_falso):
    documento = crear()
    proveedor_falso.dimension = 3072

    with pytest.raises(EmbeddingConDimensionIncorrecta):
        indexar_documento(documento_id=documento.id)

    assert FragmentoRAG.objects.count() == 0
    documento.refresh_from_db()
    assert documento.fecha_indexacion is None


def test_un_documento_sin_texto_no_llama_al_proveedor(proveedor_falso):
    documento = crear(contenido="# Solo el título")

    assert indexar_documento(documento_id=documento.id) == 0
    assert proveedor_falso.llamadas_embeddings == []


def test_si_el_texto_cambia_mientras_se_indexa_no_guarda_fragmentos_viejos(
    proveedor_falso,
):
    """Reproducción de la revisión del PR #62: la reserva pasa de 15 a 30 días
    mientras se generan los vectores del texto de 15."""
    documento = crear(contenido="## Reservas\nLa reserva dura 15 días.")
    indexar_documento(documento_id=documento.id)

    def cambiar_a_30_dias():
        actualizar_contenido_documento(
            documento=DocumentoRAG.objects.get(pk=documento.id),
            contenido_fuente="## Reservas\nLa reserva dura 30 días.",
        )

    actualizar_contenido_documento(
        documento=documento, contenido_fuente="## Reservas\nLa reserva dura 15 días!"
    )
    proveedor_falso.mientras_genera = cambiar_a_30_dias

    with pytest.raises(DocumentoModificadoDuranteIndexacion):
        indexar_documento(documento_id=documento.id)

    documento.refresh_from_db()
    assert documento.version == 3
    # Sigue pendiente: no quedó marcado como indexado con el texto viejo.
    assert documento.fecha_indexacion is None
    # Y la siguiente indexación toma el texto actual.
    indexar_documento(documento_id=documento.id)
    assert list(documento.fragmentos.values_list("contenido", flat=True)) == [
        "La reserva dura 30 días."
    ]
