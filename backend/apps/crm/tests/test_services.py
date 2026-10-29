"""Pruebas de los servicios de CRM (spec 004, §9, nivel servicio)."""

from datetime import date
from decimal import Decimal

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.core.exceptions import CiudadFueraDelPais
from apps.core.tests.factories import CiudadFactory, PaisFactory
from apps.crm.enums import TipoCliente
from apps.crm.exceptions import (
    AgenteConClientes,
    AgenteInactivo,
    ClienteDuplicado,
    SinPerfilDeAgente,
    UsuarioNoEsAgente,
    UsuarioYaEsAgente,
)
from apps.crm.services import (
    actualizar_agente,
    actualizar_cliente,
    crear_agente,
    crear_cliente,
    desactivar_agente,
    desactivar_cliente,
    reasignar_cliente,
)
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import AgenteFactory, ClienteFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.10"


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


@pytest.fixture
def gerente():
    return usuario_con_rol(NombreRol.GERENTE)


def datos_persona(**cambios):
    datos = {
        "tipo": TipoCliente.PERSONA,
        "nombre": "Cliente",
        "apellidos": "Demo",
        "documento_identidad": "1234567890101",
        "pais": PaisFactory(),
        "agente_asignado": AgenteFactory(),
    }
    datos.update(cambios)
    return datos


# ---------- crear_agente ----------


def test_crear_agente_genera_el_codigo_y_audita_con_el_codigo_final(gerente):
    usuario = usuario_con_rol(NombreRol.AGENTE)

    agente = crear_agente(
        usuario_agente=usuario,
        porcentaje_comision=Decimal("3.50"),
        fecha_ingreso=date(2026, 10, 1),
        autor=gerente,
        ip=IP,
    )

    assert agente.codigo == f"AGT-{agente.pk:03d}"
    assert agente.creado_por == gerente
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.CREAR)
    assert registro.entidad == "crm_agente"
    assert registro.usuario == gerente
    assert registro.ip == IP
    assert registro.valores_nuevos["codigo"] == agente.codigo
    assert registro.valores_nuevos["porcentaje_comision"] == "3.50"


def test_crear_agente_rechaza_un_usuario_sin_rol_agente(gerente):
    with pytest.raises(UsuarioNoEsAgente):
        crear_agente(
            usuario_agente=usuario_con_rol(NombreRol.CONTABILIDAD),
            porcentaje_comision=Decimal("3"),
            fecha_ingreso=date(2026, 10, 1),
            autor=gerente,
            ip=IP,
        )


def test_crear_agente_rechaza_un_usuario_que_ya_tiene_perfil(gerente):
    existente = AgenteFactory()

    with pytest.raises(UsuarioYaEsAgente):
        crear_agente(
            usuario_agente=existente.usuario,
            porcentaje_comision=Decimal("3"),
            fecha_ingreso=date(2026, 10, 1),
            autor=gerente,
            ip=IP,
        )


# ---------- actualizar_agente ----------


def test_actualizar_agente_audita_solo_lo_que_cambio(gerente):
    agente = AgenteFactory(porcentaje_comision=Decimal("3.00"))

    actualizar_agente(
        agente=agente,
        datos={
            "porcentaje_comision": Decimal("4.25"),
            "fecha_ingreso": agente.fecha_ingreso,
        },
        autor=gerente,
        ip=IP,
    )

    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ACTUALIZAR)
    assert registro.valores_anteriores == {"porcentaje_comision": "3.00"}
    assert registro.valores_nuevos == {"porcentaje_comision": "4.25"}


def test_actualizar_agente_sin_cambios_no_audita(gerente):
    agente = AgenteFactory()

    actualizar_agente(
        agente=agente,
        datos={"porcentaje_comision": agente.porcentaje_comision},
        autor=gerente,
        ip=IP,
    )

    assert not LogAuditoria.objects.exists()


# ---------- desactivar_agente ----------


def test_desactivar_agente_sin_clientes_lo_desactiva_y_audita(gerente):
    agente = AgenteFactory()

    desactivar_agente(agente=agente, autor=gerente, ip=IP)

    agente.refresh_from_db()
    assert agente.activo is False
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.ELIMINAR
    assert registro.valores_nuevos == {"activo": False}


def test_desactivar_agente_con_clientes_activos_se_rechaza(gerente):
    """Regla 4."""
    cliente = ClienteFactory()

    with pytest.raises(AgenteConClientes) as error:
        desactivar_agente(agente=cliente.agente_asignado, autor=gerente, ip=IP)

    assert error.value.detalles["clientes_activos"] == 1


def test_un_cliente_desactivado_no_impide_desactivar_al_agente(gerente):
    cliente = ClienteFactory(activo=False)

    desactivar_agente(agente=cliente.agente_asignado, autor=gerente, ip=IP)

    cliente.agente_asignado.refresh_from_db()
    assert cliente.agente_asignado.activo is False


# ---------- crear_cliente ----------


def test_crear_cliente_genera_el_codigo_y_audita(gerente):
    cliente = crear_cliente(datos=datos_persona(), autor=gerente, ip=IP)

    assert cliente.codigo == f"CLI-{cliente.pk:05d}"
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.CREAR)
    assert registro.entidad == "crm_cliente"
    assert registro.valores_nuevos["codigo"] == cliente.codigo


def test_un_agente_que_crea_un_cliente_queda_asignado_aunque_envie_otro():
    """Regla 12."""
    agente = AgenteFactory()
    otro = AgenteFactory()

    cliente = crear_cliente(
        datos=datos_persona(agente_asignado=otro), autor=agente.usuario, ip=IP
    )

    assert cliente.agente_asignado == agente


def test_un_agente_sin_perfil_no_puede_crear_clientes():
    """Regla 12."""
    sin_perfil = usuario_con_rol(NombreRol.AGENTE)

    with pytest.raises(SinPerfilDeAgente):
        crear_cliente(datos=datos_persona(), autor=sin_perfil, ip=IP)


def test_crear_cliente_rechaza_un_agente_inactivo(gerente):
    """Regla 5."""
    with pytest.raises(AgenteInactivo):
        crear_cliente(
            datos=datos_persona(agente_asignado=AgenteFactory(activo=False)),
            autor=gerente,
            ip=IP,
        )


def test_crear_cliente_rechaza_una_ciudad_de_otro_pais(gerente):
    """Regla 9."""
    with pytest.raises(CiudadFueraDelPais):
        crear_cliente(datos=datos_persona(ciudad=CiudadFactory()), autor=gerente, ip=IP)


def test_crear_cliente_acepta_una_ciudad_de_su_pais(gerente):
    pais = PaisFactory()
    cliente = crear_cliente(
        datos=datos_persona(pais=pais, ciudad=CiudadFactory(pais=pais)),
        autor=gerente,
        ip=IP,
    )

    assert cliente.ciudad.pais == pais


def test_crear_cliente_normaliza_el_documento_y_detecta_el_duplicado(gerente):
    """Regla 7: el mismo documento escrito distinto es el mismo."""
    pais = PaisFactory()
    cliente = crear_cliente(
        datos=datos_persona(pais=pais, documento_identidad="1234 56789-0101"),
        autor=gerente,
        ip=IP,
    )
    assert cliente.documento_identidad == "1234567890101"

    with pytest.raises(ClienteDuplicado):
        crear_cliente(
            datos=datos_persona(pais=pais, documento_identidad="1234567890101"),
            autor=gerente,
            ip=IP,
        )


def test_el_nit_de_empresa_se_normaliza_en_mayusculas(gerente):
    cliente = crear_cliente(
        datos=datos_persona(
            tipo=TipoCliente.EMPRESA,
            nombre="",
            apellidos="",
            documento_identidad="",
            razon_social="Empresa Demo, S. A.",
            nit="1234567-k",
        ),
        autor=gerente,
        ip=IP,
    )

    assert cliente.nit == "1234567K"


# ---------- actualizar_cliente ----------


def test_actualizar_cliente_audita_solo_los_campos_que_cambiaron(gerente):
    cliente = ClienteFactory(telefono="")

    actualizar_cliente(
        cliente=cliente,
        datos={"telefono": "5555-0000", "nombre": cliente.nombre},
        autor=gerente,
        ip=IP,
    )

    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ACTUALIZAR)
    assert registro.valores_anteriores == {"telefono": ""}
    assert registro.valores_nuevos == {"telefono": "5555-0000"}


def test_actualizar_cliente_no_cambia_el_agente_ni_el_codigo(gerente):
    cliente = ClienteFactory(codigo="CLI-00001")
    agente_original = cliente.agente_asignado

    actualizar_cliente(
        cliente=cliente,
        datos={"agente_asignado": AgenteFactory(), "codigo": "CLI-99999"},
        autor=gerente,
        ip=IP,
    )

    cliente.refresh_from_db()
    assert cliente.agente_asignado == agente_original
    assert cliente.codigo == "CLI-00001"


def test_cambiar_solo_el_pais_valida_la_ciudad_que_ya_tenia(gerente):
    pais = PaisFactory()
    cliente = ClienteFactory(pais=pais, ciudad=CiudadFactory(pais=pais))

    with pytest.raises(CiudadFueraDelPais):
        actualizar_cliente(
            cliente=cliente, datos={"pais": PaisFactory()}, autor=gerente, ip=IP
        )


def test_editar_el_documento_al_de_otro_cliente_se_rechaza(gerente):
    pais = PaisFactory()
    ClienteFactory(pais=pais, documento_identidad="1111111111111")
    cliente = ClienteFactory(pais=pais, documento_identidad="2222222222222")

    with pytest.raises(ClienteDuplicado):
        actualizar_cliente(
            cliente=cliente,
            datos={"documento_identidad": "1111 1111 11111"},
            autor=gerente,
            ip=IP,
        )


def test_un_cliente_puede_guardarse_con_su_propio_documento(gerente):
    """Editar otros datos no debe chocar consigo mismo."""
    cliente = ClienteFactory()

    actualizar_cliente(
        cliente=cliente,
        datos={"documento_identidad": cliente.documento_identidad, "notas": "VIP"},
        autor=gerente,
        ip=IP,
    )

    cliente.refresh_from_db()
    assert cliente.notas == "VIP"


# ---------- desactivar y reasignar ----------


def test_desactivar_cliente_es_un_borrado_logico_auditado(gerente):
    cliente = ClienteFactory()

    desactivar_cliente(cliente=cliente, autor=gerente, ip=IP)

    cliente.refresh_from_db()
    assert cliente.activo is False
    assert LogAuditoria.objects.get().accion == AccionAuditoria.ELIMINAR


def test_reasignar_cambia_el_agente_y_audita_antes_y_despues(gerente):
    cliente = ClienteFactory()
    anterior = cliente.agente_asignado
    nuevo = AgenteFactory()

    reasignar_cliente(cliente=cliente, agente=nuevo, autor=gerente, ip=IP)

    cliente.refresh_from_db()
    assert cliente.agente_asignado == nuevo
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"agente_asignado": anterior.pk}
    assert registro.valores_nuevos == {"agente_asignado": nuevo.pk}


def test_reasignar_al_mismo_agente_no_cambia_nada_ni_audita(gerente):
    """Regla 8."""
    cliente = ClienteFactory()

    reasignar_cliente(
        cliente=cliente, agente=cliente.agente_asignado, autor=gerente, ip=IP
    )

    assert not LogAuditoria.objects.exists()


def test_reasignar_a_un_agente_inactivo_se_rechaza(gerente):
    """Regla 5."""
    cliente = ClienteFactory()

    with pytest.raises(AgenteInactivo):
        reasignar_cliente(
            cliente=cliente,
            agente=AgenteFactory(activo=False),
            autor=gerente,
            ip=IP,
        )
