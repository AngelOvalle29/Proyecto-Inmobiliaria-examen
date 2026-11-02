"""Pruebas de los endpoints de pagos a constructoras y del detalle del proyecto
con sus totales (spec 017, §9, nivel API)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.construccion.enums import EstadoPago
from apps.core.tests.factories import MonedaFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db

PROYECTOS = "/api/v1/proyectos-construccion/"
PAGOS = "/api/v1/pagos-constructora/"
HOY = timezone.localdate()
PAGAN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE, NombreRol.CONTABILIDAD]
NO_PAGAN = [NombreRol.AGENTE, NombreRol.CONSULTA]


def cliente_http(rol=NombreRol.GERENTE):
    http = APIClient()
    http.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return http


def crear_proyecto(presupuesto="1000.00"):
    respuesta = cliente_http().post(
        PROYECTOS,
        {
            "nombre": "Obra demo",
            "propiedad": PropiedadFactory(estado=EstadoPropiedad.ADQUIRIDA).pk,
            "constructora": ConstructoraFactory().pk,
            "fecha_inicio": (HOY - timedelta(days=10)).isoformat(),
            "fecha_fin_estimada": (HOY + timedelta(days=90)).isoformat(),
            "presupuesto_total": presupuesto,
            "moneda": MonedaFactory(codigo="USD").pk,
        },
        format="json",
    )
    return respuesta.json()


def programar(http, proyecto, monto="100.00", tipo="AVANCE"):
    return http.post(
        f"{PROYECTOS}{proyecto['id']}/pagos/",
        {"tipo": tipo, "monto": monto, "fecha_programada": HOY.isoformat()},
        format="json",
    )


@pytest.mark.parametrize("rol", PAGAN)
def test_administracion_gerencia_y_contabilidad_programan_y_pagan(rol):
    http = cliente_http(rol)
    proyecto = crear_proyecto()

    programado = programar(http, proyecto)
    assert programado.status_code == 201
    assert programado.json()["codigo"].startswith("PG-")
    assert programado.json()["moneda"]["codigo"] == "USD"

    pagado = http.post(
        f"{PAGOS}{programado.json()['id']}/pagar/",
        {"fecha_pago": HOY.isoformat(), "referencia_pago": "TRF-1"},
        format="json",
    )
    assert pagado.status_code == 200
    assert pagado.json()["estado"] == EstadoPago.PAGADO


@pytest.mark.parametrize("rol", NO_PAGAN)
def test_agente_y_consulta_leen_pero_no_programan_ni_pagan(rol):
    proyecto = crear_proyecto()
    pago = programar(cliente_http(), proyecto).json()
    http = cliente_http(rol)

    assert http.get(f"{PROYECTOS}{proyecto['id']}/pagos/").status_code == 200
    assert http.get(PAGOS).status_code == 200
    assert programar(http, proyecto).status_code == 403
    respuesta = http.post(
        f"{PAGOS}{pago['id']}/pagar/",
        {"fecha_pago": HOY.isoformat(), "referencia_pago": "x"},
        format="json",
    )
    assert respuesta.status_code == 403


def test_contabilidad_paga_pero_no_ejecuta_acciones_del_proyecto():
    """Regla 24: contabilidad registra pagos, no decide obras."""
    proyecto = crear_proyecto()
    respuesta = cliente_http(NombreRol.CONTABILIDAD).post(
        f"{PROYECTOS}{proyecto['id']}/iniciar/"
    )
    assert respuesta.status_code == 403


def test_un_pago_que_supera_el_presupuesto_responde_409():
    http = cliente_http()
    proyecto = crear_proyecto(presupuesto="1000.00")

    respuesta = programar(http, proyecto, monto="1000.01")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PRESUPUESTO_EXCEDIDO"


def test_un_finiquito_antes_de_finalizar_responde_409():
    respuesta = programar(cliente_http(), crear_proyecto(), tipo="FINIQUITO")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TRANSICION_INVALIDA"


def test_el_detalle_trae_total_comprometido_y_disponible():
    http = cliente_http()
    proyecto = crear_proyecto(presupuesto="1000.00")
    programar(http, proyecto, monto="250.00")

    detalle = http.get(f"{PROYECTOS}{proyecto['id']}/").json()

    assert detalle["total_comprometido"] == "250.00"
    assert detalle["disponible"] == "750.00"


def test_patch_responde_los_totales_al_dia():
    http = cliente_http()
    proyecto = crear_proyecto(presupuesto="1000.00")
    programar(http, proyecto, monto="250.00")

    respuesta = http.patch(
        f"{PROYECTOS}{proyecto['id']}/", {"presupuesto_total": "2000.00"}, format="json"
    )

    assert respuesta.json()["disponible"] == "1750.00"


def test_pagar_con_fecha_futura_responde_400_junto_al_campo():
    http = cliente_http()
    pago = programar(http, crear_proyecto()).json()

    respuesta = http.post(
        f"{PAGOS}{pago['id']}/pagar/",
        {"fecha_pago": (HOY + timedelta(days=1)).isoformat(), "referencia_pago": "x"},
        format="json",
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "FECHA_INVALIDA"
    assert "fecha_pago" in respuesta.json()["error"]["detalles"]


def test_anular_sin_motivo_responde_400_y_con_motivo_anula():
    http = cliente_http()
    pago = programar(http, crear_proyecto()).json()
    url = f"{PAGOS}{pago['id']}/anular/"

    assert http.post(url, {}, format="json").status_code == 400
    respuesta = http.post(url, {"motivo": "Duplicado"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoPago.ANULADO


def test_anular_un_pago_pagado_responde_409():
    http = cliente_http()
    pago = programar(http, crear_proyecto()).json()
    http.post(
        f"{PAGOS}{pago['id']}/pagar/",
        {"fecha_pago": HOY.isoformat(), "referencia_pago": "x"},
        format="json",
    )

    respuesta = http.post(
        f"{PAGOS}{pago['id']}/anular/", {"motivo": "x"}, format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TRANSICION_INVALIDA"


def test_los_pagos_de_un_proyecto_solo_son_los_suyos():
    http = cliente_http()
    uno, otro = crear_proyecto(), crear_proyecto()
    programar(http, uno)
    programar(http, otro)

    pagos = http.get(f"{PROYECTOS}{uno['id']}/pagos/").json()["results"]

    assert [p["proyecto"]["id"] for p in pagos] == [uno["id"]]


def test_los_pagos_de_un_proyecto_inexistente_responden_404():
    assert cliente_http().get(f"{PROYECTOS}999999/pagos/").status_code == 404


def test_el_listado_general_filtra_por_estado_y_proyecto():
    http = cliente_http()
    proyecto = crear_proyecto()
    pagado = programar(http, proyecto).json()
    programar(http, proyecto)
    http.post(
        f"{PAGOS}{pagado['id']}/pagar/",
        {"fecha_pago": HOY.isoformat(), "referencia_pago": "x"},
        format="json",
    )

    respuesta = http.get(PAGOS, {"estado": "PAGADO", "proyecto": proyecto["id"]})

    assert [p["id"] for p in respuesta.json()["results"]] == [pagado["id"]]
