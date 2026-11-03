"""R12 con pagos de servicios reales y evidencia histórica por abono."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.arrendamientos.services import registrar_pago_renta
from apps.auditoria.models import LogAuditoria
from apps.core.tests.factories import MonedaFactory, TipoCambioFactory
from apps.crm.tests.factories import ClienteFactory
from apps.reportes.catalogo import CATALOGO
from apps.reportes.estructuras import FiltrosIngresos
from apps.reportes.exceptions import DatosCobrosIncompletos
from apps.reportes.selectors_ingresos import resumir_ingresos, seleccionar_ingresos
from apps.reportes.services import obtener_reporte_exportacion
from apps.reportes.tests.test_comerciales import arrendar, vender
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory
from apps.ventas.services import anular_contrato, registrar_pago_cuota

pytestmark = pytest.mark.django_db


def abonar(cuota, monto, fecha):
    registrar_pago_cuota(
        cuota=cuota,
        monto=Decimal(monto),
        fecha=fecha,
        referencia="DEMO-R12",
        autor=None,
        ip=None,
    )


def test_quince_reportes_y_abonos_en_sus_meses_y_tasas():
    assert len(CATALOGO) == 15
    moneda = MonedaFactory(codigo="GTQ")
    usd = MonedaFactory(codigo="USD")
    hoy = timezone.localdate()
    inicio = date(hoy.year, hoy.month, 1) - timedelta(days=40)
    primero = date(inicio.year, inicio.month, 1)
    segundo = date(hoy.year, hoy.month, 1)
    TipoCambioFactory(
        moneda_origen=moneda, moneda_destino=usd, fecha=primero, tasa=Decimal("0.10")
    )
    TipoCambioFactory(
        moneda_origen=moneda, moneda_destino=usd, fecha=segundo, tasa=Decimal("0.20")
    )
    venta = vender(ClienteFactory(), moneda, dias=(hoy - primero).days, cuotas=2)
    cuota = venta.cuotas.first()
    abonar(cuota, "100.00", primero)
    abonar(cuota, "200.00", segundo)
    resumen = resumir_ingresos(filtros=FiltrosIngresos(origen="CUOTA"))
    assert resumen.count == 2
    assert resumen.totales["recibido_por_moneda"] == {"GTQ": Decimal("300.00")}
    assert resumen.totales["total_usd"] == Decimal("50.00")
    filtros = FiltrosIngresos(fecha_desde=primero, fecha_hasta=primero)
    fila = seleccionar_ingresos(filtros=filtros, offset=0, limite=25)[0]
    assert fila["recibido"] == Decimal("100.00")
    assert fila["fecha"] == primero
    assert resumir_ingresos(filtros=filtros).count == 1


def test_contado_enganche_renta_con_recargo_y_anulados():
    moneda = MonedaFactory(codigo="USD")
    cliente = ClienteFactory()
    contado = vender(cliente, moneda)
    financiado = vender(cliente, moneda, cuotas=2, enganche="100.00")
    anulado = vender(cliente, moneda, cuotas=2, enganche="200.00")
    anular_contrato(contrato=anulado, autor=None, ip=None)
    renta = arrendar(cliente, moneda)
    pago = renta.pagos.order_by("fecha_vencimiento").first()
    registrar_pago_renta(
        pago=pago,
        monto=Decimal("110.00"),
        fecha=timezone.localdate(),
        referencia="R12",
        autor=None,
        ip=None,
    )
    resumen = resumir_ingresos(filtros=FiltrosIngresos())
    assert resumen.count == 3
    assert resumen.totales["total_usd"] == Decimal("1410.00")
    resultado = seleccionar_ingresos(filtros=FiltrosIngresos(), offset=0, limite=25)
    assert {f["contrato"] for f in resultado} == {
        contado.codigo,
        financiado.codigo,
        renta.codigo,
    }
    assert next(f for f in resultado if f["origen"] == "RENTA")["recibido"] == Decimal(
        "110.00"
    )
    pais = contado.propiedad.ciudad.pais_id
    assert resumir_ingresos(filtros=FiltrosIngresos(pais=pais)).count == 1
    assert resumir_ingresos(filtros=FiltrosIngresos(moneda="GTQ")).count == 0


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("fecha", "2026-02-31"),
        ("pago", "NaN"),
        ("tasa_a_usd", None),
        ("tasa_a_usd", "0"),
    ],
)
def test_json_invalido_es_409_sin_500(campo, valor):
    venta = vender(ClienteFactory(), MonedaFactory(codigo="USD"), cuotas=2)
    abonar(venta.cuotas.first(), "100", timezone.localdate())
    log = LogAuditoria.objects.get(entidad="ventas_cuotapago")
    # Corrupción histórica simulada solo en la base de prueba; la aplicación
    # nunca modifica la bitácora. Se evita el modelo inmutable intencionalmente.
    import json

    datos = {**log.valores_nuevos, campo: valor}
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE auditoria_log_sistema SET valores_nuevos=%s WHERE id=%s",
            [json.dumps(datos), log.id],
        )
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre="GERENTE")))
    for sufijo in ("", "excel/", "pdf/"):
        respuesta = cliente.get(f"/api/v1/reportes/flujo-ingresos/{sufijo}")
        assert respuesta.status_code == 409
        assert respuesta.data["error"]["codigo"] == "DATOS_INCOMPLETOS"


def test_cuota_sin_log_rechaza_incluso_un_mes_acotado():
    venta = vender(ClienteFactory(), MonedaFactory(codigo="USD"), cuotas=2)
    abonar(venta.cuotas.first(), "100", timezone.localdate())
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM auditoria_log_sistema WHERE entidad='ventas_cuotapago'"
        )
    with pytest.raises(DatosCobrosIncompletos):
        resumir_ingresos(filtros=FiltrosIngresos(fecha_hasta=date(2000, 1, 1)))
    assert resumir_ingresos(filtros=FiltrosIngresos(origen="CONTADO")).count == 0


def test_paginacion_sql_totales_y_exportacion_de_todo():
    moneda = MonedaFactory(codigo="USD")
    cliente = ClienteFactory()
    for _ in range(30):
        vender(cliente, moneda)
    usuario = UsuarioFactory(rol=Rol.objects.get(nombre="GERENTE"))
    api = APIClient()
    api.force_authenticate(usuario)
    with CaptureQueriesContext(connection) as consultas:
        respuesta = api.get("/api/v1/reportes/flujo-ingresos/?page=2")
    assert respuesta.status_code == 200
    assert respuesta.data["filas"]["count"] == 30
    assert len(respuesta.data["filas"]["results"]) == 5
    assert respuesta.data["totales"]["total_usd"] == "36000.00"
    assert any("LIMIT 25 OFFSET 25" in c["sql"] for c in consultas)
    excel = api.get("/api/v1/reportes/flujo-ingresos/excel/")
    libro = load_workbook(BytesIO(excel.content))
    assert libro["Reporte"].max_row == 36
    assert api.get("/api/v1/reportes/flujo-ingresos/pdf/").content.startswith(b"%PDF-")
    resumen = resumir_ingresos(filtros=FiltrosIngresos())
    with (
        patch(
            "apps.reportes.services.resumir_reporte",
            return_value=replace(resumen, count=5001),
        ),
        patch("apps.reportes.services.seleccionar_filas_reporte") as detalles,
    ):
        from apps.reportes.exceptions import ReporteDemasiadoGrande

        with pytest.raises(ReporteDemasiadoGrande):
            obtener_reporte_exportacion(
                slug="flujo-ingresos", filtros=FiltrosIngresos(), usuario=usuario
            )
        detalles.assert_not_called()


@pytest.mark.parametrize("rol", NombreRol.values)
def test_permisos_catalogo_y_archivos(rol):
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    permitido = rol in ("ADMINISTRADOR", "GERENTE", "CONTABILIDAD")
    catalogo = cliente.get("/api/v1/reportes/").data["results"]
    assert any(r["codigo"] == "R12" for r in catalogo) == permitido
    for sufijo in ("", "excel/", "pdf/"):
        assert cliente.get(f"/api/v1/reportes/flujo-ingresos/{sufijo}").status_code == (
            200 if permitido else 403
        )


def test_filtros_invalidos_y_vacio():
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre="GERENTE")))
    for consulta in (
        "origen=OTRO",
        "moneda=gtq",
        "pais=0",
        "page=1&page=2",
        "fecha_desde=2026-11-02&fecha_hasta=2026-11-01",
        "origen=CUOTA&origen=RENTA",
    ):
        respuesta = cliente.get("/api/v1/reportes/flujo-ingresos/?" + consulta)
        assert respuesta.status_code in (400, 404)
    assert resumir_ingresos(filtros=FiltrosIngresos()).totales["total_usd"] == Decimal(
        "0.00"
    )
