"""Reglas de la spec 021 en los reportes comerciales, con contratos reales."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.arrendamientos.models import ContratoArrendamiento
from apps.arrendamientos.services import (
    firmar_arrendamiento,
    registrar_pago_renta,
    rescindir_arrendamiento,
)
from apps.catalogo.tests.factories import PropiedadFactory
from apps.core.tests.factories import MonedaFactory
from apps.crm.services import (
    aprobar_cotizacion,
    crear_cotizacion,
    enviar_cotizacion,
    reasignar_cliente,
)
from apps.crm.tests.factories import AgenteFactory, ClienteFactory
from apps.reportes.estructuras import (
    FiltrosAgentes,
    FiltrosClientes,
    FiltrosCotizaciones,
    FiltrosEstadoCuenta,
    FiltrosMorosidad,
    FiltrosVentas,
)
from apps.reportes.selectors_comerciales import (
    REPORTES_COMERCIALES,
    resumir_agentes,
    resumir_clientes,
    resumir_cotizaciones,
    resumir_estado_cuenta,
    resumir_morosidad,
    resumir_ventas,
    seleccionar_agentes,
    seleccionar_clientes,
    seleccionar_cotizaciones,
    seleccionar_estado_cuenta,
    seleccionar_morosidad,
    seleccionar_ventas,
)
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory
from apps.ventas.services import anular_contrato, firmar_contrato, registrar_pago_cuota

pytestmark = pytest.mark.django_db
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


@pytest.fixture
def dolar():
    return MonedaFactory(codigo="USD")


def vender(cliente, moneda, *, dias=100, cuotas=None, cotizacion=None, enganche=0):
    """Firma una venta de 1,200: de contado, o financiada en cuotas sin interés."""
    datos = dict(
        fecha_firma=HOY - timedelta(days=dias),
        modalidad="FINANCIADO" if cuotas else "CONTADO",
    )
    if cotizacion:
        datos["cotizacion"] = cotizacion
    else:
        datos.update(
            cliente=cliente,
            propiedad=PropiedadFactory(estado="DISPONIBLE"),
            monto_total=Decimal("1200.00"),
            moneda=moneda,
        )
    if cuotas:
        datos.update(
            enganche=Decimal(enganche),
            numero_cuotas=cuotas,
            tasa_interes_anual=Decimal("0"),
            fecha_primera_cuota=HOY - timedelta(days=dias) + timedelta(days=30),
        )
    return firmar_contrato(datos=datos, autor=None, ip=None)


def arrendar(cliente, moneda, *, dias=100, meses=12):
    return firmar_arrendamiento(
        datos=dict(
            cliente=cliente,
            propiedad=PropiedadFactory(estado="DISPONIBLE"),
            fecha_inicio=HOY - timedelta(days=dias),
            duracion_meses=meses,
            renta_mensual=Decimal("100.00"),
            moneda=moneda,
            deposito=Decimal("0"),
            dia_cobro=1,
            dias_gracia=0,
            porcentaje_mora=Decimal("10.00"),
        ),
        autor=None,
        ip=None,
    )


def cotizar(cliente, *, hasta="APROBADA", descuento="50.00"):
    cotizacion = crear_cotizacion(
        datos=dict(
            cliente=cliente,
            propiedad=PropiedadFactory(
                estado="DISPONIBLE", precio_lista=Decimal("1000.00")
            ),
            unidad=None,
            fecha_vencimiento=HOY + timedelta(days=10),
            descuento=Decimal(descuento),
        ),
        autor=None,
        ip=None,
    )
    if hasta != "BORRADOR":
        enviar_cotizacion(cotizacion=cotizacion, autor=None, ip=None)
    if hasta == "APROBADA":
        aprobar_cotizacion(cotizacion=cotizacion, autor=None, ip=None)
    return cotizacion


def filas(seleccionar, filtros, usuario):
    return seleccionar(filtros=filtros, usuario=usuario, offset=0, limite=100)


def test_r01_separa_monedas_y_no_inventa_descuento(gerente, dolar):
    cliente = ClienteFactory()
    vender(cliente, dolar)
    cotizacion = cotizar(cliente)
    vender(None, None, cotizacion=cotizacion)
    anulado = vender(cliente, dolar, cuotas=2)
    anular_contrato(contrato=anulado, autor=None, ip=None)

    resumen = resumir_ventas(filtros=FiltrosVentas(), usuario=gerente)
    resultado = filas(seleccionar_ventas, FiltrosVentas(), gerente)

    assert resumen.count == 2  # el anulado no es una venta
    assert resumen.totales["con_cotizacion"] == 1
    moneda = cotizacion.moneda.codigo
    assert resumen.totales["por_moneda"][moneda]["descuento"] == Decimal("50.00")
    sin_cotizacion = next(f for f in resultado if f["bruto"] is None)
    assert sin_cotizacion["descuento"] is None
    assert sin_cotizacion["modalidad"] == "Contado"


def test_r01_filtra_por_periodo_inclusivo_y_agrupa_por_mes(gerente, dolar):
    cliente = ClienteFactory()
    contrato = vender(cliente, dolar, dias=40)
    vender(cliente, dolar, dias=5)

    filtros = FiltrosVentas(
        fecha_desde=contrato.fecha_firma, fecha_hasta=contrato.fecha_firma
    )
    resumen = resumir_ventas(filtros=filtros, usuario=gerente)

    assert resumen.count == 1
    assert resumen.agrupamientos[0].valores["cantidad"] == 1
    assert contrato.fecha_firma.strftime("%Y-%m") in resumen.agrupamientos[0].etiqueta


def test_r01_el_agente_no_ve_totales_de_otra_cartera(dolar):
    propio = ClienteFactory()
    ajeno = ClienteFactory()
    vender(propio, dolar)
    vender(ajeno, dolar)
    agente = propio.agente_asignado.usuario

    resumen = resumir_ventas(filtros=FiltrosVentas(), usuario=agente)

    assert resumen.count == 1
    assert resumen.totales["por_moneda"]["USD"]["neto"] == Decimal("1200.00")


def test_r02_cohorte_sin_borradores_y_venta_directa_aparte(gerente, dolar):
    cliente = ClienteFactory()
    agente = cliente.agente_asignado
    cotizar(cliente, hasta="BORRADOR")
    cotizar(cliente, hasta="ENVIADA")
    vender(None, None, cotizacion=cotizar(cliente))
    vender(cliente, dolar)

    fila = filas(seleccionar_agentes, FiltrosAgentes(agente=agente.pk), gerente)[0]

    assert fila["emitidas"] == 2
    assert fila["aprobadas"] == 1
    assert fila["vinculadas"] == 1
    assert fila["ventas_directas"] == 1
    assert fila["conversion_pct"] == Decimal("50.00")


def test_r02_sin_cotizaciones_la_conversion_es_null_no_cero(gerente):
    agente = AgenteFactory()

    fila = filas(seleccionar_agentes, FiltrosAgentes(agente=agente.pk), gerente)[0]
    resumen = resumir_agentes(filtros=FiltrosAgentes(agente=agente.pk), usuario=gerente)

    assert fila["conversion_pct"] is None
    assert resumen.totales["conversion_pct"] is None


def test_r02_un_agente_ve_solo_su_fila_tras_reasignar(dolar):
    cliente = ClienteFactory()
    anterior = cliente.agente_asignado
    vender(cliente, dolar)
    nuevo = AgenteFactory()
    reasignar_cliente(cliente=cliente, agente=nuevo, autor=None, ip=None)

    resultado = filas(seleccionar_agentes, FiltrosAgentes(), nuevo.usuario)
    otro = FiltrosAgentes(agente=anterior.pk)

    assert [f["codigo"] for f in resultado] == [nuevo.codigo]
    assert filas(seleccionar_agentes, otro, nuevo.usuario) == []


def test_r03_cuenta_estados_y_conversion_de_la_cohorte(gerente):
    cliente = ClienteFactory()
    cotizar(cliente, hasta="BORRADOR")
    cotizar(cliente, hasta="ENVIADA")
    firmada = cotizar(cliente)
    contrato = vender(None, None, cotizacion=firmada)

    resumen = resumir_cotizaciones(filtros=FiltrosCotizaciones(), usuario=gerente)
    resultado = filas(seleccionar_cotizaciones, FiltrosCotizaciones(), gerente)

    assert resumen.count == 3
    assert resumen.totales["por_estado"]["Borrador"] == 1
    assert resumen.totales["con_contrato"] == 1
    assert resumen.totales["conversion_pct"] == Decimal("33.33")
    assert resumen.totales["aprobacion_pct"] == Decimal("50.00")
    con_contrato = next(f for f in resultado if f["estado"] == "Aprobada")
    assert con_contrato["contrato"] == contrato.codigo


def test_r03_un_contrato_anulado_no_cuenta_como_conversion(gerente):
    cliente = ClienteFactory()
    contrato = vender(None, None, cotizacion=cotizar(cliente), dias=1)
    contrato.estado = "VIGENTE"
    contrato.save(update_fields=["estado"])
    anular_contrato(contrato=contrato, autor=None, ip=None)

    resumen = resumir_cotizaciones(filtros=FiltrosCotizaciones(), usuario=gerente)
    resultado = filas(seleccionar_cotizaciones, FiltrosCotizaciones(), gerente)

    assert resumen.totales["con_contrato"] == 0
    assert resumen.totales["conversion_pct"] == Decimal("0.00")
    assert resultado[0]["contrato"] is None


def test_r04_ordena_por_venta_usd_y_no_mezcla_rentas(gerente, dolar):
    con_venta = ClienteFactory()
    solo_renta = ClienteFactory()
    sin_nada = ClienteFactory()
    vender(con_venta, dolar)
    arrendar(solo_renta, dolar)

    resultado = filas(seleccionar_clientes, FiltrosClientes(), gerente)
    resumen = resumir_clientes(filtros=FiltrosClientes(), usuario=gerente)

    assert [f["id"] for f in resultado] == [con_venta.pk, solo_renta.pk]
    assert sin_nada.pk not in [f["id"] for f in resultado]
    assert resultado[0]["vendido_usd"] == Decimal("1200.00")
    assert resultado[1]["vendido_usd"] == 0
    assert resumen.totales["vendido_usd"] == Decimal("1200.00")


def test_r04_el_saldo_cuenta_cuotas_futuras_pero_no_rentas_futuras(gerente, dolar):
    cliente = ClienteFactory()
    vender(cliente, dolar, cuotas=12, dias=10)
    arrendar(cliente, dolar, dias=70, meses=12)

    fila = filas(seleccionar_clientes, FiltrosClientes(), gerente)[0]
    resumen = resumir_clientes(filtros=FiltrosClientes(), usuario=gerente)

    # 1,200 de cuotas firmadas, más solo las rentas ya vencidas.
    vencidas = ContratoArrendamiento.objects.get().pagos.filter(
        fecha_vencimiento__lt=HOY
    )
    esperado = Decimal("1200.00") + vencidas.count() * Decimal("100.00")
    assert resumen.totales["saldos_actuales"]["USD"] == esperado
    assert fila["saldos"] == f"USD {esperado:,.2f}"


def test_r04_un_contrato_anulado_no_deja_deuda(gerente, dolar):
    cliente = ClienteFactory()
    contrato = vender(cliente, dolar, cuotas=2)
    anular_contrato(contrato=contrato, autor=None, ip=None)
    vender(cliente, dolar)

    resumen = resumir_clientes(filtros=FiltrosClientes(), usuario=gerente)

    assert resumen.totales["saldos_actuales"] == {}


def test_r10_no_lista_rentas_futuras_ni_canceladas(gerente, dolar):
    cliente = ClienteFactory()
    contrato = arrendar(cliente, dolar, dias=70, meses=12)
    pendientes = contrato.pagos.filter(fecha_vencimiento__lt=HOY).count()
    assert pendientes

    resultado = filas(seleccionar_estado_cuenta, FiltrosEstadoCuenta(), gerente)

    assert len(resultado) == pendientes
    assert all(f["fecha_vencimiento"] < HOY for f in resultado)
    assert all(f["mora"] == "Sí" for f in resultado)


def test_r10_renta_pagada_con_recargo_sin_saldo_ni_doble_suma(gerente, dolar):
    cliente = ClienteFactory()
    contrato = arrendar(cliente, dolar, dias=70, meses=12)
    pago = contrato.pagos.order_by("fecha_vencimiento").first()
    registrar_pago_renta(
        pago=pago,
        fecha=HOY,
        monto=Decimal("110.00"),
        referencia="R-1",
        autor=None,
        ip=None,
    )

    resultado = filas(
        seleccionar_estado_cuenta, FiltrosEstadoCuenta(estado="PAGADO"), gerente
    )
    resumen = resumir_estado_cuenta(
        filtros=FiltrosEstadoCuenta(estado="PAGADO"), usuario=gerente
    )

    assert resultado[0]["exigible"] == Decimal("110.00")
    assert resultado[0]["pagado"] == Decimal("110.00")
    assert resultado[0]["saldo"] == 0
    assert resumen.totales["por_moneda"]["USD"]["pagado"] == Decimal("110.00")


def test_r10_cuota_parcial_y_contrato_anulado(gerente, dolar):
    cliente = ClienteFactory()
    contrato = vender(cliente, dolar, cuotas=2, dias=90)
    anulado = vender(cliente, dolar, cuotas=2, dias=90)
    anular_contrato(contrato=anulado, autor=None, ip=None)
    cuota = contrato.cuotas.get(numero=1)
    registrar_pago_cuota(
        cuota=cuota,
        monto=Decimal("200.00"),
        fecha=HOY,
        referencia="C-1",
        autor=None,
        ip=None,
    )

    resultado = filas(seleccionar_estado_cuenta, FiltrosEstadoCuenta(), gerente)
    resumen = resumir_estado_cuenta(filtros=FiltrosEstadoCuenta(), usuario=gerente)

    assert len(resultado) == 2
    assert {f["contrato_codigo"] for f in resultado} == {contrato.codigo}
    assert resultado[0]["saldo"] == cuota.monto_total - Decimal("200.00")
    assert resumen.totales["por_moneda"]["USD"]["saldo"] == Decimal("1000.00")
    assert resumen.agrupamientos[0].valores["cantidad"] == 2


def test_r11_clasifica_por_tramo_y_excluye_lo_no_vencido(gerente, dolar):
    cliente = ClienteFactory()
    contrato = vender(cliente, dolar, cuotas=2, dias=61)
    contrato.cuotas.filter(numero=1).update(fecha_vencimiento=HOY - timedelta(days=30))
    contrato.cuotas.filter(numero=2).update(fecha_vencimiento=HOY)

    resumen = resumir_morosidad(filtros=FiltrosMorosidad(), usuario=gerente)
    resultado = filas(seleccionar_morosidad, FiltrosMorosidad(), gerente)

    assert resumen.count == 1
    assert resultado[0]["dias_atraso"] == 30
    assert resultado[0]["tramo"] == "1 a 30 días"
    assert resumen.agrupamientos[0].valores["cantidad"] == 1


@pytest.mark.parametrize(
    ("dias", "tramo"),
    [
        (1, "1 a 30 días"),
        (30, "1 a 30 días"),
        (31, "31 a 60 días"),
        (60, "31 a 60 días"),
        (61, "61 a 90 días"),
        (90, "61 a 90 días"),
        (91, "Más de 90 días"),
    ],
)
def test_r11_los_totales_y_el_detalle_usan_el_mismo_tramo(gerente, dolar, dias, tramo):
    contrato = vender(ClienteFactory(), dolar, cuotas=1, dias=200)
    contrato.cuotas.update(fecha_vencimiento=HOY - timedelta(days=dias))

    resumen = resumir_morosidad(filtros=FiltrosMorosidad(), usuario=gerente)
    fila = filas(seleccionar_morosidad, FiltrosMorosidad(), gerente)[0]

    assert fila["tramo"] == tramo
    grupo = next(g for g in resumen.agrupamientos if g.etiqueta == tramo)
    assert grupo.valores["cantidad"] == 1


def test_r11_une_cuotas_y_rentas_y_excluye_anulados(gerente, dolar):
    cliente = ClienteFactory()
    anulado = vender(cliente, dolar, cuotas=1, dias=60)
    anular_contrato(contrato=anulado, autor=None, ip=None)
    vender(cliente, dolar, cuotas=1, dias=60)
    arrendar(cliente, dolar, dias=70)

    resultado = filas(seleccionar_morosidad, FiltrosMorosidad(), gerente)

    origenes = {f["origen"] for f in resultado}
    assert origenes == {"Cuota", "Renta"}
    assert sum(f["origen"] == "Cuota" for f in resultado) == 1


def test_r11_una_renta_rescindida_vencida_se_sigue_debiendo(gerente, dolar):
    contrato = arrendar(ClienteFactory(), dolar, dias=70)
    rescindir_arrendamiento(contrato=contrato, fecha_rescision=HOY, autor=None, ip=None)

    resumen = resumir_morosidad(filtros=FiltrosMorosidad(), usuario=gerente)

    assert resumen.count == contrato.pagos.filter(fecha_vencimiento__lt=HOY).count()
    assert resumen.count > 0


def test_r11_el_agente_no_amplia_su_cartera_con_el_filtro(dolar):
    propio = ClienteFactory()
    ajeno = ClienteFactory()
    vender(propio, dolar, cuotas=1, dias=60)
    vender(ajeno, dolar, cuotas=1, dias=60)
    usuario = propio.agente_asignado.usuario

    filtros = FiltrosMorosidad(agente=ajeno.agente_asignado.pk)

    assert resumir_morosidad(filtros=filtros, usuario=usuario).count == 0
    assert filas(seleccionar_morosidad, filtros, usuario) == []


@pytest.mark.parametrize("slug", sorted(REPORTES_COMERCIALES))
@pytest.mark.parametrize("rol", NombreRol.values)
def test_cada_rol_consulta_y_exporta_a_excel_con_la_demo(slug, rol, monkeypatch):
    monkeypatch.delenv("DEMO_AGENTES_PASSWORD", raising=False)
    call_command("seed_demo")
    usuario = UsuarioFactory(rol=Rol.objects.get(nombre=rol))
    cliente = APIClient()
    cliente.force_authenticate(usuario)

    respuesta = cliente.get(f"/api/v1/reportes/{slug}/")
    excel = cliente.get(f"/api/v1/reportes/{slug}/excel/")

    assert respuesta.status_code == 200, respuesta.json()
    assert excel.status_code == 200
    if rol != NombreRol.AGENTE:
        assert respuesta.json()["filas"]["count"] > 0


def test_el_monto_exige_moneda(gerente):
    cliente = APIClient()
    cliente.force_authenticate(gerente)

    respuesta = cliente.get("/api/v1/reportes/morosidad/", {"saldo_min": "10"})

    assert respuesta.status_code == 400
