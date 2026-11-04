"""Pruebas de la gestión de usuarios desde el sistema (spec 026)."""

import pytest
from rest_framework.test import APIClient

from apps.auditoria.models import LogAuditoria
from apps.crm.tests.factories import AgenteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.exceptions import UltimoAdministrador
from apps.usuarios.models import Rol, Usuario
from apps.usuarios.services import actualizar_usuario, desactivar_usuario

from .factories import CONTRASENA_DE_PRUEBA, UsuarioFactory

pytestmark = pytest.mark.django_db

USUARIOS = "/api/v1/usuarios/"
LOGIN = "/api/v1/auth/login/"
CAMBIAR = "/api/v1/auth/cambiar-contrasena/"
CONTRASENA_NUEVA = "otra-clave-segura-2026"


def usuario_con_rol(rol: str, **campos) -> Usuario:
    return UsuarioFactory(rol=Rol.objects.get(nombre=rol), **campos)


def cliente(usuario: Usuario) -> APIClient:
    http = APIClient()
    http.force_authenticate(usuario)
    return http


@pytest.fixture
def admin() -> Usuario:
    return usuario_con_rol(NombreRol.ADMINISTRADOR)


def datos_nuevo(**cambios) -> dict:
    return {
        "email": "nueva.cuenta@demo.test",
        "nombre_completo": "Cuenta Nueva Demo",
        "rol": NombreRol.CONTABILIDAD,
        "password": CONTRASENA_NUEVA,
        **cambios,
    }


def test_el_administrador_crea_un_usuario_que_puede_iniciar_sesion(admin):
    respuesta = cliente(admin).post(USUARIOS, datos_nuevo(), format="json")

    assert respuesta.status_code == 201
    assert respuesta.json()["rol"] == NombreRol.CONTABILIDAD
    assert respuesta.json()["activo"] is True
    nuevo = Usuario.objects.get(email="nueva.cuenta@demo.test")
    assert nuevo.is_staff is False
    login = APIClient().post(
        LOGIN,
        {"email": "nueva.cuenta@demo.test", "password": CONTRASENA_NUEVA},
        format="json",
    )
    assert login.status_code == 200


def test_un_correo_repetido_con_otras_mayusculas_responde_409(admin):
    UsuarioFactory(email="repetido@demo.test")

    respuesta = cliente(admin).post(
        USUARIOS, datos_nuevo(email="Repetido@Demo.test"), format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "USUARIO_DUPLICADO"


def test_una_contrasena_debil_responde_400_con_los_motivos(admin):
    respuesta = cliente(admin).post(
        USUARIOS, datos_nuevo(password="1234"), format="json"
    )

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "CONTRASENA_INVALIDA"
    assert error["detalles"]["password"]
    assert not Usuario.objects.filter(email="nueva.cuenta@demo.test").exists()


@pytest.mark.parametrize(
    "rol",
    [NombreRol.GERENTE, NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA],
)
def test_solo_el_administrador_escribe(rol):
    http = cliente(usuario_con_rol(rol))
    otro = UsuarioFactory()

    assert http.post(USUARIOS, datos_nuevo(), format="json").status_code == 403
    assert http.patch(f"{USUARIOS}{otro.pk}/", {"telefono": "1"}).status_code == 403
    assert http.post(f"{USUARIOS}{otro.pk}/desactivar/").status_code == 403
    assert (
        http.post(
            f"{USUARIOS}{otro.pk}/restablecer-contrasena/",
            {"password": CONTRASENA_NUEVA},
        ).status_code
        == 403
    )


def test_el_listado_filtra_por_estado(admin):
    inactivo = UsuarioFactory(is_active=False)
    http = cliente(admin)

    def ids(estado=None):
        parametros = {"estado": estado} if estado else {}
        return {u["id"] for u in http.get(USUARIOS, parametros).json()["results"]}

    assert inactivo.pk not in ids()
    assert inactivo.pk in ids("INACTIVOS")
    assert {admin.pk, inactivo.pk} <= ids("TODOS")


def test_editar_cambia_rol_y_datos_y_audita_solo_lo_que_cambia(admin):
    otro = usuario_con_rol(NombreRol.CONSULTA, telefono="111")

    respuesta = cliente(admin).patch(
        f"{USUARIOS}{otro.pk}/",
        {
            "rol": NombreRol.GERENTE,
            "telefono": "222",
            "nombre_completo": otro.nombre_completo,
        },
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == NombreRol.GERENTE
    registro = LogAuditoria.objects.filter(entidad="usuarios_usuario").latest("id")
    assert registro.valores_anteriores == {"rol": "CONSULTA", "telefono": "111"}
    assert registro.valores_nuevos == {"rol": "GERENTE", "telefono": "222"}


def test_nadie_se_cambia_el_rol_ni_se_desactiva_a_si_mismo(admin):
    http = cliente(admin)

    rol = http.patch(
        f"{USUARIOS}{admin.pk}/", {"rol": NombreRol.CONSULTA}, format="json"
    )
    desactivar = http.post(f"{USUARIOS}{admin.pk}/desactivar/")

    assert rol.json()["error"]["codigo"] == "OPERACION_SOBRE_SI_MISMO"
    assert desactivar.json()["error"]["codigo"] == "OPERACION_SOBRE_SI_MISMO"


def test_no_se_queda_el_sistema_sin_administradores(admin):
    """Regla 5. Se prueba con el servicio: por la API, quien actúa ya es un
    administrador activo, y la regla 4 le impide tocarse a sí mismo."""
    gerente = usuario_con_rol(NombreRol.GERENTE)

    with pytest.raises(UltimoAdministrador):
        desactivar_usuario(usuario=admin, autor=gerente, ip=None)
    with pytest.raises(UltimoAdministrador):
        actualizar_usuario(
            usuario=admin,
            datos={"rol": Rol.objects.get(nombre=NombreRol.CONSULTA)},
            autor=gerente,
            ip=None,
        )

    # Con un segundo administrador activo, sí se puede.
    usuario_con_rol(NombreRol.ADMINISTRADOR)
    desactivar_usuario(usuario=admin, autor=gerente, ip=None)
    admin.refresh_from_db()
    assert admin.is_active is False


def test_un_superusuario_no_cambia_de_rol(admin):
    superusuario = Usuario.objects.create_superuser(
        email="super@demo.test",
        password=CONTRASENA_DE_PRUEBA,
        nombre_completo="Super Demo",
    )

    respuesta = cliente(admin).patch(
        f"{USUARIOS}{superusuario.pk}/", {"rol": NombreRol.GERENTE}, format="json"
    )

    assert respuesta.json()["error"]["codigo"] == "SUPERUSUARIO_ES_ADMINISTRADOR"


def test_un_usuario_con_perfil_de_agente_activo_no_cambia_ni_se_desactiva(admin):
    agente = AgenteFactory()
    http = cliente(admin)

    rol = http.patch(
        f"{USUARIOS}{agente.usuario.pk}/", {"rol": NombreRol.CONSULTA}, format="json"
    )
    desactivar = http.post(f"{USUARIOS}{agente.usuario.pk}/desactivar/")

    assert rol.json()["error"]["codigo"] == "USUARIO_CON_PERFIL_AGENTE"
    assert desactivar.json()["error"]["codigo"] == "USUARIO_CON_PERFIL_AGENTE"


def test_un_usuario_desactivado_no_entra_y_su_token_deja_de_servir(admin):
    otro = UsuarioFactory()
    login = APIClient().post(
        LOGIN, {"email": otro.email, "password": CONTRASENA_DE_PRUEBA}, format="json"
    )
    token = login.json()["access"]

    assert cliente(admin).post(f"{USUARIOS}{otro.pk}/desactivar/").status_code == 200

    con_token = APIClient()
    con_token.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert con_token.get("/api/v1/auth/yo/").status_code == 401
    otra_vez = APIClient().post(
        LOGIN, {"email": otro.email, "password": CONTRASENA_DE_PRUEBA}, format="json"
    )
    assert otra_vez.status_code == 401

    assert cliente(admin).post(f"{USUARIOS}{otro.pk}/reactivar/").json()["activo"]


def test_restablecer_contrasena_no_guarda_el_valor_en_la_bitacora(admin):
    otro = UsuarioFactory()

    respuesta = cliente(admin).post(
        f"{USUARIOS}{otro.pk}/restablecer-contrasena/",
        {"password": CONTRASENA_NUEVA},
        format="json",
    )

    assert respuesta.status_code == 204
    otro.refresh_from_db()
    assert otro.check_password(CONTRASENA_NUEVA)
    registro = LogAuditoria.objects.filter(entidad="usuarios_usuario").latest("id")
    assert CONTRASENA_NUEVA not in str(registro.valores_nuevos)


def test_cualquiera_cambia_su_contrasena_dando_la_actual():
    yo = usuario_con_rol(NombreRol.CONSULTA)
    http = cliente(yo)

    mala = http.post(
        CAMBIAR, {"actual": "no-es-esta", "nueva": CONTRASENA_NUEVA}, format="json"
    )
    assert mala.json()["error"]["codigo"] == "CONTRASENA_ACTUAL_INCORRECTA"

    buena = http.post(
        CAMBIAR,
        {"actual": CONTRASENA_DE_PRUEBA, "nueva": CONTRASENA_NUEVA},
        format="json",
    )
    assert buena.status_code == 204
    yo.refresh_from_db()
    assert yo.check_password(CONTRASENA_NUEVA)
    assert CONTRASENA_NUEVA not in str(
        LogAuditoria.objects.filter(entidad="usuarios_usuario")
        .latest("id")
        .valores_nuevos
    )
