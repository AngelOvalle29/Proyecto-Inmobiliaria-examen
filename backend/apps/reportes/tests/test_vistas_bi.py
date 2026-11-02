"""Las vistas del esquema bi para Power BI (spec 021, §4).

Las crea la migración 0001 de reportes, que también corre en la base de
pruebas. Se consultan con SQL, como las leerá Power BI.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.core.tests.factories import MonedaFactory
from apps.crm.tests.factories import ClienteFactory
from apps.ventas.models import ContratoVenta

pytestmark = pytest.mark.django_db


def consultar(sql: str, parametros: tuple = ()) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        columnas = [c.name for c in cursor.description]
        return [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]


def vender(*, propiedad=None, unidad=None, estado="VIGENTE", fecha=date(2026, 3, 15)):
    cliente = ClienteFactory()
    return ContratoVenta.objects.create(
        cliente=cliente,
        agente=cliente.agente_asignado,
        propiedad=propiedad,
        unidad=unidad,
        fecha_firma=fecha,
        monto_total=Decimal("1000.00"),
        moneda=MonedaFactory(codigo="USD"),
        tasa_a_usd=Decimal("1"),
        monto_total_usd=Decimal("1000.00"),
        modalidad="CONTADO",
        comision_agente=Decimal("30.00"),
        estado=estado,
    )


def test_dim_propiedad_cuenta_las_unidades_y_no_el_edificio():
    """Regla 12, como R05: el edificio no es un bien; sus unidades sí."""
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))
    UnidadFactory.create_batch(2, propiedad=edificio)
    casa = PropiedadFactory(tipo=tipo("Casa"))

    filas = consultar("SELECT bien_clave, origen, propiedad_id FROM bi.dim_propiedad")

    assert sorted(f["origen"] for f in filas) == ["PROPIEDAD", "UNIDAD", "UNIDAD"]
    assert {f["propiedad_id"] for f in filas} == {edificio.id, casa.id}
    assert len({f["bien_clave"] for f in filas}) == 3


def test_hechos_ventas_excluye_anulados_y_cada_bien_esta_en_su_dimension():
    unidad = UnidadFactory()
    casa = PropiedadFactory()
    vender(unidad=unidad)
    vender(propiedad=casa)
    vender(propiedad=PropiedadFactory(), estado="ANULADO")

    hechos = consultar(
        "SELECT h.bien_clave, d.bien_clave AS en_dimension, h.neto_usd, h.ciudad_id "
        "FROM bi.hechos_ventas h "
        "LEFT JOIN bi.dim_propiedad d ON d.bien_clave = h.bien_clave"
    )

    assert sorted(h["bien_clave"] for h in hechos) == [
        f"PROPIEDAD-{casa.id}",
        f"UNIDAD-{unidad.id}",
    ]
    assert all(h["en_dimension"] == h["bien_clave"] for h in hechos)
    # La ciudad de una unidad es la de su edificio.
    assert {h["ciudad_id"] for h in hechos} == {
        casa.ciudad_id,
        unidad.propiedad.ciudad_id,
    }
    assert sum(h["neto_usd"] for h in hechos) == Decimal("2000.00")


def test_dim_tiempo_cubre_cada_fecha_de_venta_sin_repetir_dias():
    vender(propiedad=PropiedadFactory(), fecha=date(2024, 7, 1))

    [resumen] = consultar(
        "SELECT COUNT(*) AS dias, COUNT(DISTINCT fecha_id) AS distintos, "
        "MIN(fecha) AS desde FROM bi.dim_tiempo"
    )
    sin_fecha = consultar(
        "SELECT h.fecha_id FROM bi.hechos_ventas h "
        "LEFT JOIN bi.dim_tiempo t ON t.fecha_id = h.fecha_id WHERE t.fecha_id IS NULL"
    )
    [julio] = consultar(
        "SELECT anio, mes, nombre_mes, anio_mes FROM bi.dim_tiempo "
        "WHERE fecha_id = 20240701"
    )

    assert resumen["dias"] == resumen["distintos"]
    assert resumen["desde"] == date(2024, 1, 1)
    assert sin_fecha == []
    assert julio == {
        "anio": 2024,
        "mes": 7,
        "nombre_mes": "Julio",
        "anio_mes": "2024-07",
    }


def test_dim_geografia_trae_ciudad_y_pais():
    propiedad = PropiedadFactory()

    [fila] = consultar(
        "SELECT ciudad, pais FROM bi.dim_geografia WHERE ciudad_id = %s",
        (propiedad.ciudad_id,),
    )

    assert fila == {
        "ciudad": propiedad.ciudad.nombre,
        "pais": propiedad.ciudad.pais.nombre,
    }
