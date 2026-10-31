"""
Pruebas de los endpoints de arrendamientos (spec 008, §9, nivel API): matriz de
permisos (reglas 13 a 16), cartera, validación de entrada y formato de los
errores. Las reglas ya están probadas en los servicios.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.arrendamientos.models import ContratoArrendamiento
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.core.tests.factories import MonedaFactory
from apps.crm.tests.factories import ClienteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

CONTRATOS = "/api/v1/contratos-arrendamiento/"
HOY = timezone.localdate()


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


def http(usuario=None):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(user=usuario)
    return cliente


def entrada(cliente, **cambios):
    datos = {
        "cliente": cliente.pk,
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE).pk,
        "fecha_inicio": HOY.isoformat(),
        "duracion_meses": 6,
        "renta_mensual": "1000.00",
        "moneda": MonedaFactory(codigo="USD").pk,
        "deposito": "2000.00",
        "dia_cobro": 5,
        "dias_gracia": 5,
        "porcentaje_mora": "5.00",
    }
    datos.update(cambios)
    return datos


def firmar(usuario, cliente=None, **cambios):
    cliente = cliente or ClienteFactory()
    return http(usuario).post(CONTRATOS, entrada(cliente, **cambios), format="json")


def test_sin_token_responde_401():
    assert http().get(CONTRATOS).status_code == 401


def test_un_agente_arrienda_a_su_cliente_y_ve_el_calendario():
    cliente = ClienteFactory()

    respuesta = firmar(cliente.agente_asignado.usuario, cliente)

    assert respuesta.status_code == 201, respuesta.json()
    contrato = respuesta.json()
    assert contrato["codigo"].startswith("ARR-")
    assert len(contrato["pagos"]) == 6
    assert contrato["pagos"][0]["en_mora"] is False


def test_un_agente_no_arrienda_a_un_cliente_ajeno():
    otro_agente = ClienteFactory().agente_asignado.usuario

    respuesta = firmar(otro_agente, ClienteFactory())

    assert respuesta.status_code == 400
    assert "cliente" in respuesta.json()["error"]["detalles"]


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_contabilidad_y_consulta_no_firman(rol):
    assert firmar(usuario_con_rol(rol)).status_code == 403


def test_un_dia_de_cobro_29_responde_400():
    """Regla 3: del 1 al 28, para que todos los meses lo tengan."""
    respuesta = firmar(usuario_con_rol(NombreRol.GERENTE), dia_cobro=29)

    assert respuesta.status_code == 400
    assert "dia_cobro" in respuesta.json()["error"]["detalles"]


def test_el_contrato_ajeno_responde_404():
    contrato = firmar(usuario_con_rol(NombreRol.GERENTE)).json()
    otro_agente = ClienteFactory().agente_asignado.usuario

    assert http(otro_agente).get(f"{CONTRATOS}{contrato['id']}/").status_code == 404


def test_solo_administracion_y_gerencia_rescinden_y_finalizan():
    cliente = ClienteFactory()
    contrato = firmar(usuario_con_rol(NombreRol.GERENTE), cliente).json()
    agente = http(cliente.agente_asignado.usuario)
    ruta = f"{CONTRATOS}{contrato['id']}"

    rescindir = {"fecha_rescision": HOY.isoformat()}
    assert (
        agente.post(f"{ruta}/rescindir/", rescindir, format="json").status_code == 403
    )
    assert agente.post(f"{ruta}/finalizar/").status_code == 403


def test_finalizar_antes_del_fin_responde_409():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    contrato = firmar(gerente).json()

    respuesta = http(gerente).post(f"{CONTRATOS}{contrato['id']}/finalizar/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CONTRATO_NO_TERMINADO"


def test_una_rescision_futura_responde_400():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    contrato = firmar(gerente).json()

    respuesta = http(gerente).post(
        f"{CONTRATOS}{contrato['id']}/rescindir/",
        {"fecha_rescision": (HOY + timedelta(days=1)).isoformat()},
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "FECHA_RESCISION_INVALIDA"


def test_el_agente_renueva_su_contrato():
    cliente = ClienteFactory()
    agente = cliente.agente_asignado.usuario
    contrato = firmar(agente, cliente).json()

    respuesta = http(agente).post(
        f"{CONTRATOS}{contrato['id']}/renovar/",
        {"renta_mensual": "1100.00", "duracion_meses": 12},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["contrato_anterior"] == contrato["id"]
    assert len(respuesta.json()["pagos"]) == 12


def test_pagos_de_renta_los_registran_administracion_gerencia_y_contabilidad():
    cliente = ClienteFactory()
    pago = firmar(usuario_con_rol(NombreRol.GERENTE), cliente).json()["pagos"][0]
    ruta = f"/api/v1/pagos-renta/{pago['id']}/pagar/"
    cuerpo = {"fecha": HOY.isoformat(), "monto": "1000.00", "referencia": "DEP-1"}

    agente = http(cliente.agente_asignado.usuario)
    assert agente.post(ruta, cuerpo, format="json").status_code == 403

    respuesta = http(usuario_con_rol(NombreRol.CONTABILIDAD)).post(
        ruta, cuerpo, format="json"
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "PAGADO"


def test_un_monto_equivocado_responde_400_con_el_esperado():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    pago = firmar(gerente).json()["pagos"][0]

    respuesta = http(gerente).post(
        f"/api/v1/pagos-renta/{pago['id']}/pagar/",
        {"fecha": HOY.isoformat(), "monto": "100.00", "referencia": "X"},
        format="json",
    )

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "MONTO_INCORRECTO"
    assert Decimal(error["detalles"]["esperado"]) == Decimal("1000.00")


def test_filtra_por_estado():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    firmar(gerente)
    contrato = firmar(gerente).json()
    http(gerente).post(
        f"{CONTRATOS}{contrato['id']}/rescindir/",
        {"fecha_rescision": HOY.isoformat()},
        format="json",
    )

    respuesta = http(gerente).get(CONTRATOS, {"estado": "RESCINDIDO"})

    assert [c["id"] for c in respuesta.json()["results"]] == [contrato["id"]]


def test_seed_demo_carga_un_arrendamiento_con_pagos_y_mora(monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)

    call_command("seed_demo")
    call_command("seed_demo")

    contrato = ContratoArrendamiento.objects.get()
    pagos = list(contrato.pagos.order_by("fecha_vencimiento")[:3])
    assert [p.estado for p in pagos] == ["PAGADO", "PAGADO", "PENDIENTE"]
    assert pagos[0].mora_aplicada == 0
    assert pagos[1].mora_aplicada > 0  # pagado tarde, con recargo
    assert pagos[2].en_mora()
