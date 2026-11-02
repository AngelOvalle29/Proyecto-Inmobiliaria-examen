"""Reglas de la spec 021 en R13 y R15, sobre los modelos de la spec 017.

Los contratos, proyectos y pagos se crean con el ORM para fijar estados y
montos exactos; las reglas de cómo llegan a esos estados las prueban compras y
construcción.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.tests.factories import PropiedadFactory
from apps.compras.models import ContratoCompra
from apps.compras.tests.factories import ProveedorFactory
from apps.construccion.models import PagoConstructora, ProyectoConstruccion
from apps.construccion.selectors import listar_proyectos_con_totales
from apps.construccion.tests.factories import ConstructoraFactory
from apps.core.tests.factories import MonedaFactory, PaisFactory
from apps.reportes.estructuras import FiltrosCompras, FiltrosObras
from apps.reportes.selectors_compras_obra import (
    resumir_compras,
    resumir_obras,
    seleccionar_compras,
    seleccionar_obras,
)
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db
HOY = timezone.localdate()


@pytest.fixture
def dolar():
    return MonedaFactory(codigo="USD")


def todas(seleccionar, filtros):
    return seleccionar(filtros=filtros, offset=0, limite=100)


# ---------- R13 Compras por proveedor ----------


def comprar(moneda, *, estado="COMPLETADO", proveedor=None, propiedad=None, **cambios):
    datos = dict(
        proveedor=proveedor or ProveedorFactory(),
        propiedad=propiedad or PropiedadFactory(),
        fecha_compra=date(2026, 4, 16),
        monto=Decimal("1000.00"),
        gastos_legales=Decimal("50.00"),
        impuestos=Decimal("30.00"),
        costo_total=Decimal("1080.00"),
        moneda=moneda,
        tasa_a_usd=Decimal("1"),
        costo_total_usd=Decimal("1080.00"),
        estado=estado,
    )
    datos.update(cambios)
    return ContratoCompra.objects.create(**datos)


def test_r13_solo_cuenta_las_compras_completadas(dolar):
    """Regla 16: una compra EN_PROCESO o ANULADO no es una adquisición."""
    comprar(dolar)
    comprar(dolar, estado="EN_PROCESO")
    comprar(dolar, estado="ANULADO")

    resumen = resumir_compras(filtros=FiltrosCompras())

    assert resumen.count == 1
    assert resumen.totales["costo_usd"] == Decimal("1080.00")


def test_r13_el_pais_es_el_de_la_propiedad_no_el_del_proveedor(dolar):
    pais = PaisFactory()
    propiedad = PropiedadFactory(ciudad__pais=pais)
    comprar(dolar, propiedad=propiedad)
    comprar(dolar, proveedor=ProveedorFactory(pais=pais))

    filas = todas(seleccionar_compras, FiltrosCompras(pais=pais.id))

    assert [f["propiedad_codigo"] for f in filas] == [propiedad.codigo]


def test_r13_no_suma_monedas_y_consolida_en_dolares(dolar):
    quetzal = MonedaFactory(codigo="GTQ")
    comprar(dolar)
    comprar(
        quetzal,
        monto=Decimal("7700.00"),
        gastos_legales=Decimal("0"),
        impuestos=Decimal("0"),
        costo_total=Decimal("7700.00"),
        tasa_a_usd=Decimal("0.13"),
        costo_total_usd=Decimal("1001.00"),
    )

    resumen = resumir_compras(filtros=FiltrosCompras())

    assert resumen.totales["costo_por_moneda"] == {
        "GTQ": Decimal("7700.00"),
        "USD": Decimal("1080.00"),
    }
    assert resumen.totales["costo_usd"] == Decimal("2081.00")


def test_r13_agrupa_por_proveedor_mes_y_moneda(dolar):
    proveedor = ProveedorFactory()
    comprar(dolar, proveedor=proveedor, fecha_compra=date(2026, 4, 1))
    comprar(dolar, proveedor=proveedor, fecha_compra=date(2026, 4, 30))
    comprar(dolar, proveedor=proveedor, fecha_compra=date(2026, 5, 2))

    grupos = resumir_compras(filtros=FiltrosCompras()).agrupamientos

    assert [(g.valores["mes"], g.valores["cantidad"]) for g in grupos] == [
        ("2026-04", 2),
        ("2026-05", 1),
    ]
    assert grupos[0].valores["costo_total"] == Decimal("2160.00")


# ---------- R15 Avance y presupuesto de obra ----------


def proyecto(moneda, *, estado="EN_EJECUCION", presupuesto="1000.00", **cambios):
    # Con el ORM no se asigna el código PC-NNNNN (lo pone el servicio): se fija
    # uno para poder encontrar la fila.
    datos = dict(
        codigo=f"PC-T{ProyectoConstruccion.objects.count() + 1:03d}",
        nombre="Obra de prueba",
        propiedad=PropiedadFactory(),
        constructora=ConstructoraFactory(),
        fecha_inicio=HOY - timedelta(days=60),
        fecha_fin_estimada=HOY + timedelta(days=60),
        presupuesto_total=Decimal(presupuesto),
        moneda=moneda,
        tasa_a_usd=Decimal("1"),
        presupuesto_total_usd=Decimal(presupuesto),
        estado=estado,
        porcentaje_avance=60,
    )
    datos.update(cambios)
    return ProyectoConstruccion.objects.create(**datos)


def pagar(obra, monto, estado, *, monto_usd=None):
    return PagoConstructora.objects.create(
        proyecto=obra,
        tipo="AVANCE",
        monto=Decimal(monto),
        moneda=obra.moneda,
        fecha_programada=HOY,
        estado=estado,
        fecha_pago=HOY if estado == "PAGADO" else None,
        # La base exige referencia en un pago PAGADO (spec 017, regla 21).
        referencia_pago="TRF-PRUEBA" if estado == "PAGADO" else "",
        tasa_a_usd=Decimal("1") if estado == "PAGADO" else None,
        monto_usd=Decimal(monto_usd or monto) if estado == "PAGADO" else None,
    )


def test_r15_coincide_con_el_detalle_del_proyecto(dolar):
    """Regla 16: comprometido y disponible como el detalle de la spec 017.
    Saldo por pagar es otra cosa: presupuesto menos lo pagado."""
    obra = proyecto(dolar)
    pagar(obra, "300.00", "PAGADO")
    pagar(obra, "200.00", "PROGRAMADO")
    pagar(obra, "999.00", "ANULADO")

    [fila] = todas(seleccionar_obras, FiltrosObras())
    detalle = listar_proyectos_con_totales().get(pk=obra.pk)

    assert fila["pagado"] == Decimal("300.00")
    assert fila["programado"] == Decimal("200.00")
    assert fila["comprometido"] == detalle.total_comprometido == Decimal("500.00")
    assert fila["disponible"] == detalle.disponible == Decimal("500.00")
    assert fila["saldo_por_pagar"] == Decimal("700.00")
    # El avance financiero no es el físico (60 %).
    assert fila["avance_financiero"] == Decimal("30.00")


def test_r15_agrupa_sin_repetir_el_presupuesto_por_cada_pago(dolar):
    """Con tres pagos, el presupuesto se cuenta una vez, no tres."""
    constructora = ConstructoraFactory()
    obra = proyecto(dolar, constructora=constructora)
    for _ in range(3):
        pagar(obra, "100.00", "PAGADO")

    [grupo] = resumir_obras(filtros=FiltrosObras()).agrupamientos

    assert grupo.valores["presupuesto_total"] == Decimal("1000.00")
    assert grupo.valores["pagado"] == Decimal("300.00")


def test_r15_el_total_en_dolares_solo_suma_pagos_realizados(dolar):
    obra = proyecto(dolar)
    pagar(obra, "300.00", "PAGADO", monto_usd="300.00")
    pagar(obra, "200.00", "PROGRAMADO")

    resumen = resumir_obras(filtros=FiltrosObras())

    assert resumen.totales["pagado_usd"] == Decimal("300.00")


def test_r15_desviacion_de_fechas(dolar):
    """Atrasada si pasó la fecha estimada; una cancelada no se califica."""
    atrasada = proyecto(dolar, fecha_fin_estimada=HOY - timedelta(days=5))
    terminada = proyecto(
        dolar,
        estado="FINALIZADO",
        fecha_fin_estimada=HOY - timedelta(days=10),
        fecha_fin_real=HOY - timedelta(days=7),
    )
    cancelada = proyecto(
        dolar, estado="CANCELADO", fecha_fin_estimada=HOY - timedelta(days=30)
    )

    filas = {f["codigo"]: f for f in todas(seleccionar_obras, FiltrosObras())}
    resumen = resumir_obras(filtros=FiltrosObras())

    assert filas[atrasada.codigo]["desviacion_dias"] == 5
    assert filas[terminada.codigo]["desviacion_dias"] == 3
    assert filas[cancelada.codigo]["desviacion_dias"] is None
    assert resumen.totales["atrasados"] == 2


# ---------- API ----------


@pytest.mark.parametrize("slug", ["compras-proveedores", "avance-presupuesto-obra"])
@pytest.mark.parametrize(
    ("rol", "estado"),
    [
        (NombreRol.ADMINISTRADOR, 200),
        (NombreRol.GERENTE, 200),
        (NombreRol.CONTABILIDAD, 200),
        (NombreRol.AGENTE, 403),
        (NombreRol.CONSULTA, 403),
    ],
)
def test_r13_y_r15_solo_para_finanzas(slug, rol, estado, dolar):
    """Regla 7: administración, gerencia y contabilidad."""
    comprar(dolar)
    proyecto(dolar)
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))

    respuesta = cliente.get(f"/api/v1/reportes/{slug}/")

    assert respuesta.status_code == estado
    if estado == 200:
        assert respuesta.json()["filas"]["count"] == 1
        assert cliente.get(f"/api/v1/reportes/{slug}/excel/").status_code == 200
