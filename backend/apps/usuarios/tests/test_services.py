"""Pruebas de los servicios de usuarios: inicio de sesión y su auditoría."""

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.usuarios.exceptions import CredencialesInvalidas
from apps.usuarios.services import (
    iniciar_sesion,
    registrar_acceso,
    registrar_login_fallido,
)

from .factories import CONTRASENA_DE_PRUEBA, UsuarioFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.10"
NAVEGADOR = "Mozilla/5.0"


def test_registrar_acceso_actualiza_el_ultimo_acceso_y_lo_audita():
    usuario = UsuarioFactory()
    assert usuario.last_login is None

    registrar_acceso(usuario=usuario, ip=IP, user_agent=NAVEGADOR)

    usuario.refresh_from_db()
    assert usuario.last_login is not None
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.INICIAR_SESION
    assert registro.usuario == usuario
    assert registro.entidad == "usuarios_usuario"
    assert registro.entidad_id == usuario.pk
    assert registro.ip == IP
    assert registro.user_agent == NAVEGADOR


def test_login_fallido_registra_el_correo_y_nunca_la_contrasena():
    usuario = UsuarioFactory(email="agente@demo.test")

    registrar_login_fallido(email="agente@demo.test", ip=IP, user_agent=NAVEGADOR)

    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.LOGIN_FALLIDO
    assert registro.usuario is None
    # El correo existe: el intento queda asociado a esa cuenta.
    assert registro.entidad_id == usuario.pk
    assert registro.valores_nuevos == {"email": "agente@demo.test"}


def test_login_fallido_con_un_correo_inexistente_no_apunta_a_ningun_registro():
    registrar_login_fallido(email="nadie@demo.test", ip=IP, user_agent=NAVEGADOR)

    assert LogAuditoria.objects.get().entidad_id is None


def test_iniciar_sesion_entrega_los_dos_tokens():
    UsuarioFactory(email="agente@demo.test")

    tokens = iniciar_sesion(
        email="agente@demo.test",
        password=CONTRASENA_DE_PRUEBA,
        ip=IP,
        user_agent=NAVEGADOR,
    )

    assert set(tokens) == {"access", "refresh"}
    assert LogAuditoria.objects.get().accion == AccionAuditoria.INICIAR_SESION


def test_una_contrasena_incorrecta_se_rechaza_y_el_intento_queda_registrado():
    """
    La excepción no revierte el registro: iniciar_sesion no es atómica a
    propósito, para conservar justo los intentos fallidos.
    """
    UsuarioFactory(email="agente@demo.test")

    with pytest.raises(CredencialesInvalidas):
        iniciar_sesion(
            email="agente@demo.test",
            password="contrasena-equivocada",
            ip=IP,
            user_agent=NAVEGADOR,
        )

    assert LogAuditoria.objects.get().accion == AccionAuditoria.LOGIN_FALLIDO


def test_un_usuario_desactivado_no_puede_iniciar_sesion():
    UsuarioFactory(email="agente@demo.test", is_active=False)

    with pytest.raises(CredencialesInvalidas):
        iniciar_sesion(
            email="agente@demo.test",
            password=CONTRASENA_DE_PRUEBA,
            ip=IP,
            user_agent=NAVEGADOR,
        )
