"""Pruebas de la consulta pública al agente (spec 005, reglas 1 a 4 y 9)."""

import pytest

from apps.ia.exceptions import AgenteNoDisponible
from apps.ia.instrucciones import INSTRUCCIONES_SISTEMA, MENSAJE_SIN_INFORMACION
from apps.ia.models import DocumentoRAG, FragmentoRAG
from apps.ia.proveedores.base import RolMensaje, TareaEmbedding
from apps.ia.services import responder_consulta_publica

from .proveedor_falso import vector_eje, vector_mezcla

pytestmark = pytest.mark.django_db

PREGUNTA = "¿Qué documentos necesito para comprar?"


@pytest.fixture
def documento():
    documento = DocumentoRAG.objects.create(
        titulo="Requisitos – Guatemala", tipo="LEGAL", contenido_fuente="## A\nB"
    )
    FragmentoRAG.objects.create(
        documento=documento,
        orden=0,
        seccion="Documentos del comprador",
        contenido="El comprador presenta su DPI vigente.",
        tokens=10,
        embedding=vector_eje(0),
    )
    FragmentoRAG.objects.create(
        documento=documento,
        orden=1,
        seccion="Impuestos",
        contenido="La primera venta paga IVA. " * 20,
        tokens=10,
        embedding=vector_mezcla(0, 1, 0.9),
    )
    return documento


def test_con_fragmentos_responde_con_el_modelo_y_cita_las_fuentes(
    proveedor_falso, documento
):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)

    resultado = responder_consulta_publica(pregunta=PREGUNTA)

    assert resultado.sin_informacion is False
    assert resultado.respuesta == "Respuesta de prueba [1]."
    cita = resultado.citas[0]
    assert cita.documento == "Requisitos – Guatemala"
    assert cita.seccion == "Documentos del comprador"
    assert cita.tipo == "LEGAL"
    assert cita.extracto == "El comprador presenta su DPI vigente."


def test_solo_se_devuelven_las_fuentes_que_el_modelo_cito(proveedor_falso, documento):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)

    resultado = responder_consulta_publica(pregunta=PREGUNTA)

    # El modelo recibió dos fragmentos y solo citó el [1].
    assert [c.numero for c in resultado.citas] == [1]


def test_una_fuente_citada_conserva_su_numero(proveedor_falso, documento):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)
    proveedor_falso.texto_respuesta = "Solo el segundo dato [2]."

    resultado = responder_consulta_publica(pregunta=PREGUNTA)

    assert [(c.numero, c.seccion) for c in resultado.citas] == [(2, "Impuestos")]


def test_si_el_modelo_no_cita_se_devuelven_todas_las_fuentes(
    proveedor_falso, documento
):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)
    proveedor_falso.texto_respuesta = "Respuesta sin marcadores."

    resultado = responder_consulta_publica(pregunta=PREGUNTA)

    assert [c.numero for c in resultado.citas] == [1, 2]


def test_el_extracto_de_un_fragmento_largo_se_recorta(proveedor_falso, documento):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)
    proveedor_falso.texto_respuesta = "Dato [2]."

    cita_larga = responder_consulta_publica(pregunta=PREGUNTA).citas[0]

    assert len(cita_larga.extracto) <= 201
    assert cita_larga.extracto.endswith("…")


def test_al_modelo_le_llegan_las_reglas_y_los_fragmentos_numerados(
    proveedor_falso, documento
):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)

    responder_consulta_publica(pregunta=PREGUNTA)

    assert proveedor_falso.llamadas_embeddings[0]["tarea"] == TareaEmbedding.CONSULTA
    sistema, usuario = proveedor_falso.llamadas_respuesta[0]["mensajes"]
    assert sistema.rol == RolMensaje.SISTEMA
    assert sistema.contenido == INSTRUCCIONES_SISTEMA
    assert "[1] Requisitos – Guatemala · Documentos del comprador" in usuario.contenido
    assert "[2] Requisitos – Guatemala · Impuestos" in usuario.contenido
    assert usuario.contenido.endswith(f"Pregunta del visitante: {PREGUNTA}")


def test_sin_fragmentos_cercanos_no_llama_al_modelo(proveedor_falso, documento):
    # Eje 5: nada en común con los fragmentos guardados (regla 3).
    proveedor_falso.vectores[PREGUNTA] = vector_eje(5)

    resultado = responder_consulta_publica(pregunta=PREGUNTA)

    assert resultado.sin_informacion is True
    assert resultado.respuesta == MENSAJE_SIN_INFORMACION
    assert resultado.citas == []
    assert proveedor_falso.llamadas_respuesta == []


def test_los_documentos_inactivos_no_se_consultan(proveedor_falso, documento):
    documento.activo = False
    documento.save()
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)

    assert responder_consulta_publica(pregunta=PREGUNTA).sin_informacion is True


def test_si_el_modelo_no_devuelve_texto_no_queda_una_respuesta_vacia(
    proveedor_falso, documento
):
    proveedor_falso.vectores[PREGUNTA] = vector_eje(0)
    proveedor_falso.texto_respuesta = "   "

    assert responder_consulta_publica(pregunta=PREGUNTA).respuesta == (
        MENSAJE_SIN_INFORMACION
    )


def test_si_gemini_falla_el_agente_no_esta_disponible(proveedor_falso, documento):
    proveedor_falso.falla = True

    with pytest.raises(AgenteNoDisponible):
        responder_consulta_publica(pregunta=PREGUNTA)


def test_sin_llave_el_agente_no_esta_disponible(settings, documento):
    # Sin el proveedor falso: la fábrica real, sin llave.
    settings.IA_API_KEY = ""

    with pytest.raises(AgenteNoDisponible):
        responder_consulta_publica(pregunta=PREGUNTA)
