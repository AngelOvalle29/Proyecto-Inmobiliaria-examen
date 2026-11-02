"""Pruebas del selector de búsqueda por similitud (spec 005, §6)."""

import pytest

from apps.ia.models import DocumentoRAG, FragmentoRAG
from apps.ia.selectors import buscar_fragmentos_similares

from .proveedor_falso import vector_eje, vector_mezcla

pytestmark = pytest.mark.django_db


def fragmento(documento, orden, vector, seccion="Sección"):
    return FragmentoRAG.objects.create(
        documento=documento,
        orden=orden,
        seccion=seccion,
        contenido=f"Contenido {orden}",
        tokens=5,
        embedding=vector,
    )


@pytest.fixture
def documento():
    return DocumentoRAG.objects.create(
        titulo="Política", tipo="POLITICA", contenido_fuente="## A\nB"
    )


def test_ordena_del_mas_al_menos_cercano(documento):
    lejano = fragmento(documento, 0, vector_mezcla(0, 1, 0.6))
    identico = fragmento(documento, 1, vector_eje(0))
    cercano = fragmento(documento, 2, vector_mezcla(0, 1, 0.9))

    resultado = buscar_fragmentos_similares(
        embedding=vector_eje(0), distancia_maxima=0.6
    )

    assert resultado == [identico, cercano, lejano]
    assert resultado[0].distancia == pytest.approx(0.0, abs=1e-6)


def test_deja_fuera_lo_que_pasa_del_umbral(documento):
    fragmento(documento, 0, vector_eje(0))
    fragmento(documento, 1, vector_eje(1))  # distancia 1: nada en común

    resultado = buscar_fragmentos_similares(
        embedding=vector_eje(0), distancia_maxima=0.6
    )

    assert [f.orden for f in resultado] == [0]


def test_no_devuelve_fragmentos_de_documentos_inactivos(documento):
    fragmento(documento, 0, vector_eje(0))
    documento.activo = False
    documento.save()

    assert (
        buscar_fragmentos_similares(embedding=vector_eje(0), distancia_maxima=2) == []
    )


def test_respeta_el_limite(documento):
    for orden in range(8):
        fragmento(documento, orden, vector_eje(0))

    resultado = buscar_fragmentos_similares(
        embedding=vector_eje(0), distancia_maxima=1, limite=5
    )

    assert len(resultado) == 5
