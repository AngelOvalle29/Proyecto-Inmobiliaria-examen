"""Pruebas de los servicios de ventas (spec 007, §9, nivel servicio)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.tests.factories import MonedaFactory, TipoCambioFactory
from apps.crm.exceptions import CotizacionYaContratada, SeVendePorUnidades
from apps.crm.services import (
    aprobar_cotizacion,
    crear_cotizacion,
    enviar_cotizacion,
    rechazar_cotizacion,
)
from apps.crm.tests.factories import AgenteFactory, ClienteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory
from apps.ventas.enums import EstadoContrato, EstadoCuota, ModalidadVenta
from apps.ventas.exceptions import (
    ContratoConPagos,
    ContratoNoVigente,
    CotizacionNoAprobada,
    EngancheFueraDeRango,
    PagoExcedeSaldo,
)
from apps.ventas.services import anular_contrato, firmar_contrato, registrar_pago_cuota

pytestmark = pytest.mark.django_db

IP = "203.0.113.30"
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD")


@pytest.fixture
def gtq(usd):
    """Quetzal con su tasa al dólar desde hace un mes (regla 14)."""
    moneda = MonedaFactory(codigo="GTQ")
    TipoCambioFactory(
        moneda_origen=moneda,
        moneda_destino=usd,
        tasa=Decimal("0.129032"),
        fecha=HOY - timedelta(days=30),
    )
    return moneda


def disponible(**cambios):
    return PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE, **cambios)


def datos_contado(**cambios):
    datos = {
        "cliente": ClienteFactory(),
        "propiedad": disponible(),
        "monto_total": Decimal("150000.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "fecha_firma": HOY,
        "modalidad": ModalidadVenta.CONTADO,
    }
    datos.update(cambios)
    return datos


def datos_financiado(**cambios):
    datos = datos_contado(
        modalidad=ModalidadVenta.FINANCIADO,
        enganche=Decimal("30000.00"),
        numero_cuotas=12,
        tasa_interes_anual=Decimal("12.00"),
        fecha_primera_cuota=HOY + timedelta(days=30),
    )
    datos.update(cambios)
    return datos


def cotizacion_aprobada(autor, bien):
    cotizacion = crear_cotizacion(
        datos={
            "cliente": ClienteFactory(),
            "propiedad": bien,
            "fecha_vencimiento": HOY + timedelta(days=15),
        },
        autor=autor,
        ip=IP,
    )
    enviar_cotizacion(cotizacion=cotizacion, autor=autor, ip=IP)
    return aprobar_cotizacion(cotizacion=cotizacion, autor=autor, ip=IP)


# ---------- Firmar sin cotización ----------


def test_firmar_de_contado_vende_el_bien_y_nace_liquidado(gerente):
    datos = datos_contado()

    contrato = firmar_contrato(datos=datos, autor=gerente, ip=IP)

    datos["propiedad"].refresh_from_db()
    assert contrato.codigo == f"CV-{contrato.pk:05d}"
    assert contrato.estado == EstadoContrato.LIQUIDADO
    assert not contrato.cuotas.exists()
    assert datos["propiedad"].estado == EstadoPropiedad.VENDIDA
    assert contrato.tasa_a_usd == 1
    assert contrato.monto_total_usd == Decimal("150000.00")


def test_la_comision_se_calcula_al_firmar_y_no_cambia_despues(gerente):
    """Regla 13."""
    agente = AgenteFactory(porcentaje_comision=Decimal("3.50"))
    contrato = firmar_contrato(
        datos=datos_contado(cliente=ClienteFactory(agente_asignado=agente)),
        autor=gerente,
        ip=IP,
    )
    agente.porcentaje_comision = Decimal("10.00")
    agente.save()

    contrato.refresh_from_db()
    assert contrato.comision_agente == Decimal("5250.00")


def test_firmar_financiado_genera_las_cuotas_y_audita_cuantas(gerente):
    contrato = firmar_contrato(datos=datos_financiado(), autor=gerente, ip=IP)

    cuotas = list(contrato.cuotas.all())
    assert contrato.estado == EstadoContrato.VIGENTE
    assert len(cuotas) == 12
    # El capital de las cuotas es el saldo: monto total menos enganche.
    assert sum(c.monto_capital for c in cuotas) == Decimal("120000.00")
    registro = LogAuditoria.objects.get(entidad="ventas_contratoventa")
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["cuotas_generadas"] == 12


def test_un_contrato_en_quetzales_guarda_la_tasa_al_dolar(gerente, gtq):
    """Regla 14."""
    contrato = firmar_contrato(
        datos=datos_contado(moneda=gtq, monto_total=Decimal("775000.00")),
        autor=gerente,
        ip=IP,
    )

    assert contrato.tasa_a_usd == Decimal("0.129032")
    assert contrato.monto_total_usd == Decimal("99999.80")


def test_sin_tasa_al_dolar_no_se_firma(gerente, usd):
    sin_tasa = MonedaFactory(codigo="MXN")

    with pytest.raises(TipoCambioNoDisponible):
        firmar_contrato(datos=datos_contado(moneda=sin_tasa), autor=gerente, ip=IP)


def test_no_se_vende_un_bien_que_no_esta_disponible(gerente):
    """Regla 8."""
    reservada = PropiedadFactory(estado=EstadoPropiedad.RESERVADA)

    with pytest.raises(PropiedadNoDisponible):
        firmar_contrato(datos=datos_contado(propiedad=reservada), autor=gerente, ip=IP)


def test_no_se_vende_un_edificio_completo(gerente):
    """Regla 9."""
    edificio = disponible(tipo=tipo("Apartamentos"))

    with pytest.raises(SeVendePorUnidades):
        firmar_contrato(datos=datos_contado(propiedad=edificio), autor=gerente, ip=IP)


def test_se_vende_una_unidad(gerente):
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)

    firmar_contrato(
        datos=datos_contado(propiedad=None, unidad=unidad), autor=gerente, ip=IP
    )

    unidad.refresh_from_db()
    assert unidad.estado == EstadoPropiedad.VENDIDA


def test_un_enganche_igual_al_total_se_rechaza(gerente):
    """Regla 11: el enganche no incluye el monto total."""
    with pytest.raises(EngancheFueraDeRango):
        firmar_contrato(
            datos=datos_financiado(enganche=Decimal("150000.00")),
            autor=gerente,
            ip=IP,
        )


# ---------- Firmar desde una cotización ----------


def test_firmar_desde_una_cotizacion_toma_sus_datos(gerente):
    propiedad = disponible(precio_lista=Decimal("80000.00"))
    cotizacion = cotizacion_aprobada(gerente, propiedad)

    contrato = firmar_contrato(
        datos={
            "cotizacion": cotizacion,
            "fecha_firma": HOY,
            "modalidad": ModalidadVenta.CONTADO,
        },
        autor=gerente,
        ip=IP,
    )

    propiedad.refresh_from_db()
    assert contrato.cliente == cotizacion.cliente
    assert contrato.monto_total == cotizacion.total
    assert propiedad.estado == EstadoPropiedad.VENDIDA


def test_una_cotizacion_no_da_dos_contratos(gerente):
    """Regla 7."""
    cotizacion = cotizacion_aprobada(gerente, disponible())
    datos = {"cotizacion": cotizacion, "fecha_firma": HOY, "modalidad": "CONTADO"}
    firmar_contrato(datos=datos, autor=gerente, ip=IP)

    with pytest.raises(CotizacionYaContratada):
        firmar_contrato(datos=datos, autor=gerente, ip=IP)


def test_una_cotizacion_contratada_no_se_rechaza(gerente):
    """Regla 6: rechazarla volvería a ofrecer un bien vendido."""
    propiedad = disponible()
    cotizacion = cotizacion_aprobada(gerente, propiedad)
    firmar_contrato(
        datos={"cotizacion": cotizacion, "fecha_firma": HOY, "modalidad": "CONTADO"},
        autor=gerente,
        ip=IP,
    )

    with pytest.raises(CotizacionYaContratada):
        rechazar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)
    propiedad.refresh_from_db()
    assert propiedad.estado == EstadoPropiedad.VENDIDA


def test_una_cotizacion_solo_enviada_no_se_firma(gerente):
    cotizacion = crear_cotizacion(
        datos={
            "cliente": ClienteFactory(),
            "propiedad": disponible(),
            "fecha_vencimiento": HOY + timedelta(days=15),
        },
        autor=gerente,
        ip=IP,
    )

    with pytest.raises(CotizacionNoAprobada):
        firmar_contrato(
            datos={
                "cotizacion": cotizacion,
                "fecha_firma": HOY,
                "modalidad": "CONTADO",
            },
            autor=gerente,
            ip=IP,
        )


# ---------- Anular (regla 15) ----------


def test_anular_sin_pagos_libera_el_bien_y_audita_anular(gerente):
    datos = datos_financiado()
    contrato = firmar_contrato(datos=datos, autor=gerente, ip=IP)

    anular_contrato(contrato=contrato, autor=gerente, ip=IP)

    contrato.refresh_from_db()
    datos["propiedad"].refresh_from_db()
    assert contrato.estado == EstadoContrato.ANULADO
    assert contrato.cuotas.count() == 12  # se conservan
    assert datos["propiedad"].estado == EstadoPropiedad.DISPONIBLE
    assert LogAuditoria.objects.filter(accion=AccionAuditoria.ANULAR).exists()


def test_con_un_pago_no_se_anula(gerente):
    contrato = firmar_contrato(datos=datos_financiado(), autor=gerente, ip=IP)
    registrar_pago_cuota(
        cuota=contrato.cuotas.first(),
        monto=Decimal("1.00"),
        fecha=HOY,
        referencia="DEP-1",
        autor=gerente,
        ip=IP,
    )

    with pytest.raises(ContratoConPagos):
        anular_contrato(contrato=contrato, autor=gerente, ip=IP)


def test_un_contrato_de_contado_no_se_anula(gerente):
    """Nace LIQUIDADO: ya está pagado."""
    contrato = firmar_contrato(datos=datos_contado(), autor=gerente, ip=IP)

    with pytest.raises(ContratoNoVigente):
        anular_contrato(contrato=contrato, autor=gerente, ip=IP)


# ---------- Pagos (reglas 14 y 16 a 18) ----------


def test_un_pago_parcial_deja_la_cuota_parcial_y_otro_la_completa(gerente, gtq):
    contrato = firmar_contrato(datos=datos_financiado(moneda=gtq), autor=gerente, ip=IP)
    cuota = contrato.cuotas.first()
    mitad = (cuota.monto_total / 2).quantize(Decimal("0.01"))

    registrar_pago_cuota(
        cuota=cuota, monto=mitad, fecha=HOY, referencia="A", autor=gerente, ip=IP
    )
    cuota.refresh_from_db()
    assert cuota.estado == EstadoCuota.PARCIAL
    assert cuota.tasa_a_usd_ultimo_pago == Decimal("0.129032")

    registrar_pago_cuota(
        cuota=cuota, monto=cuota.saldo, fecha=HOY, referencia="B", autor=gerente, ip=IP
    )
    cuota.refresh_from_db()
    assert cuota.estado == EstadoCuota.PAGADA
    assert cuota.referencia_ultimo_pago == "B"
    assert LogAuditoria.objects.filter(entidad="ventas_cuotapago").count() == 2


def test_un_pago_mayor_que_el_saldo_se_rechaza(gerente):
    contrato = firmar_contrato(datos=datos_financiado(), autor=gerente, ip=IP)
    cuota = contrato.cuotas.first()

    with pytest.raises(PagoExcedeSaldo):
        registrar_pago_cuota(
            cuota=cuota,
            monto=cuota.monto_total + Decimal("0.01"),
            fecha=HOY,
            referencia="X",
            autor=gerente,
            ip=IP,
        )


def test_al_pagar_la_ultima_cuota_el_contrato_queda_liquidado(gerente):
    contrato = firmar_contrato(
        datos=datos_financiado(numero_cuotas=2), autor=gerente, ip=IP
    )

    for cuota in contrato.cuotas.all():
        registrar_pago_cuota(
            cuota=cuota,
            monto=cuota.monto_total,
            fecha=HOY,
            referencia=f"C{cuota.numero}",
            autor=gerente,
            ip=IP,
        )

    contrato.refresh_from_db()
    assert contrato.estado == EstadoContrato.LIQUIDADO


def test_no_se_paga_en_un_contrato_anulado(gerente):
    contrato = firmar_contrato(datos=datos_financiado(), autor=gerente, ip=IP)
    anular_contrato(contrato=contrato, autor=gerente, ip=IP)

    with pytest.raises(ContratoNoVigente):
        registrar_pago_cuota(
            cuota=contrato.cuotas.first(),
            monto=Decimal("1.00"),
            fecha=date(2026, 12, 1),
            referencia="X",
            autor=gerente,
            ip=IP,
        )
