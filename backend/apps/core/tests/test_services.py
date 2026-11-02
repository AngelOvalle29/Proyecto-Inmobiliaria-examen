"""Pruebas de los servicios de core: carga de datos de demostración."""

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command, get_commands

from apps.core import datos_demo
from apps.core.management.commands.seed_demo import COMANDOS_DE_DEMO
from apps.core.models import Ciudad, Moneda, Pais, TipoCambio
from apps.core.selectors import convertir_monto
from apps.core.services import _primeros_de_mes, cargar_catalogos_demo

pytestmark = pytest.mark.django_db

HOY = date(2026, 10, 15)

# 4 monedas distintas del dólar × 2 direcciones × 6 meses.
TIPOS_CAMBIO_ESPERADOS = len(datos_demo.TASAS_BASE) * 2 * datos_demo.MESES_DE_HISTORIAL


def test_carga_todos_los_catalogos():
    creados = cargar_catalogos_demo(hasta=HOY)

    assert creados == {
        "monedas": 5,
        "paises": 5,
        "ciudades": 13,
        "tipos_cambio": TIPOS_CAMBIO_ESPERADOS,
    }
    assert TipoCambio.objects.count() == 48


def test_correrlo_dos_veces_no_duplica_nada():
    cargar_catalogos_demo(hasta=HOY)

    creados = cargar_catalogos_demo(hasta=HOY)

    assert creados == {"monedas": 0, "paises": 0, "ciudades": 0, "tipos_cambio": 0}
    assert Moneda.objects.count() == 5
    assert Pais.objects.count() == 5
    assert Ciudad.objects.count() == 13
    assert TipoCambio.objects.count() == 48


def test_no_sobrescribe_lo_que_se_corrigio_desde_el_panel():
    cargar_catalogos_demo(hasta=HOY)
    Moneda.objects.filter(codigo="GTQ").update(nombre="Quetzal guatemalteco")

    cargar_catalogos_demo(hasta=HOY)

    assert Moneda.objects.get(codigo="GTQ").nombre == "Quetzal guatemalteco"


def test_las_tasas_cargadas_permiten_convertir_en_ambas_direcciones():
    """La regla 7 no calcula inversas: la carga debe traer las dos direcciones."""
    cargar_catalogos_demo(hasta=HOY)
    usd = Moneda.objects.get(codigo="USD")
    gtq = Moneda.objects.get(codigo="GTQ")

    a_quetzales = convertir_monto(
        monto=Decimal("100.00"), origen=usd, destino=gtq, fecha=HOY
    )
    a_dolares = convertir_monto(monto=a_quetzales, origen=gtq, destino=usd, fecha=HOY)

    assert a_quetzales > Decimal("100.00")
    # Ida y vuelta da el monto original, salvo diferencias de centavos.
    assert abs(a_dolares - Decimal("100.00")) <= Decimal("0.01")


def test_el_salvador_usa_el_dolar():
    cargar_catalogos_demo(hasta=HOY)

    assert Pais.objects.get(codigo_iso="SLV").moneda_principal.codigo == "USD"


def test_los_meses_de_historial_cruzan_el_cambio_de_anio():
    fechas = _primeros_de_mes(hasta=date(2026, 2, 15), cantidad=3)

    assert fechas == [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]


def test_el_comando_seed_demo_muestra_el_resumen():
    salida = StringIO()

    call_command("seed_demo", stdout=salida)

    assert "Datos de demostración cargados." in salida.getvalue()
    assert "monedas: 5 nuevos" in salida.getvalue()


def test_seed_demo_llama_a_los_comandos_de_las_apps_por_nombre():
    salida = StringIO()

    call_command("seed_demo", stdout=salida)

    assert "Catálogo de demostración cargado." in salida.getvalue()


def test_todos_los_comandos_de_demo_existen():
    """Un nombre mal escrito en COMANDOS_DE_DEMO se omitiría con un simple
    aviso, y esa app quedaría sin datos en la demostración sin que nadie lo
    note. Esta prueba lo detecta."""
    faltantes = [c for c in COMANDOS_DE_DEMO if c not in get_commands()]

    assert faltantes == []


def test_seed_demo_omite_un_comando_que_todavia_no_existe(monkeypatch):
    monkeypatch.setattr(
        "apps.core.management.commands.seed_demo.COMANDOS_DE_DEMO",
        ["cargar_demo_inexistente"],
    )
    salida = StringIO()

    call_command("seed_demo", stdout=salida)

    assert "Se omite cargar_demo_inexistente" in salida.getvalue()
