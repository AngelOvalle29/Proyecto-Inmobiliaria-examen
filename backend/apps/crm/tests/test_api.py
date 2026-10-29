"""
Pruebas de los endpoints de CRM (spec 004, §9, nivel API).

Las reglas ya están probadas en servicios y selectores. Aquí se prueba lo que
solo existe en la capa HTTP: quién puede llamar a qué (la matriz de
permisos), el 404 del cliente ajeno, los filtros y el formato de los errores.
"""

import pytest
from rest_framework.test import APIClient

from apps.auditoria.models import LogAuditoria
from apps.core.tests.factories import PaisFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import AgenteFactory, ClienteFactory, EmpresaFactory

pytestmark = pytest.mark.django_db

AGENTES = "/api/v1/agentes/"
CLIENTES = "/api/v1/clientes/"

TODOS_LOS_ROLES = list(NombreRol)


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


def cliente_http(usuario=None):
    http = APIClient()
    if usuario is not None:
        http.force_authenticate(user=usuario)
    return http


def datos_persona(**cambios):
    datos = {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo",
        "documento_identidad": "1234567890101",
        "pais": PaisFactory().pk,
    }
    datos.update(cambios)
    return datos


# ---------- Autenticación ----------


@pytest.mark.parametrize("ruta", [AGENTES, CLIENTES])
def test_sin_token_responde_401(ruta):
    assert cliente_http().get(ruta).status_code == 401


# ---------- Matriz de permisos de escritura (reglas 11 a 13) ----------


@pytest.mark.parametrize("rol", TODOS_LOS_ROLES)
def test_solo_administrador_y_gerente_crean_agentes(rol):
    usuario_agente = usuario_con_rol(NombreRol.AGENTE)

    respuesta = cliente_http(usuario_con_rol(rol)).post(
        AGENTES,
        {
            "usuario": usuario_agente.pk,
            "porcentaje_comision": "3.50",
            "fecha_ingreso": "2026-10-01",
        },
        format="json",
    )

    esperado = 201 if rol in (NombreRol.ADMINISTRADOR, NombreRol.GERENTE) else 403
    assert respuesta.status_code == esperado


@pytest.mark.parametrize(
    "rol", [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]
)
def test_los_demas_roles_no_editan_ni_desactivan_agentes(rol):
    agente = AgenteFactory()
    http = cliente_http(usuario_con_rol(rol))

    assert (
        http.patch(
            f"{AGENTES}{agente.pk}/", {"porcentaje_comision": "5"}, format="json"
        ).status_code
        == 403
    )
    assert http.delete(f"{AGENTES}{agente.pk}/").status_code == 403


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_contabilidad_y_consulta_leen_pero_no_escriben_clientes(rol):
    cliente = ClienteFactory()
    http = cliente_http(usuario_con_rol(rol))

    assert http.get(CLIENTES).json()["count"] == 1
    assert http.post(CLIENTES, datos_persona(), format="json").status_code == 403
    assert (
        http.patch(
            f"{CLIENTES}{cliente.pk}/", {"notas": "x"}, format="json"
        ).status_code
        == 403
    )
    assert http.delete(f"{CLIENTES}{cliente.pk}/").status_code == 403


@pytest.mark.parametrize(
    "rol", [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]
)
def test_solo_administrador_y_gerente_reasignan(rol):
    cliente = ClienteFactory()
    if rol == NombreRol.AGENTE:
        # Aun siendo su propio cliente, un agente no reasigna (regla 12).
        usuario = cliente.agente_asignado.usuario
    else:
        usuario = usuario_con_rol(rol)

    respuesta = cliente_http(usuario).post(
        f"{CLIENTES}{cliente.pk}/reasignar/",
        {"agente": AgenteFactory().pk},
        format="json",
    )

    assert respuesta.status_code == 403


# ---------- Cartera del agente (reglas 12 y 14) ----------


def test_un_agente_lista_solo_sus_clientes():
    mio = ClienteFactory()
    ClienteFactory()

    respuesta = cliente_http(mio.agente_asignado.usuario).get(CLIENTES)

    assert [c["id"] for c in respuesta.json()["results"]] == [mio.pk]


def test_el_cliente_de_otro_agente_responde_404_y_no_403():
    """Regla 14: un 403 confirmaría que el cliente existe."""
    ajeno = ClienteFactory()
    http = cliente_http(AgenteFactory().usuario)

    assert http.get(f"{CLIENTES}{ajeno.pk}/").status_code == 404
    assert (
        http.patch(f"{CLIENTES}{ajeno.pk}/", {"notas": "x"}, format="json").status_code
        == 404
    )
    assert http.delete(f"{CLIENTES}{ajeno.pk}/").status_code == 404


def test_un_agente_crea_un_cliente_asignado_a_si_mismo():
    agente = AgenteFactory()
    otro = AgenteFactory()

    respuesta = cliente_http(agente.usuario).post(
        CLIENTES, datos_persona(agente_asignado=otro.pk), format="json"
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["agente_asignado"]["id"] == agente.pk


def test_un_agente_sin_perfil_ve_cero_clientes_y_no_puede_crear():
    ClienteFactory()
    http = cliente_http(usuario_con_rol(NombreRol.AGENTE))

    assert http.get(CLIENTES).json()["count"] == 0
    respuesta = http.post(CLIENTES, datos_persona(), format="json")
    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "SIN_PERFIL_DE_AGENTE"


# ---------- Validación y errores de negocio ----------


def test_el_gerente_debe_indicar_el_agente_al_crear():
    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).post(
        CLIENTES, datos_persona(), format="json"
    )

    assert respuesta.status_code == 400
    assert "agente_asignado" in respuesta.json()["error"]["detalles"]


def test_una_persona_sin_documento_responde_400_indicando_el_campo():
    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).post(
        CLIENTES,
        datos_persona(documento_identidad="", agente_asignado=AgenteFactory().pk),
        format="json",
    )

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert "documento_identidad" in error["detalles"]


def test_un_documento_repetido_responde_409_con_formato_uniforme():
    existente = ClienteFactory(documento_identidad="1234567890101")

    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).post(
        CLIENTES,
        datos_persona(
            pais=existente.pais_id,
            documento_identidad="1234 56789-0101",
            agente_asignado=AgenteFactory().pk,
        ),
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CLIENTE_DUPLICADO"


def test_desactivar_un_agente_con_clientes_responde_409():
    cliente = ClienteFactory()

    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).delete(
        f"{AGENTES}{cliente.agente_asignado.pk}/"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "AGENTE_CON_CLIENTES"


def test_cambiar_una_persona_a_empresa_sin_razon_social_responde_400():
    """La validación de la regla 6 combina lo que llega con lo que ya tenía."""
    cliente = ClienteFactory()

    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).patch(
        f"{CLIENTES}{cliente.pk}/", {"tipo": "EMPRESA"}, format="json"
    )

    assert respuesta.status_code == 400
    assert {"razon_social", "nit"} <= set(respuesta.json()["error"]["detalles"])


# ---------- Flujo completo y auditoría ----------


def test_crear_editar_reasignar_y_desactivar_dejan_su_registro():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    http = cliente_http(gerente)
    agente = AgenteFactory()

    creado = http.post(
        CLIENTES, datos_persona(agente_asignado=agente.pk), format="json"
    ).json()
    ruta = f"{CLIENTES}{creado['id']}/"
    assert http.patch(ruta, {"telefono": "5555-0000"}, format="json").status_code == 200
    assert (
        http.post(
            f"{ruta}reasignar/", {"agente": AgenteFactory().pk}, format="json"
        ).status_code
        == 200
    )
    assert http.delete(ruta).status_code == 204

    acciones = list(
        LogAuditoria.objects.filter(entidad="crm_cliente")
        .order_by("id")
        .values_list("accion", flat=True)
    )
    assert acciones == ["CREAR", "ACTUALIZAR", "ACTUALIZAR", "ELIMINAR"]
    assert http.get(ruta).status_code == 404  # desactivado: ya no se lista


def test_el_codigo_aparece_en_la_respuesta():
    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).post(
        CLIENTES, datos_persona(agente_asignado=AgenteFactory().pk), format="json"
    )

    assert respuesta.json()["codigo"].startswith("CLI-")


# ---------- Filtros y paginación ----------


def test_filtros_por_tipo_pais_agente_y_busqueda():
    agente = AgenteFactory()
    persona = ClienteFactory(agente_asignado=agente, apellidos="Bolívar Demo")
    empresa = EmpresaFactory()
    http = cliente_http(usuario_con_rol(NombreRol.GERENTE))

    def ids(parametros):
        return [c["id"] for c in http.get(CLIENTES, parametros).json()["results"]]

    assert ids({"tipo": "EMPRESA"}) == [empresa.pk]
    assert ids({"pais": persona.pais_id}) == [persona.pk]
    assert ids({"agente": agente.pk}) == [persona.pk]
    assert ids({"buscar": "bolívar"}) == [persona.pk]


def test_los_clientes_se_paginan_de_25_en_25():
    agente = AgenteFactory()
    for _ in range(26):
        ClienteFactory(agente_asignado=agente)

    respuesta = cliente_http(usuario_con_rol(NombreRol.GERENTE)).get(CLIENTES)

    assert respuesta.json()["count"] == 26
    assert len(respuesta.json()["results"]) == 25


def test_el_listado_de_agentes_incluye_sus_clientes_activos():
    cliente = ClienteFactory()

    respuesta = cliente_http(usuario_con_rol(NombreRol.CONSULTA)).get(AGENTES)

    agente = respuesta.json()["results"][0]
    assert agente["id"] == cliente.agente_asignado.pk
    assert agente["clientes_activos"] == 1
