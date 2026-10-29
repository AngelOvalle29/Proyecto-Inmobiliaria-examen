"""
Pruebas de los endpoints de ventas (spec 007, §9, nivel API).

Las reglas ya están probadas en los servicios. Aquí, lo que solo existe en la
capa HTTP: la matriz de permisos (reglas 20 a 22), la cartera, la validación
de entrada y el formato de los errores.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.core.tests.factories import MonedaFactory
from apps.crm.services import aprobar_cotizacion, crear_cotizacion, enviar_cotizacion
from apps.crm.tests.factories import ClienteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

CONTRATOS = "/api/v1/contratos-venta/"
HOY = timezone.localdate()


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


def http(usuario=None):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(user=usuario)
    return cliente


def financiado(cliente, **cambios):
    datos = {
        "cliente": cliente.pk,
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE).pk,
        "monto_total": "120000.00",
        "moneda": MonedaFactory(codigo="USD").pk,
        "fecha_firma": HOY.isoformat(),
        "modalidad": "FINANCIADO",
        "enganche": "20000.00",
        "numero_cuotas": 12,
        "tasa_interes_anual": "9.00",
        "fecha_primera_cuota": (HOY + timedelta(days=30)).isoformat(),
    }
    datos.update(cambios)
    return datos


def firmar(usuario, cliente, **cambios):
    return http(usuario).post(CONTRATOS, financiado(cliente, **cambios), format="json")


def test_sin_token_responde_401():
    assert http().get(CONTRATOS).status_code == 401


def test_un_agente_firma_para_su_cliente_y_ve_las_cuotas_con_mora():
    cliente = ClienteFactory()
    agente = cliente.agente_asignado.usuario

    respuesta = firmar(agente, cliente)

    assert respuesta.status_code == 201, respuesta.json()
    contrato = respuesta.json()
    assert contrato["codigo"].startswith("CV-")
    assert contrato["estado"] == "VIGENTE"
    assert len(contrato["cuotas"]) == 12
    assert contrato["cuotas"][0]["en_mora"] is False
    assert contrato["cuotas"][0]["saldo"] == contrato["cuotas"][0]["monto_total"]


def test_un_agente_no_firma_para_un_cliente_ajeno():
    ajeno = ClienteFactory()
    otro_agente = ClienteFactory().agente_asignado.usuario

    respuesta = firmar(otro_agente, ajeno)

    assert respuesta.status_code == 400
    assert "cliente" in respuesta.json()["error"]["detalles"]


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_contabilidad_y_consulta_no_firman(rol):
    assert firmar(usuario_con_rol(rol), ClienteFactory()).status_code == 403


def test_el_contrato_ajeno_responde_404():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    contrato = firmar(gerente, ClienteFactory()).json()
    otro_agente = ClienteFactory().agente_asignado.usuario

    assert http(otro_agente).get(f"{CONTRATOS}{contrato['id']}/").status_code == 404


def test_financiado_sin_plan_responde_400_indicando_los_campos():
    gerente = usuario_con_rol(NombreRol.GERENTE)

    respuesta = firmar(gerente, ClienteFactory(), numero_cuotas=None)

    # numero_cuotas=None llega como null: el serializador lo rechaza.
    assert respuesta.status_code == 400


def test_con_cotizacion_no_se_envian_los_datos_que_salen_de_ella():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    cotizacion = crear_cotizacion(
        datos={
            "cliente": ClienteFactory(),
            "propiedad": PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE),
            "fecha_vencimiento": HOY + timedelta(days=15),
        },
        autor=gerente,
        ip=None,
    )
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=None)
    aprobar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=None)

    con_monto = http(gerente).post(
        CONTRATOS,
        {
            "cotizacion": cotizacion.pk,
            "monto_total": "1.00",
            "fecha_firma": HOY.isoformat(),
            "modalidad": "CONTADO",
        },
        format="json",
    )
    assert con_monto.status_code == 400
    assert "monto_total" in con_monto.json()["error"]["detalles"]

    bien = http(gerente).post(
        CONTRATOS,
        {
            "cotizacion": cotizacion.pk,
            "fecha_firma": HOY.isoformat(),
            "modalidad": "CONTADO",
        },
        format="json",
    )
    assert bien.status_code == 201
    assert Decimal(bien.json()["monto_total"]) == cotizacion.total


def test_pagos_solo_los_registran_administracion_gerencia_y_contabilidad():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    cliente = ClienteFactory()
    cuota = firmar(gerente, cliente).json()["cuotas"][0]
    ruta = f"/api/v1/cuotas/{cuota['id']}/pagos/"
    pago = {"monto": "100.00", "fecha": HOY.isoformat(), "referencia": "DEP-1"}

    agente = cliente.agente_asignado.usuario
    assert http(agente).post(ruta, pago, format="json").status_code == 403

    respuesta = http(usuario_con_rol(NombreRol.CONTABILIDAD)).post(
        ruta, pago, format="json"
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "PARCIAL"
    assert Decimal(respuesta.json()["monto_pagado"]) == Decimal("100.00")


def test_un_pago_mayor_que_el_saldo_responde_400():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    cuota = firmar(gerente, ClienteFactory()).json()["cuotas"][0]

    respuesta = http(gerente).post(
        f"/api/v1/cuotas/{cuota['id']}/pagos/",
        {"monto": "999999.00", "fecha": HOY.isoformat(), "referencia": "X"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "PAGO_EXCEDE_SALDO"


def test_solo_administracion_y_gerencia_anulan():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    cliente = ClienteFactory()
    contrato = firmar(gerente, cliente).json()
    ruta = f"{CONTRATOS}{contrato['id']}/anular/"

    assert http(cliente.agente_asignado.usuario).post(ruta).status_code == 403
    respuesta = http(gerente).post(ruta)
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ANULADO"


def test_filtra_por_modalidad():
    gerente = usuario_con_rol(NombreRol.GERENTE)
    firmar(gerente, ClienteFactory())
    contado = financiado(ClienteFactory(), modalidad="CONTADO")
    for campo in [
        "enganche",
        "numero_cuotas",
        "tasa_interes_anual",
        "fecha_primera_cuota",
    ]:
        del contado[campo]
    assert http(gerente).post(CONTRATOS, contado, format="json").status_code == 201

    respuesta = http(gerente).get(CONTRATOS, {"modalidad": "FINANCIADO"})

    assert respuesta.json()["count"] == 1
