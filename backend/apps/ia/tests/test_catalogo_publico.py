"""Pruebas del catálogo público generado desde la base (spec 025)."""

from decimal import Decimal

import pytest

from apps.auditoria.models import LogAgenteIA
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.selectors import listar_propiedades_publicas, listar_unidades
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory
from apps.ia.catalogo_publico import TITULO_CATALOGO, armar_catalogo
from apps.ia.enums import EstadoIndexacion
from apps.ia.models import DocumentoRAG
from apps.ia.services import responder_consulta_publica, sincronizar_catalogo_publico

pytestmark = pytest.mark.django_db


@pytest.fixture
def torre():
    """Un edificio público con una unidad disponible y una vendida."""
    torre = PropiedadFactory(nombre="Torre Demo", es_publica=True)
    UnidadFactory(
        propiedad=torre,
        codigo="A-101",
        precio_lista=Decimal("650000.00"),
        estado=EstadoPropiedad.DISPONIBLE,
    )
    UnidadFactory(propiedad=torre, codigo="A-102", estado=EstadoPropiedad.VENDIDA)
    return torre


def catalogo() -> DocumentoRAG:
    return DocumentoRAG.objects.get(titulo=TITULO_CATALOGO)


def test_armar_catalogo_lista_unidades_con_su_estado(torre):
    casa = PropiedadFactory(
        nombre="Casa Demo", es_publica=True, estado=EstadoPropiedad.VENDIDA
    )
    propiedades = list(listar_propiedades_publicas())

    texto = armar_catalogo(propiedades, listar_unidades())

    assert texto.startswith(f"# {TITULO_CATALOGO}")
    # Una sección por propiedad, para que cada cita apunte a su ficha.
    assert f"## {torre.nombre}," in texto
    assert f"## {casa.nombre}," in texto
    assert "- A-101: nivel 1, 80 m², 2 habitaciones, 1 baño. USD 650,000.00." in texto
    assert "Estado: disponible." in texto
    assert "Estado: vendida." in texto
    assert "Unidades disponibles ahora: A-101." in texto
    # Una propiedad sin unidades muestra su propio estado.
    assert "No está disponible: su estado actual es vendida." in texto


def test_no_incluye_propiedades_que_no_son_publicas(proveedor_falso, torre):
    PropiedadFactory(nombre="Terreno Privado", es_publica=False)

    sincronizar_catalogo_publico()

    assert "Terreno Privado" not in catalogo().contenido_fuente


def test_la_primera_vez_crea_e_indexa(proveedor_falso, torre):
    assert sincronizar_catalogo_publico() is True

    documento = catalogo()
    assert documento.estado_indexacion == EstadoIndexacion.INDEXADO
    assert documento.fragmentos.count() >= 2
    assert len(proveedor_falso.llamadas_embeddings) == 1


def test_sin_cambios_no_reindexa(proveedor_falso, torre):
    sincronizar_catalogo_publico()
    version = catalogo().version

    assert sincronizar_catalogo_publico() is False

    assert catalogo().version == version
    assert len(proveedor_falso.llamadas_embeddings) == 1


def test_una_venta_cambia_el_catalogo_en_la_pregunta_siguiente(proveedor_falso, torre):
    sincronizar_catalogo_publico()
    version = catalogo().version
    torre.unidades.filter(codigo="A-101").update(estado=EstadoPropiedad.VENDIDA)

    assert sincronizar_catalogo_publico() is True

    documento = catalogo()
    assert documento.version == version + 1
    assert documento.estado_indexacion == EstadoIndexacion.INDEXADO
    assert "Por ahora no hay unidades disponibles" in documento.contenido_fuente


def test_un_catalogo_desactivado_no_se_vuelve_a_crear(proveedor_falso, torre):
    sincronizar_catalogo_publico()
    DocumentoRAG.objects.filter(titulo=TITULO_CATALOGO).update(activo=False)
    torre.unidades.update(estado=EstadoPropiedad.RESERVADA)

    assert sincronizar_catalogo_publico() is False
    assert DocumentoRAG.objects.filter(titulo=TITULO_CATALOGO).count() == 1


def test_sin_propiedades_publicas_no_crea_nada(proveedor_falso):
    PropiedadFactory(es_publica=False)

    assert sincronizar_catalogo_publico() is False
    assert not DocumentoRAG.objects.filter(titulo=TITULO_CATALOGO).exists()


def test_reemplaza_el_catalogo_subido_a_mano(proveedor_falso, torre):
    DocumentoRAG.objects.create(
        titulo=TITULO_CATALOGO, tipo="FICHA_PROPIEDAD", contenido_fuente="## Viejo\nx"
    )

    assert sincronizar_catalogo_publico() is True

    documento = catalogo()
    assert documento.version == 2
    assert "Torre Demo" in documento.contenido_fuente


def test_la_consulta_regenera_y_lo_anota_en_la_bitacora(proveedor_falso, torre):
    responder_consulta_publica(pregunta="¿Qué apartamentos hay disponibles?")

    assert catalogo().estado_indexacion == EstadoIndexacion.INDEXADO
    registro = LogAgenteIA.objects.get()
    assert registro.herramientas_invocadas[0]["nombre"] == (
        "sincronizar_catalogo_publico"
    )

    # La segunda pregunta, sin cambios, no regenera nada.
    responder_consulta_publica(pregunta="¿Y casas?")
    assert LogAgenteIA.objects.order_by("-id").first().herramientas_invocadas == []
