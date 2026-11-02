"""Pruebas de los servicios de contratos de compra (spec 017, reglas 1 a 8 y 22)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.tests.factories import PropiedadFactory
from apps.compras.enums import EstadoContratoCompra
from apps.compras.exceptions import (
    FechaInvalida,
    PropiedadConContrato,
    ProveedorConContratos,
    TransicionInvalida,
)
from apps.compras.models import ContratoCompra
from apps.compras.services import (
    ENTIDAD_CONTRATO,
    anular_contrato_compra,
    completar_contrato_compra,
    crear_contrato_compra,
    desactivar_proveedor,
)
from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.tests.factories import MonedaFactory, TipoCambioFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ProveedorFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.40"
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD")


@pytest.fixture
def gtq(usd):
    """Quetzal con su tasa al dólar desde hace un mes (regla 5)."""
    moneda = MonedaFactory(codigo="GTQ")
    TipoCambioFactory(
        moneda_origen=moneda,
        moneda_destino=usd,
        tasa=Decimal("0.129032"),
        fecha=HOY - timedelta(days=30),
    )
    return moneda


def en_negociacion(**cambios):
    return PropiedadFactory(estado=EstadoPropiedad.EN_NEGOCIACION, **cambios)


def datos(moneda, **cambios):
    base = {
        "proveedor": ProveedorFactory(),
        "propiedad": en_negociacion(),
        "fecha_compra": HOY,
        "monto": Decimal("850000.00"),
        "gastos_legales": Decimal("12000.00"),
        "impuestos": Decimal("25500.00"),
        "moneda": moneda,
        "observaciones": "Compra a banco por adjudicación.",
    }
    base.update(cambios)
    return base


def crear(autor, moneda, **cambios):
    return crear_contrato_compra(datos=datos(moneda, **cambios), autor=autor, ip=IP)


def recargar(propiedad):
    propiedad.refresh_from_db()
    return propiedad.estado


# ---------- Registrar (reglas 1 a 5 y 8) ----------


def test_registra_en_proceso_con_costo_total_y_codigo(gerente, usd):
    contrato = crear(gerente, usd)

    assert contrato.codigo == f"CC-{contrato.pk:05d}"
    assert contrato.estado == EstadoContratoCompra.EN_PROCESO
    assert contrato.costo_total == Decimal("887500.00")
    assert contrato.tasa_a_usd == Decimal("1")
    assert contrato.costo_total_usd == Decimal("887500.00")


def test_registrar_no_cambia_el_estado_de_la_propiedad(gerente, usd):
    """Regla 1: la propiedad pasa a ADQUIRIDA solo al completar."""
    contrato = crear(gerente, usd)
    assert recargar(contrato.propiedad) == EstadoPropiedad.EN_NEGOCIACION


def test_guarda_la_tasa_al_dolar_de_la_fecha_y_el_costo_convertido(gerente, gtq):
    contrato = crear(
        gerente,
        gtq,
        monto=Decimal("100000.00"),
        gastos_legales=Decimal("0"),
        impuestos=Decimal("0"),
    )

    assert contrato.tasa_a_usd == Decimal("0.129032")
    # 100,000 × 0.129032 = 12,903.20
    assert contrato.costo_total_usd == Decimal("12903.20")


def test_sin_tasa_registrada_no_se_registra(gerente):
    MonedaFactory(codigo="USD")
    sin_tasa = MonedaFactory(codigo="HNL")

    with pytest.raises(TipoCambioNoDisponible):
        crear(gerente, sin_tasa)
    assert not ContratoCompra.objects.exists()


def test_la_propiedad_debe_estar_en_negociacion(gerente, usd):
    disponible = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)

    with pytest.raises(PropiedadNoDisponible):
        crear(gerente, usd, propiedad=disponible)


def test_un_segundo_contrato_sobre_la_misma_propiedad_se_rechaza(gerente, usd):
    """Regla 2: tras anular el primero, sí se acepta otro."""
    primero = crear(gerente, usd)

    with pytest.raises(PropiedadConContrato):
        crear(gerente, usd, propiedad=primero.propiedad)

    anular_contrato_compra(
        contrato=primero, motivo="Error en el monto", autor=gerente, ip=IP
    )
    segundo = crear(gerente, usd, propiedad=primero.propiedad)
    assert segundo.estado == EstadoContratoCompra.EN_PROCESO


def test_la_fecha_de_compra_no_puede_ser_futura(gerente, usd):
    with pytest.raises(FechaInvalida) as error:
        crear(gerente, usd, fecha_compra=HOY + timedelta(days=1))
    assert "fecha_compra" in error.value.detalles


def test_registrar_queda_en_la_bitacora(gerente, usd):
    contrato = crear(gerente, usd)

    registro = LogAuditoria.objects.get(entidad=ENTIDAD_CONTRATO)
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.entidad_id == contrato.pk
    assert registro.valores_nuevos["codigo"] == contrato.codigo
    assert registro.valores_nuevos["estado"] == EstadoContratoCompra.EN_PROCESO


# ---------- Completar (regla 6) ----------


def test_completar_deja_la_propiedad_adquirida(gerente, usd):
    contrato = crear(gerente, usd)

    completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)

    contrato.refresh_from_db()
    assert contrato.estado == EstadoContratoCompra.COMPLETADO
    assert recargar(contrato.propiedad) == EstadoPropiedad.ADQUIRIDA


def test_completar_dos_veces_se_rechaza(gerente, usd):
    contrato = crear(gerente, usd)
    completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)


def test_si_la_propiedad_ya_no_esta_en_negociacion_no_cambia_nada(gerente, usd):
    """Regla 6: alguien la movió a mano; se revierte todo."""
    contrato = crear(gerente, usd)
    propiedad = contrato.propiedad
    propiedad.estado = EstadoPropiedad.DISPONIBLE
    propiedad.save(update_fields=["estado"])

    with pytest.raises(PropiedadNoDisponible):
        completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)

    contrato.refresh_from_db()
    assert contrato.estado == EstadoContratoCompra.EN_PROCESO
    assert recargar(propiedad) == EstadoPropiedad.DISPONIBLE


def test_completar_audita_el_contrato_y_el_cambio_de_la_propiedad(gerente, usd):
    contrato = crear(gerente, usd)

    completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)

    registro = LogAuditoria.objects.get(
        entidad=ENTIDAD_CONTRATO, accion=AccionAuditoria.ACTUALIZAR
    )
    assert registro.valores_anteriores == {"estado": EstadoContratoCompra.EN_PROCESO}
    assert registro.valores_nuevos == {"estado": EstadoContratoCompra.COMPLETADO}
    # El cambio de la propiedad lo audita cambiar_estado_propiedad (spec 017, §7).
    assert LogAuditoria.objects.filter(
        entidad="catalogo_propiedad",
        entidad_id=contrato.propiedad_id,
        accion=AccionAuditoria.ACTUALIZAR,
    ).exists()


# ---------- Anular (regla 7) ----------


def test_anular_guarda_el_motivo_y_no_cambia_la_propiedad(gerente, usd):
    contrato = crear(gerente, usd)

    anular_contrato_compra(
        contrato=contrato, motivo="El banco retiró la oferta", autor=gerente, ip=IP
    )

    contrato.refresh_from_db()
    assert contrato.estado == EstadoContratoCompra.ANULADO
    assert recargar(contrato.propiedad) == EstadoPropiedad.EN_NEGOCIACION
    registro = LogAuditoria.objects.get(
        entidad=ENTIDAD_CONTRATO, accion=AccionAuditoria.ANULAR
    )
    assert registro.valores_nuevos["motivo"] == "El banco retiró la oferta"


def test_un_contrato_completado_no_se_anula(gerente, usd):
    contrato = crear(gerente, usd)
    completar_contrato_compra(contrato=contrato, autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        anular_contrato_compra(contrato=contrato, motivo="Tarde", autor=gerente, ip=IP)


# ---------- Desactivar proveedor (regla 22) ----------


def test_un_proveedor_con_un_contrato_en_proceso_no_se_desactiva(gerente, usd):
    contrato = crear(gerente, usd)

    with pytest.raises(ProveedorConContratos):
        desactivar_proveedor(proveedor=contrato.proveedor, autor=gerente, ip=IP)
    contrato.proveedor.refresh_from_db()
    assert contrato.proveedor.activo


def test_un_proveedor_con_contratos_cerrados_si_se_desactiva(gerente, usd):
    """Completados y anulados ya no lo impiden."""
    completado = crear(gerente, usd)
    completar_contrato_compra(contrato=completado, autor=gerente, ip=IP)
    anulado = crear(gerente, usd, proveedor=completado.proveedor)
    anular_contrato_compra(contrato=anulado, motivo="Duplicado", autor=gerente, ip=IP)

    desactivar_proveedor(proveedor=completado.proveedor, autor=gerente, ip=IP)

    completado.proveedor.refresh_from_db()
    assert not completado.proveedor.activo
