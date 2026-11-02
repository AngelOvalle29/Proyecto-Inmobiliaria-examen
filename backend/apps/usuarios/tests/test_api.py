"""Pruebas de los endpoints de usuarios: un caso feliz y uno de error."""

import pytest
from rest_framework.test import APIClient

from apps.auditoria.models import LogAuditoria
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol

from .factories import CONTRASENA_DE_PRUEBA, UsuarioFactory

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/refresh/"
YO = "/api/v1/auth/yo/"


@pytest.fixture
def cliente():
    return APIClient()


@pytest.fixture
def usuario():
    return UsuarioFactory(email="agente@demo.test", nombre_completo="Agente Demo")


def iniciar_sesion(cliente, email="agente@demo.test", password=CONTRASENA_DE_PRUEBA):
    return cliente.post(LOGIN, {"email": email, "password": password}, format="json")


# ---------- login ----------


def test_login_correcto_devuelve_los_tokens(cliente, usuario):
    respuesta = iniciar_sesion(cliente)

    assert respuesta.status_code == 200
    assert set(respuesta.json()) == {"access", "refresh"}


def test_login_con_credenciales_invalidas_devuelve_401(cliente, usuario):
    respuesta = iniciar_sesion(cliente, password="contrasena-equivocada")

    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "error": {
            "codigo": "CREDENCIALES_INVALIDAS",
            "mensaje": "Correo o contraseña incorrectos.",
            "detalles": {},
        }
    }


def test_login_sin_contrasena_devuelve_error_de_validacion(cliente):
    respuesta = cliente.post(LOGIN, {"email": "agente@demo.test"}, format="json")

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert "password" in error["detalles"]


def test_el_intento_31_en_un_minuto_devuelve_429(cliente, usuario):
    for _ in range(30):
        iniciar_sesion(cliente, password="contrasena-equivocada")

    respuesta = iniciar_sesion(cliente)

    assert respuesta.status_code == 429
    assert respuesta.json()["error"]["codigo"] == "DEMASIADAS_PETICIONES"


def test_agotar_los_intentos_de_login_no_bloquea_la_renovacion(cliente, usuario):
    """Login y renovación tienen límites separados: quien ya entró sigue
    renovando su token aunque otros agoten los intentos desde la misma IP."""
    tokens = iniciar_sesion(cliente).json()
    for _ in range(30):
        iniciar_sesion(cliente, password="contrasena-equivocada")

    respuesta = cliente.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")

    assert respuesta.status_code == 200


def test_el_login_audita_la_ip_del_cliente(cliente, usuario):
    iniciar_sesion(cliente)

    assert LogAuditoria.objects.get().ip == "127.0.0.1"


# ---------- refresh ----------


def test_refresh_entrega_un_nuevo_token_de_acceso(cliente, usuario):
    refresh = iniciar_sesion(cliente).json()["refresh"]

    respuesta = cliente.post(REFRESH, {"refresh": refresh}, format="json")

    assert respuesta.status_code == 200
    assert "access" in respuesta.json()


def test_refresh_con_un_token_invalido_devuelve_401(cliente):
    respuesta = cliente.post(REFRESH, {"refresh": "no-es-un-token"}, format="json")

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_refresh_de_un_usuario_que_ya_no_existe_devuelve_401(cliente, usuario):
    """Pasa si se reinicia la base y el navegador conserva el token: antes era
    un 500 y la app no salía de "No se pudo conectar con el servidor"."""
    refresh = iniciar_sesion(cliente).json()["refresh"]
    LogAuditoria.objects.all().delete()  # el login lo audita, y protege al usuario
    usuario.delete()

    respuesta = cliente.post(REFRESH, {"refresh": refresh}, format="json")

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_refresh_de_un_usuario_desactivado_devuelve_401(cliente, usuario):
    refresh = iniciar_sesion(cliente).json()["refresh"]
    usuario.is_active = False
    usuario.save(update_fields=["is_active"])

    respuesta = cliente.post(REFRESH, {"refresh": refresh}, format="json")

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "NO_AUTENTICADO"


# ---------- yo ----------


def test_yo_sin_token_devuelve_401(cliente):
    respuesta = cliente.get(YO)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_yo_con_token_devuelve_los_datos_del_usuario(cliente, usuario):
    access = iniciar_sesion(cliente).json()["access"]
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    respuesta = cliente.get(YO)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["email"] == "agente@demo.test"
    assert datos["nombre_completo"] == "Agente Demo"
    assert datos["rol"] == NombreRol.CONSULTA
    assert datos["pais"] is None
    # El login acaba de registrar el acceso.
    assert datos["ultimo_acceso"] is not None
    assert "password" not in datos


def test_yo_rechaza_el_token_de_un_usuario_desactivado(cliente, usuario):
    access = iniciar_sesion(cliente).json()["access"]
    usuario.is_active = False
    usuario.save(update_fields=["is_active"])
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert cliente.get(YO).status_code == 401


def test_yo_muestra_el_rol_asignado(cliente):
    UsuarioFactory(
        email="gerente@demo.test", rol=Rol.objects.get(nombre=NombreRol.GERENTE)
    )
    access = iniciar_sesion(cliente, email="gerente@demo.test").json()["access"]
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert cliente.get(YO).json()["rol"] == NombreRol.GERENTE
