"""Pruebas de los servicios de auditoría."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import transaction

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


def test_registrar_auditoria_guarda_todos_los_campos():
    usuario = UsuarioFactory()

    registro = registrar_auditoria(
        usuario=usuario,
        entidad="core_moneda",
        entidad_id=7,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"nombre": "Dólar"},
        valores_nuevos={"nombre": "Dólar estadounidense"},
        ip="203.0.113.10",
        user_agent="Mozilla/5.0",
    )

    registro.refresh_from_db()
    assert registro.usuario == usuario
    assert registro.entidad == "core_moneda"
    assert registro.entidad_id == 7
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"nombre": "Dólar"}
    assert registro.valores_nuevos == {"nombre": "Dólar estadounidense"}
    assert registro.ip == "203.0.113.10"
    assert registro.user_agent == "Mozilla/5.0"
    assert registro.fecha is not None


def test_una_accion_del_sistema_no_tiene_usuario():
    registro = registrar_auditoria(
        usuario=None,
        entidad="core_tipo_cambio",
        entidad_id=1,
        accion=AccionAuditoria.CREAR,
    )

    assert registro.usuario is None
    assert registro.user_agent == ""


def test_guarda_montos_y_fechas_en_los_valores():
    """Los montos son Decimal y las fechas date: el JSON estándar no los acepta."""
    registro = registrar_auditoria(
        usuario=None,
        entidad="ventas_contratoventa",
        entidad_id=1,
        accion=AccionAuditoria.CREAR,
        valores_nuevos={
            "monto": Decimal("150000.00"),
            "fecha_firma": date(2026, 10, 1),
        },
    )

    registro.refresh_from_db()
    assert registro.valores_nuevos == {
        "monto": "150000.00",
        "fecha_firma": "2026-10-01",
    }


def test_si_la_operacion_se_revierte_su_registro_tambien():
    """
    registrar_auditoria corre dentro de la transacción de quien escribe: si la
    operación de negocio falla, no queda registro de algo que no ocurrió.
    """
    with pytest.raises(RuntimeError), transaction.atomic():
        registrar_auditoria(
            usuario=None,
            entidad="core_moneda",
            entidad_id=1,
            accion=AccionAuditoria.CREAR,
        )
        raise RuntimeError("falla la operación de negocio después de auditar")

    assert LogAuditoria.objects.count() == 0
