"""
Pruebas de los constraints de CRM (spec 004, §9, nivel modelo).

Comprueban que la base de datos misma rechaza los datos inválidos, sin pasar
por servicios: así las reglas se cumplen aunque el dato entre por un script.
Cada caso que debe fallar va dentro de transaction.atomic(), porque en
PostgreSQL un error deja la transacción de la prueba inutilizable.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.core.tests.factories import PaisFactory

from .factories import AgenteFactory, ClienteFactory, EmpresaFactory

pytestmark = pytest.mark.django_db


# ---------- Regla 6: datos obligatorios según el tipo ----------


@pytest.mark.parametrize("campo", ["nombre", "apellidos", "documento_identidad"])
def test_una_persona_sin_uno_de_sus_datos_se_rechaza(campo):
    with pytest.raises(IntegrityError), transaction.atomic():
        ClienteFactory(**{campo: ""})


@pytest.mark.parametrize("campo", ["razon_social", "nit"])
def test_una_empresa_sin_uno_de_sus_datos_se_rechaza(campo):
    with pytest.raises(IntegrityError), transaction.atomic():
        EmpresaFactory(**{campo: ""})


def test_una_persona_completa_y_una_empresa_completa_se_aceptan():
    ClienteFactory()
    EmpresaFactory()


# ---------- Regla 7: documento y NIT únicos por país ----------


def test_el_mismo_documento_en_el_mismo_pais_se_rechaza():
    guatemala = PaisFactory()
    ClienteFactory(pais=guatemala, documento_identidad="1234567890101")

    with pytest.raises(IntegrityError), transaction.atomic():
        ClienteFactory(pais=guatemala, documento_identidad="1234567890101")


def test_el_mismo_documento_en_otro_pais_se_acepta():
    """El DPI de Guatemala y la cédula de Costa Rica son sistemas distintos."""
    ClienteFactory(pais=PaisFactory(), documento_identidad="1234567890101")
    ClienteFactory(pais=PaisFactory(), documento_identidad="1234567890101")


def test_el_mismo_nit_de_empresa_en_el_mismo_pais_se_rechaza():
    guatemala = PaisFactory()
    EmpresaFactory(pais=guatemala, nit="1234567K")

    with pytest.raises(IntegrityError), transaction.atomic():
        EmpresaFactory(pais=guatemala, nit="1234567K")


def test_el_documento_repetido_se_rechaza_aunque_el_primero_este_desactivado():
    guatemala = PaisFactory()
    ClienteFactory(pais=guatemala, documento_identidad="1234567890101", activo=False)

    with pytest.raises(IntegrityError), transaction.atomic():
        ClienteFactory(pais=guatemala, documento_identidad="1234567890101")


# ---------- Regla 3: comisión entre 0 y 100 ----------


@pytest.mark.parametrize("comision", ["-0.01", "100.01"])
def test_una_comision_fuera_de_0_a_100_se_rechaza(comision):
    with pytest.raises(IntegrityError), transaction.atomic():
        AgenteFactory(porcentaje_comision=Decimal(comision))


@pytest.mark.parametrize("comision", ["0", "100"])
def test_los_extremos_0_y_100_se_aceptan(comision):
    AgenteFactory(porcentaje_comision=Decimal(comision))


# ---------- Código nulo mientras se crea (spec 004, §4) ----------


def test_dos_registros_sin_codigo_no_chocan_con_unique():
    """
    El servicio inserta con código nulo y luego lo asigna. Si dos clientes se
    crean a la vez, los dos están un instante sin código: con nulo no chocan.
    """
    ClienteFactory(codigo=None)
    ClienteFactory(codigo=None)


def test_un_usuario_tiene_como_maximo_un_perfil_de_agente():
    """Regla 1: usuario es OneToOne."""
    agente = AgenteFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        AgenteFactory(usuario=agente.usuario)
