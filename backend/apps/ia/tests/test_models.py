"""Pruebas de los modelos y el panel de IA (spec 005, §4 y §7)."""

import pytest
from django.contrib import admin
from django.db import IntegrityError

from apps.ia.models import DocumentoRAG, FragmentoRAG

from .proveedor_falso import vector_eje

pytestmark = pytest.mark.django_db


def test_un_documento_no_repite_el_orden_de_sus_fragmentos():
    documento = DocumentoRAG.objects.create(
        titulo="Manual", tipo="MANUAL", contenido_fuente="## A\nB"
    )
    datos = {"seccion": "A", "contenido": "B", "tokens": 1, "embedding": vector_eje(0)}
    FragmentoRAG.objects.create(documento=documento, orden=0, **datos)

    with pytest.raises(IntegrityError):
        FragmentoRAG.objects.create(documento=documento, orden=0, **datos)


@pytest.mark.parametrize("modelo", [DocumentoRAG, FragmentoRAG])
def test_el_panel_solo_permite_consultar(modelo):
    modelo_admin = admin.site._registry[modelo]

    assert modelo_admin.has_add_permission(request=None) is False
    assert modelo_admin.has_change_permission(request=None) is False
    assert modelo_admin.has_delete_permission(request=None) is False
