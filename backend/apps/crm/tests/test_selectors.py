"""Pruebas de los selectores de CRM (spec 004, §9, nivel selector)."""

import pytest

from apps.crm.selectors import (
    existe_cliente_con_documento,
    listar_agentes,
    listar_clientes_visibles,
)
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import AgenteFactory, ClienteFactory, EmpresaFactory

pytestmark = pytest.mark.django_db


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


# ---------- Cartera (reglas 11 a 14) ----------


def test_un_agente_solo_ve_su_cartera():
    mio = ClienteFactory()
    ClienteFactory()  # de otro agente

    visibles = listar_clientes_visibles(usuario=mio.agente_asignado.usuario)

    assert list(visibles) == [mio]


def test_un_agente_sin_perfil_no_ve_ningun_cliente():
    ClienteFactory()

    visibles = listar_clientes_visibles(usuario=usuario_con_rol(NombreRol.AGENTE))

    assert not visibles.exists()


@pytest.mark.parametrize(
    "rol",
    [
        NombreRol.ADMINISTRADOR,
        NombreRol.GERENTE,
        NombreRol.CONTABILIDAD,
        NombreRol.CONSULTA,
    ],
)
def test_los_demas_roles_ven_a_todos_los_clientes(rol):
    ClienteFactory()
    ClienteFactory()

    assert listar_clientes_visibles(usuario=usuario_con_rol(rol)).count() == 2


def test_los_clientes_desactivados_no_se_listan():
    ClienteFactory(activo=False)

    gerente = usuario_con_rol(NombreRol.GERENTE)
    assert not listar_clientes_visibles(usuario=gerente).exists()


# ---------- Agentes ----------


def test_listar_agentes_cuenta_solo_los_clientes_activos():
    agente = AgenteFactory()
    ClienteFactory(agente_asignado=agente)
    ClienteFactory(agente_asignado=agente, activo=False)

    assert listar_agentes().get(pk=agente.pk).clientes_activos == 1


def test_listar_agentes_no_incluye_a_los_desactivados():
    AgenteFactory(activo=False)

    assert not listar_agentes().exists()


# ---------- Duplicados (regla 7) ----------


def test_existe_cliente_con_documento_compara_solo_dentro_del_tipo():
    """El NIT opcional de una persona no choca con el de una empresa."""
    persona = ClienteFactory(nit="NIT123")

    assert not existe_cliente_con_documento(
        pais_id=persona.pais_id, tipo="EMPRESA", documento="NIT123"
    )


def test_existe_cliente_con_documento_puede_excluir_al_propio_cliente():
    empresa = EmpresaFactory(nit="NIT123")

    assert existe_cliente_con_documento(
        pais_id=empresa.pais_id, tipo="EMPRESA", documento="NIT123"
    )
    assert not existe_cliente_con_documento(
        pais_id=empresa.pais_id,
        tipo="EMPRESA",
        documento="NIT123",
        excluir_id=empresa.pk,
    )
