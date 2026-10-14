"""Pruebas de los endpoints de catálogos de core: listados, filtros y paginación."""

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.usuarios.tests.factories import UsuarioFactory

from .factories import CiudadFactory, MonedaFactory, PaisFactory, TipoCambioFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    """
    Cliente ya autenticado. force_authenticate salta el login: aquí se prueban
    los catálogos, y el JWT tiene sus propias pruebas en usuarios.
    """
    cliente = APIClient()
    cliente.force_authenticate(user=UsuarioFactory())
    return cliente


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD", nombre="Dólar", simbolo="$")


@pytest.fixture
def gtq():
    return MonedaFactory(codigo="GTQ", nombre="Quetzal", simbolo="Q")


# ---------- acceso ----------


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1/monedas/",
        "/api/v1/paises/",
        "/api/v1/ciudades/",
        "/api/v1/tipos-cambio/",
    ],
)
def test_los_catalogos_exigen_autenticacion(ruta):
    respuesta = APIClient().get(ruta)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["codigo"] == "NO_AUTENTICADO"


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1/monedas/",
        "/api/v1/paises/",
        "/api/v1/ciudades/",
        "/api/v1/tipos-cambio/",
    ],
)
def test_los_catalogos_son_de_solo_lectura(cliente, ruta):
    assert cliente.post(ruta, {}).status_code == 405


# ---------- monedas y países ----------


def test_monedas_lista_solo_las_activas(cliente, usd):
    MonedaFactory(codigo="XYZ", activo=False)

    respuesta = cliente.get("/api/v1/monedas/")

    assert respuesta.status_code == 200
    assert respuesta.json()["results"] == [
        {"id": usd.id, "codigo": "USD", "nombre": "Dólar", "simbolo": "$"}
    ]


def test_paises_incluye_el_resumen_de_su_moneda(cliente, gtq):
    guatemala = PaisFactory(nombre="Guatemala", codigo_iso="GTM", moneda_principal=gtq)

    datos = cliente.get("/api/v1/paises/").json()["results"]

    assert datos == [
        {
            "id": guatemala.id,
            "nombre": "Guatemala",
            "codigo_iso": "GTM",
            "moneda_principal": {"id": gtq.id, "codigo": "GTQ"},
        }
    ]


# ---------- ciudades ----------


def test_ciudades_filtra_por_pais(cliente):
    guatemala = PaisFactory(nombre="Guatemala", codigo_iso="GTM")
    mexico = PaisFactory(nombre="México", codigo_iso="MEX")
    CiudadFactory(nombre="Quetzaltenango", pais=guatemala)
    CiudadFactory(nombre="Antigua Guatemala", pais=guatemala)
    CiudadFactory(nombre="Puebla", pais=mexico)

    datos = cliente.get("/api/v1/ciudades/", {"pais": guatemala.id}).json()["results"]

    assert [ciudad["nombre"] for ciudad in datos] == [
        "Antigua Guatemala",
        "Quetzaltenango",
    ]
    assert datos[0]["pais"] == {"id": guatemala.id, "nombre": "Guatemala"}


def test_ciudades_omite_las_de_un_pais_desactivado(cliente):
    CiudadFactory(nombre="Quetzaltenango", pais=PaisFactory(codigo_iso="GTM"))
    CiudadFactory(nombre="Puebla", pais=PaisFactory(codigo_iso="MEX", activo=False))

    datos = cliente.get("/api/v1/ciudades/").json()["results"]

    assert [ciudad["nombre"] for ciudad in datos] == ["Quetzaltenango"]


# ---------- tipos de cambio ----------


def test_tipos_cambio_filtra_por_monedas_y_rango_de_fechas(cliente, usd, gtq):
    for dia in (1, 10, 20):
        TipoCambioFactory(
            moneda_origen=usd,
            moneda_destino=gtq,
            tasa=Decimal("7.75"),
            fecha=date(2026, 10, dia),
        )
    TipoCambioFactory(
        moneda_origen=gtq,
        moneda_destino=usd,
        tasa=Decimal("0.129"),
        fecha=date(2026, 10, 10),
    )

    respuesta = cliente.get(
        "/api/v1/tipos-cambio/",
        {
            "moneda_origen": usd.id,
            "moneda_destino": gtq.id,
            "fecha_desde": "2026-10-05",
            "fecha_hasta": "2026-10-20",
        },
    )

    datos = respuesta.json()["results"]
    # Del más reciente al más antiguo; el 1 de octubre queda fuera del rango.
    assert [tipo["fecha"] for tipo in datos] == ["2026-10-20", "2026-10-10"]
    assert datos[0]["tasa"] == "7.750000"
    assert datos[0]["moneda_origen"] == {"id": usd.id, "codigo": "USD"}


def test_una_fecha_mal_escrita_devuelve_error_de_validacion(cliente):
    respuesta = cliente.get("/api/v1/tipos-cambio/", {"fecha_desde": "10/05/2026"})

    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert "fecha_desde" in error["detalles"]


# ---------- paginación ----------


def test_los_listados_se_paginan_de_25_en_25(cliente):
    MonedaFactory.create_batch(30)

    primera = cliente.get("/api/v1/monedas/").json()
    segunda = cliente.get("/api/v1/monedas/", {"page": 2}).json()

    assert primera["count"] == 30
    assert len(primera["results"]) == 25
    assert primera["next"] is not None
    assert len(segunda["results"]) == 5
    # Ninguna moneda aparece en las dos páginas.
    codigos_primera = {moneda["codigo"] for moneda in primera["results"]}
    codigos_segunda = {moneda["codigo"] for moneda in segunda["results"]}
    assert codigos_primera.isdisjoint(codigos_segunda)


def test_ciudades_carga_los_paises_sin_una_consulta_por_ciudad(
    cliente, django_assert_num_queries
):
    """
    select_related en listar_ciudades: el país viene en la misma consulta.
    Sin él, cada ciudad haría otra consulta para su país (el problema N+1).
    """
    CiudadFactory.create_batch(10)

    # Una consulta cuenta el total para la paginación; otra trae la página.
    with django_assert_num_queries(2):
        cliente.get("/api/v1/ciudades/")
