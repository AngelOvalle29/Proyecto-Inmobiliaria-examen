"""Pruebas de los servicios de pagos a constructoras (spec 017, reglas 16, 17 y
19 a 21) y de los totales del detalle del proyecto."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import DocumentoDeOtraPropiedad
from apps.catalogo.tests.factories import DocumentoOficialFactory, PropiedadFactory
from apps.construccion.enums import EstadoPago, TipoPagoConstructora
from apps.construccion.exceptions import (
    FechaInvalida,
    PresupuestoExcedido,
    TransicionInvalida,
)
from apps.construccion.selectors import (
    listar_proyectos_con_totales,
    total_comprometido,
)
from apps.construccion.services import (
    ENTIDAD_PAGO,
    actualizar_proyecto,
    anular_pago,
    cancelar_proyecto,
    crear_proyecto,
    finalizar_proyecto,
    iniciar_proyecto,
    pagar,
    programar_pago,
    registrar_avance,
)
from apps.core.tests.factories import MonedaFactory, TipoCambioFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.60"
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD")


@pytest.fixture
def gtq(usd):
    """Quetzal con su tasa al dólar desde hace un mes."""
    moneda = MonedaFactory(codigo="GTQ")
    TipoCambioFactory(
        moneda_origen=moneda,
        moneda_destino=usd,
        tasa=Decimal("0.129032"),
        fecha=HOY - timedelta(days=30),
    )
    return moneda


def proyecto(autor, moneda, presupuesto="1000.00", **cambios):
    datos = {
        "nombre": "Obra demo",
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.ADQUIRIDA),
        "constructora": ConstructoraFactory(),
        "fecha_inicio": HOY - timedelta(days=10),
        "fecha_fin_estimada": HOY + timedelta(days=90),
        "presupuesto_total": Decimal(presupuesto),
        "moneda": moneda,
    }
    datos.update(cambios)
    return crear_proyecto(datos=datos, autor=autor, ip=IP)


def programar(autor, obra, monto="100.00", tipo=TipoPagoConstructora.AVANCE, **cambios):
    datos = {"tipo": tipo, "monto": Decimal(monto), "fecha_programada": HOY}
    datos.update(cambios)
    return programar_pago(proyecto=obra, datos=datos, autor=autor, ip=IP)


def finalizado(autor, moneda, **cambios):
    obra = proyecto(autor, moneda, **cambios)
    iniciar_proyecto(proyecto=obra, autor=autor, ip=IP)
    registrar_avance(
        proyecto=obra, porcentaje=100, descripcion="Fin", autor=autor, ip=IP
    )
    return finalizar_proyecto(proyecto=obra, autor=autor, ip=IP)


def estado_de(pago):
    pago.refresh_from_db()
    return pago.estado


# ---------- Programar (reglas 19 y 20) ----------


def test_programa_en_la_moneda_del_proyecto_con_codigo(gerente, gtq):
    obra = proyecto(gerente, gtq)

    pago = programar(gerente, obra)

    assert pago.codigo == f"PG-{pago.pk:05d}"
    assert pago.estado == EstadoPago.PROGRAMADO
    assert pago.moneda == gtq
    assert pago.tasa_a_usd is None
    registro = LogAuditoria.objects.get(entidad=ENTIDAD_PAGO)
    assert registro.accion == AccionAuditoria.CREAR


def test_un_pago_que_supera_el_presupuesto_se_rechaza(gerente, usd):
    """Regla 19; tras subir el presupuesto, se acepta."""
    obra = proyecto(gerente, usd, presupuesto="1000.00")
    programar(gerente, obra, monto="800.00")

    with pytest.raises(PresupuestoExcedido):
        programar(gerente, obra, monto="300.00")

    actualizar_proyecto(
        proyecto=obra,
        datos={"presupuesto_total": Decimal("1100.00")},
        autor=gerente,
        ip=IP,
    )
    programar(gerente, obra, monto="300.00")
    assert total_comprometido(proyecto=obra) == Decimal("1100.00")


def test_un_pago_anulado_ya_no_cuenta_contra_el_presupuesto(gerente, usd):
    obra = proyecto(gerente, usd, presupuesto="1000.00")
    primero = programar(gerente, obra, monto="1000.00")
    anular_pago(pago=primero, motivo="Error", autor=gerente, ip=IP)

    programar(gerente, obra, monto="1000.00")


def test_bajar_el_presupuesto_por_debajo_de_lo_comprometido_se_rechaza(gerente, usd):
    """Reglas 17 y 19."""
    obra = proyecto(gerente, usd, presupuesto="1000.00")
    programar(gerente, obra, monto="600.00")

    with pytest.raises(PresupuestoExcedido):
        actualizar_proyecto(
            proyecto=obra,
            datos={"presupuesto_total": Decimal("500.00")},
            autor=gerente,
            ip=IP,
        )
    actualizar_proyecto(
        proyecto=obra,
        datos={"presupuesto_total": Decimal("600.00")},
        autor=gerente,
        ip=IP,
    )


def test_un_finiquito_solo_para_un_proyecto_finalizado(gerente, usd):
    obra = proyecto(gerente, usd)
    with pytest.raises(TransicionInvalida):
        programar(gerente, obra, tipo=TipoPagoConstructora.FINIQUITO)

    terminada = finalizado(gerente, usd)
    pago = programar(gerente, terminada, tipo=TipoPagoConstructora.FINIQUITO)
    assert pago.tipo == TipoPagoConstructora.FINIQUITO


def test_en_un_finalizado_se_sube_el_presupuesto_y_se_paga_el_finiquito(gerente, usd):
    """Criterio de §8: el finiquito que no cabía."""
    obra = finalizado(gerente, usd, presupuesto="1000.00")
    programar(gerente, obra, monto="1000.00")

    actualizar_proyecto(
        proyecto=obra,
        datos={"presupuesto_total": Decimal("1200.00")},
        autor=gerente,
        ip=IP,
    )
    finiquito = programar(
        gerente, obra, monto="200.00", tipo=TipoPagoConstructora.FINIQUITO
    )
    pagar(pago=finiquito, fecha_pago=HOY, referencia="TRF-9", autor=gerente, ip=IP)

    assert estado_de(finiquito) == EstadoPago.PAGADO


def test_no_se_programa_en_un_proyecto_cancelado(gerente, usd):
    obra = proyecto(gerente, usd)
    cancelar_proyecto(proyecto=obra, motivo="x", autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        programar(gerente, obra)


def test_el_documento_debe_ser_de_la_misma_propiedad(gerente, usd):
    obra = proyecto(gerente, usd)
    ajeno = DocumentoOficialFactory()
    propio = DocumentoOficialFactory(propiedad=obra.propiedad)

    with pytest.raises(DocumentoDeOtraPropiedad):
        programar(gerente, obra, documento=ajeno)
    assert programar(gerente, obra, documento=propio).documento == propio


# ---------- Pagar (regla 21) ----------


def test_pagar_guarda_fecha_referencia_tasa_y_monto_en_dolares(gerente, gtq):
    obra = proyecto(gerente, gtq)
    pago = programar(gerente, obra, monto="1000.00")

    pagar(pago=pago, fecha_pago=HOY, referencia="TRF-123", autor=gerente, ip=IP)

    pago.refresh_from_db()
    assert pago.estado == EstadoPago.PAGADO
    assert pago.fecha_pago == HOY
    assert pago.referencia_pago == "TRF-123"
    assert pago.tasa_a_usd == Decimal("0.129032")
    assert pago.monto_usd == Decimal("129.03")


def test_pagar_dos_veces_se_rechaza(gerente, usd):
    pago = programar(gerente, proyecto(gerente, usd))
    pagar(pago=pago, fecha_pago=HOY, referencia="A", autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        pagar(pago=pago, fecha_pago=HOY, referencia="B", autor=gerente, ip=IP)


def test_la_fecha_de_pago_no_puede_ser_futura(gerente, usd):
    pago = programar(gerente, proyecto(gerente, usd))

    with pytest.raises(FechaInvalida) as error:
        pagar(
            pago=pago,
            fecha_pago=HOY + timedelta(days=1),
            referencia="A",
            autor=gerente,
            ip=IP,
        )
    assert "fecha_pago" in error.value.detalles


def test_solo_un_anticipo_se_paga_antes_del_inicio_de_la_obra(gerente, usd):
    """Regla 21, decidida en la revisión de Marco."""
    obra = proyecto(
        gerente,
        usd,
        fecha_inicio=HOY + timedelta(days=10),
        fecha_fin_estimada=HOY + timedelta(days=100),
    )
    anticipo = programar(gerente, obra, tipo=TipoPagoConstructora.ANTICIPO)
    avance = programar(gerente, obra, tipo=TipoPagoConstructora.AVANCE)

    pagar(pago=anticipo, fecha_pago=HOY, referencia="A", autor=gerente, ip=IP)
    with pytest.raises(FechaInvalida):
        pagar(pago=avance, fecha_pago=HOY, referencia="B", autor=gerente, ip=IP)

    assert estado_de(anticipo) == EstadoPago.PAGADO
    assert estado_de(avance) == EstadoPago.PROGRAMADO


# ---------- Anular (regla 21) ----------


def test_anular_guarda_el_motivo(gerente, usd):
    pago = programar(gerente, proyecto(gerente, usd))

    anular_pago(pago=pago, motivo="Factura con error", autor=gerente, ip=IP)

    assert estado_de(pago) == EstadoPago.ANULADO
    registro = LogAuditoria.objects.get(
        entidad=ENTIDAD_PAGO, accion=AccionAuditoria.ANULAR
    )
    assert registro.valores_nuevos["motivo"] == "Factura con error"


def test_un_pago_pagado_no_se_anula(gerente, usd):
    pago = programar(gerente, proyecto(gerente, usd))
    pagar(pago=pago, fecha_pago=HOY, referencia="A", autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        anular_pago(pago=pago, motivo="Tarde", autor=gerente, ip=IP)


# ---------- Cancelar el proyecto (regla 16) ----------


def test_cancelar_anula_los_programados_y_deja_los_pagados(gerente, usd):
    obra = proyecto(gerente, usd)
    iniciar_proyecto(proyecto=obra, autor=gerente, ip=IP)
    pagado = programar(gerente, obra)
    pagar(pago=pagado, fecha_pago=HOY, referencia="A", autor=gerente, ip=IP)
    programado = programar(gerente, obra)

    cancelar_proyecto(proyecto=obra, motivo="Sin fondos", autor=gerente, ip=IP)

    assert estado_de(programado) == EstadoPago.ANULADO
    assert estado_de(pagado) == EstadoPago.PAGADO


# ---------- Totales del detalle (§5) ----------


def test_los_totales_del_detalle_suben_y_bajan_con_los_pagos(gerente, usd):
    obra = proyecto(gerente, usd, presupuesto="1000.00")

    def totales():
        detalle = listar_proyectos_con_totales().get(pk=obra.pk)
        return detalle.total_comprometido, detalle.disponible

    assert totales() == (Decimal("0"), Decimal("1000.00"))

    pago = programar(gerente, obra, monto="300.00")
    assert totales() == (Decimal("300.00"), Decimal("700.00"))

    anular_pago(pago=pago, motivo="x", autor=gerente, ip=IP)
    assert totales() == (Decimal("0"), Decimal("1000.00"))


def test_pagar_queda_en_la_bitacora_con_la_fecha_y_la_referencia(gerente, usd):
    """Criterio de §8: cada operación queda en la bitácora."""
    pago = programar(gerente, proyecto(gerente, usd))

    pagar(pago=pago, fecha_pago=HOY, referencia="TRF-77", autor=gerente, ip=IP)

    registro = LogAuditoria.objects.get(
        entidad=ENTIDAD_PAGO, accion=AccionAuditoria.ACTUALIZAR
    )
    assert registro.valores_anteriores == {"estado": EstadoPago.PROGRAMADO}
    assert registro.valores_nuevos["referencia_pago"] == "TRF-77"
    assert registro.valores_nuevos["estado"] == EstadoPago.PAGADO
