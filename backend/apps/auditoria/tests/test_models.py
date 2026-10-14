"""Pruebas de la bitácora como registro de solo inserción."""

import pytest
from django.contrib import admin

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.exceptions import RegistroAuditoriaInmutable
from apps.auditoria.models import LogAuditoria
from apps.auditoria.services import registrar_auditoria

pytestmark = pytest.mark.django_db


@pytest.fixture
def registro():
    return registrar_auditoria(
        usuario=None, entidad="core_moneda", entidad_id=1, accion=AccionAuditoria.CREAR
    )


def test_un_registro_guardado_no_se_puede_modificar(registro):
    registro.accion = AccionAuditoria.ELIMINAR

    with pytest.raises(RegistroAuditoriaInmutable):
        registro.save()


def test_un_registro_no_se_puede_borrar(registro):
    with pytest.raises(RegistroAuditoriaInmutable):
        registro.delete()

    assert LogAuditoria.objects.filter(pk=registro.pk).exists()


def test_el_panel_solo_permite_consultar_la_bitacora():
    modelo_admin = admin.site._registry[LogAuditoria]

    assert modelo_admin.has_add_permission(request=None) is False
    assert modelo_admin.has_change_permission(request=None) is False
    assert modelo_admin.has_delete_permission(request=None) is False
