"""Pruebas de los servicios de arrendamientos (spec 008, §9, nivel servicio)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.arrendamientos.enums import EstadoArrendamiento, EstadoPagoRenta
from apps.arrendamientos.exceptions import (
    ArrendamientoNoVigente,
    ContratoNoTerminado,
    ContratoYaRenovado,
    FechaPagoRentaInvalida,
    FechaRescisionInvalida,
    MontoIncorrecto,
    PagoNoPendiente,
    SeArriendaPorUnidades,
)
from apps.arrendamientos.models import ContratoArrendamiento, PagoRenta
from apps.arrendamientos.services import (
    finalizar_arrendamiento,
    firmar_arrendamiento,
    registrar_pago_renta,
    renovar_arrendamiento,
    rescindir_arrendamiento,
)
from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.core.tests.factories import MonedaFactory
from apps.crm.tests.factories import ClienteFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.40"
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


def datos(**cambios):
    base = {
        "cliente": ClienteFactory(),
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE),
        "fecha_inicio": HOY,
        "duracion_meses": 12,
        "renta_mensual": Decimal("1000.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "deposito": Decimal("2000.00"),
        "dia_cobro": 5,
        "dias_gracia": 5,
        "porcentaje_mora": Decimal("5.00"),
    }
    base.update(cambios)
    return base


def firmar(autor, **cambios):
    return firmar_arrendamiento(datos=datos(**cambios), autor=autor, ip=IP)


def atrasar(contrato, dias):
    """Mueve el contrato y sus pagos hacia el pasado, como si se hubiera
    firmado hace `dias` días."""
    delta = timedelta(days=dias)
    ContratoArrendamiento.objects.filter(pk=contrato.pk).update(
        fecha_inicio=contrato.fecha_inicio - delta,
        fecha_fin=contrato.fecha_fin - delta,
    )
    for pago in contrato.pagos.all():
        pago.fecha_vencimiento -= delta
        pago.save(update_fields=["fecha_vencimiento"])
    contrato.refresh_from_db()
    return contrato


# ---------- Firmar (reglas 1 a 5) ----------


def test_firmar_arrienda_el_bien_y_genera_un_pago_por_mes(gerente):
    contrato = firmar(gerente)

    contrato.propiedad.refresh_from_db()
    assert contrato.codigo == f"ARR-{contrato.pk:05d}"
    assert contrato.propiedad.estado == EstadoPropiedad.ARRENDADA
    assert contrato.pagos.count() == 12
    assert {p.monto for p in contrato.pagos.all()} == {Decimal("1000.00")}
    assert contrato.agente == contrato.cliente.agente_asignado
    assert contrato.tasa_a_usd == 1
    registro = LogAuditoria.objects.get(entidad="arrendamientos_contratoarrendamiento")
    assert registro.valores_nuevos["pagos_generados"] == 12


def test_no_se_arrienda_un_bien_no_disponible(gerente):
    with pytest.raises(PropiedadNoDisponible):
        firmar(gerente, propiedad=PropiedadFactory(estado=EstadoPropiedad.VENDIDA))


def test_no_se_arrienda_un_edificio_completo(gerente):
    edificio = PropiedadFactory(
        estado=EstadoPropiedad.DISPONIBLE, tipo=tipo("Apartamentos")
    )

    with pytest.raises(SeArriendaPorUnidades):
        firmar(gerente, propiedad=edificio)


def test_se_arrienda_una_unidad(gerente):
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)

    firmar(gerente, propiedad=None, unidad=unidad)

    unidad.refresh_from_db()
    assert unidad.estado == EstadoPropiedad.ARRENDADA


def test_la_base_no_acepta_dos_pagos_del_mismo_periodo(gerente):
    pago = firmar(gerente).pagos.first()

    with pytest.raises(IntegrityError), transaction.atomic():
        PagoRenta.objects.create(
            contrato=pago.contrato,
            periodo_anio=pago.periodo_anio,
            periodo_mes=pago.periodo_mes,
            fecha_vencimiento=pago.fecha_vencimiento,
            monto=pago.monto,
        )


# ---------- Pagos (reglas 6 a 8) ----------


def test_pagar_a_tiempo_no_lleva_recargo(gerente):
    pago = firmar(gerente).pagos.order_by("fecha_vencimiento").first()

    registrar_pago_renta(
        pago=pago,
        fecha=HOY,
        monto=Decimal("1000.00"),
        referencia="DEP-1",
        autor=gerente,
        ip=IP,
    )

    pago.refresh_from_db()
    assert pago.estado == EstadoPagoRenta.PAGADO
    assert pago.mora_aplicada == 0
    assert pago.tasa_a_usd == 1


def test_pagar_tarde_exige_renta_mas_recargo(gerente):
    contrato = atrasar(firmar(gerente), dias=60)
    pago = contrato.pagos.order_by("fecha_vencimiento").first()
    assert pago.en_mora()

    with pytest.raises(MontoIncorrecto) as error:
        registrar_pago_renta(
            pago=pago,
            fecha=HOY,
            monto=Decimal("1000.00"),
            referencia="X",
            autor=gerente,
            ip=IP,
        )
    assert error.value.detalles["esperado"] == "1050.00"

    registrar_pago_renta(
        pago=pago,
        fecha=HOY,
        monto=Decimal("1050.00"),
        referencia="DEP-2",
        autor=gerente,
        ip=IP,
    )
    pago.refresh_from_db()
    assert pago.mora_aplicada == Decimal("50.00")


def test_un_pago_no_se_registra_dos_veces(gerente):
    pago = firmar(gerente).pagos.first()
    pagar = {"fecha": HOY, "monto": Decimal("1000.00"), "referencia": "A"}
    registrar_pago_renta(pago=pago, autor=gerente, ip=IP, **pagar)

    with pytest.raises(PagoNoPendiente):
        registrar_pago_renta(pago=pago, autor=gerente, ip=IP, **pagar)


def test_la_fecha_de_pago_no_puede_ser_futura(gerente):
    pago = firmar(gerente).pagos.first()

    with pytest.raises(FechaPagoRentaInvalida):
        registrar_pago_renta(
            pago=pago,
            fecha=HOY + timedelta(days=1),
            monto=Decimal("1000.00"),
            referencia="X",
            autor=gerente,
            ip=IP,
        )


# ---------- Renovar (regla 9) ----------


def test_renovar_crea_un_contrato_que_empieza_al_dia_siguiente(gerente):
    anterior = firmar(gerente, duracion_meses=6)

    nuevo = renovar_arrendamiento(
        contrato=anterior,
        renta_mensual=Decimal("1100.00"),
        duracion_meses=12,
        autor=gerente,
        ip=IP,
    )

    anterior.refresh_from_db()
    anterior.propiedad.refresh_from_db()
    assert anterior.estado == EstadoArrendamiento.RENOVADO
    assert nuevo.contrato_anterior == anterior
    assert nuevo.fecha_inicio == anterior.fecha_fin + timedelta(days=1)
    assert nuevo.pagos.count() == 12
    assert nuevo.renta_mensual == Decimal("1100.00")
    assert anterior.propiedad.estado == EstadoPropiedad.ARRENDADA


def test_un_contrato_renovado_no_se_vuelve_a_renovar(gerente):
    anterior = firmar(gerente)
    renovacion = {"renta_mensual": Decimal("1"), "duracion_meses": 1}
    renovar_arrendamiento(contrato=anterior, autor=gerente, ip=IP, **renovacion)

    with pytest.raises(ContratoYaRenovado):
        renovar_arrendamiento(contrato=anterior, autor=gerente, ip=IP, **renovacion)


def test_un_contrato_vencido_no_se_renueva(gerente):
    contrato = atrasar(firmar(gerente, duracion_meses=1), dias=60)
    finalizar_arrendamiento(contrato=contrato, autor=gerente, ip=IP)

    with pytest.raises(ContratoYaRenovado):
        renovar_arrendamiento(
            contrato=contrato,
            renta_mensual=Decimal("1"),
            duracion_meses=1,
            autor=gerente,
            ip=IP,
        )


# ---------- Rescindir (regla 10) ----------


def test_rescindir_cancela_lo_futuro_conserva_lo_vencido_y_libera(gerente):
    contrato = atrasar(firmar(gerente), dias=70)

    rescindir_arrendamiento(
        contrato=contrato, fecha_rescision=HOY, autor=gerente, ip=IP
    )

    contrato.refresh_from_db()
    contrato.propiedad.refresh_from_db()
    pagos = contrato.pagos.all()
    vencidos = [p for p in pagos if p.fecha_vencimiento <= HOY]
    futuros = [p for p in pagos if p.fecha_vencimiento > HOY]
    assert contrato.estado == EstadoArrendamiento.RESCINDIDO
    assert all(p.estado == EstadoPagoRenta.PENDIENTE for p in vencidos)
    assert all(p.estado == EstadoPagoRenta.CANCELADO for p in futuros)
    assert contrato.propiedad.estado == EstadoPropiedad.DISPONIBLE
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ANULAR)
    assert registro.valores_nuevos["pagos_cancelados"] == len(futuros)


@pytest.mark.parametrize("dias", [1, -1])
def test_la_fecha_de_rescision_va_del_inicio_a_hoy(gerente, dias):
    contrato = firmar(gerente)
    fecha = HOY + timedelta(days=dias)  # mañana, o antes del inicio (hoy)

    with pytest.raises(FechaRescisionInvalida):
        rescindir_arrendamiento(
            contrato=contrato, fecha_rescision=fecha, autor=gerente, ip=IP
        )


def test_rescindir_una_renovacion_que_no_empieza_cancela_tambien_el_anterior(
    gerente,
):
    """Regla 10: el inquilino se va antes de que empiece la renovación."""
    anterior = atrasar(firmar(gerente, duracion_meses=6), dias=40)
    nuevo = renovar_arrendamiento(
        contrato=anterior,
        renta_mensual=Decimal("1100.00"),
        duracion_meses=12,
        autor=gerente,
        ip=IP,
    )

    rescindir_arrendamiento(contrato=nuevo, fecha_rescision=HOY, autor=gerente, ip=IP)

    assert not nuevo.pagos.exclude(estado=EstadoPagoRenta.CANCELADO).exists()
    assert not anterior.pagos.filter(
        estado=EstadoPagoRenta.PENDIENTE, fecha_vencimiento__gt=HOY
    ).exists()
    anterior.refresh_from_db()
    assert anterior.estado == EstadoArrendamiento.RENOVADO


def test_un_contrato_renovado_no_se_rescinde_por_si_solo(gerente):
    anterior = firmar(gerente)
    renovar_arrendamiento(
        contrato=anterior,
        renta_mensual=Decimal("1"),
        duracion_meses=1,
        autor=gerente,
        ip=IP,
    )

    with pytest.raises(ArrendamientoNoVigente):
        rescindir_arrendamiento(
            contrato=anterior, fecha_rescision=HOY, autor=gerente, ip=IP
        )


# ---------- Finalizar (regla 11) ----------


def test_no_se_finaliza_antes_de_la_fecha_de_fin(gerente):
    with pytest.raises(ContratoNoTerminado):
        finalizar_arrendamiento(contrato=firmar(gerente), autor=gerente, ip=IP)


def test_finalizar_lo_deja_vencido_conserva_la_deuda_y_libera(gerente):
    contrato = atrasar(firmar(gerente, duracion_meses=1), dias=60)

    finalizar_arrendamiento(contrato=contrato, autor=gerente, ip=IP)

    contrato.refresh_from_db()
    contrato.propiedad.refresh_from_db()
    assert contrato.estado == EstadoArrendamiento.VENCIDO
    assert contrato.pagos.get().estado == EstadoPagoRenta.PENDIENTE
    assert contrato.propiedad.estado == EstadoPropiedad.DISPONIBLE


def test_rescindir_actualiza_la_fecha_de_modificacion_de_los_pagos(gerente):
    """auto_now solo actúa con save(): el update() debe poner la fecha."""
    contrato = firmar(gerente)
    hace_una_semana = timezone.now() - timedelta(days=7)
    contrato.pagos.update(actualizado_en=hace_una_semana)

    rescindir_arrendamiento(
        contrato=contrato, fecha_rescision=HOY, autor=gerente, ip=IP
    )

    cancelado = contrato.pagos.filter(estado=EstadoPagoRenta.CANCELADO).first()
    assert cancelado.actualizado_en > hace_una_semana
    assert cancelado.actualizado_por == gerente
