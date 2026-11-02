"""Reglas de la spec 021 en los reportes del catálogo: R06, R08 y R14."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.arrendamientos.enums import EstadoArrendamiento
from apps.arrendamientos.services import firmar_arrendamiento
from apps.catalogo.services import cambiar_estado_propiedad
from apps.catalogo.tests.factories import (
    AvaluoFactory,
    PropiedadFactory,
    UnidadFactory,
    tipo,
)
from apps.core.tests.factories import MonedaFactory, PaisFactory
from apps.crm.tests.factories import ClienteFactory
from apps.reportes.estructuras import (
    FiltrosAvaluos,
    FiltrosEstadoPropiedades,
    FiltrosOcupacion,
)
from apps.reportes.selectors_catalogo import (
    resumir_avaluos,
    resumir_estados,
    resumir_ocupacion,
    seleccionar_avaluos,
    seleccionar_estados,
    seleccionar_ocupacion,
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


# ---------- R06 Propiedades por estado ----------


def test_r06_cuenta_las_unidades_y_no_el_edificio():
    """Regla 12: un edificio no se cuenta además de sus unidades."""
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))
    UnidadFactory.create_batch(2, propiedad=edificio)
    PropiedadFactory(tipo=tipo("Casa"))

    filas = todas(seleccionar_estados, FiltrosEstadoPropiedades())

    assert sorted(f["origen"] for f in filas) == ["PROPIEDAD", "UNIDAD", "UNIDAD"]
    assert resumir_estados(filtros=FiltrosEstadoPropiedades()).count == 3


def test_r06_sin_registro_en_la_bitacora_la_fecha_es_null():
    """Regla 12: sin evidencia, null; nunca actualizado_en."""
    PropiedadFactory(estado="DISPONIBLE")

    [fila] = todas(seleccionar_estados, FiltrosEstadoPropiedades())
    resumen = resumir_estados(filtros=FiltrosEstadoPropiedades())

    assert fila["fecha_estado"] is None
    assert fila["dias_en_estado"] is None
    assert resumen.totales["sin_historia"] == 1
    assert resumen.totales["dias_promedio"] is None


def test_r06_la_fecha_es_la_del_ultimo_cambio_al_estado_actual():
    propiedad = PropiedadFactory(estado="EN_NEGOCIACION")
    autor = UsuarioFactory()
    for estado in ("DISPONIBLE", "RESERVADA", "DISPONIBLE"):
        cambiar_estado_propiedad(
            propiedad=propiedad, estado=estado, autor=autor, ip=None, motivo="prueba"
        )

    [fila] = todas(seleccionar_estados, FiltrosEstadoPropiedades())
    resumen = resumir_estados(filtros=FiltrosEstadoPropiedades())

    assert fila["estado"] == "DISPONIBLE"
    assert fila["fecha_estado"] == HOY
    assert fila["dias_en_estado"] == 0
    assert resumen.totales["sin_historia"] == 0
    assert resumen.totales["dias_promedio"] == Decimal("0.00")


def test_r06_filtra_por_estado_y_agrupa_por_estado_y_tipo():
    PropiedadFactory(estado="DISPONIBLE")
    PropiedadFactory(estado="VENDIDA")

    filtros = FiltrosEstadoPropiedades(estado="VENDIDA")
    resumen = resumir_estados(filtros=filtros)

    assert [f["estado"] for f in todas(seleccionar_estados, filtros)] == ["VENDIDA"]
    assert [g.etiqueta for g in resumen.agrupamientos] == ["VENDIDA / Casa"]


# ---------- R08 Evolución de avalúos ----------


def test_r08_el_anterior_se_busca_antes_del_periodo(dolar):
    """Regla 13: el primero del período también tiene anterior si lo hubo."""
    propiedad = PropiedadFactory()
    AvaluoFactory(
        propiedad=propiedad,
        moneda=dolar,
        fecha=date(2025, 1, 15),
        valor=Decimal("100000"),
    )
    AvaluoFactory(
        propiedad=propiedad,
        moneda=dolar,
        fecha=date(2026, 1, 15),
        valor=Decimal("120000"),
    )

    filtros = FiltrosAvaluos(fecha_desde=date(2026, 1, 1))
    [fila] = todas(seleccionar_avaluos, filtros)

    assert fila["anterior"] == Decimal("100000.00")
    assert fila["variacion_pct"] == Decimal("20.00")


def test_r08_no_compara_monedas_distintas(dolar):
    propiedad = PropiedadFactory()
    AvaluoFactory(propiedad=propiedad, moneda=dolar, fecha=date(2025, 1, 15))
    AvaluoFactory(
        propiedad=propiedad,
        moneda=MonedaFactory(codigo="GTQ"),
        fecha=date(2026, 1, 15),
        valor=Decimal("1200000"),
    )

    filas = todas(seleccionar_avaluos, FiltrosAvaluos())

    assert [f["anterior"] for f in filas] == [None, None]
    assert [f["variacion_pct"] for f in filas] == [None, None]


def test_r08_resume_la_primera_y_la_ultima_del_periodo(dolar):
    propiedad = PropiedadFactory()
    for fecha, valor in (
        (date(2025, 1, 15), "100000"),
        (date(2025, 6, 15), "110000"),
        (date(2026, 1, 15), "125000"),
    ):
        AvaluoFactory(
            propiedad=propiedad, moneda=dolar, fecha=fecha, valor=Decimal(valor)
        )

    resumen = resumir_avaluos(filtros=FiltrosAvaluos())

    assert resumen.totales == {"cantidad": 3, "propiedades": 1}
    [grupo] = resumen.agrupamientos
    assert grupo.valores["primera"] == Decimal("100000.00")
    assert grupo.valores["ultima"] == Decimal("125000.00")
    assert grupo.valores["variacion_pct"] == Decimal("25.00")


# ---------- R14 Ocupación de arrendamientos ----------


def test_r14_la_ocupacion_es_ponderada_y_disponible_es_su_estado():
    """Regla 17: 2 arrendados de 5 bienes es 40 %, no el promedio de 25 % y
    100 %. Disponible es DISPONIBLE, no el total menos los arrendados."""
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))
    for estado in ("ARRENDADA", "DISPONIBLE", "RESERVADA", "RESERVADA"):
        UnidadFactory(propiedad=edificio, estado=estado)
    PropiedadFactory(estado="ARRENDADA")

    resumen = resumir_ocupacion(filtros=FiltrosOcupacion())
    filas = {f["id"]: f for f in todas(seleccionar_ocupacion, FiltrosOcupacion())}

    assert resumen.totales["elegibles"] == 5
    assert resumen.totales["arrendados"] == 2
    assert resumen.totales["disponibles"] == 1
    assert resumen.totales["otros"] == 2
    assert resumen.totales["ocupacion_pct"] == Decimal("40.00")
    assert filas[edificio.id]["ocupacion_pct"] == Decimal("25.00")


def test_r14_sin_bienes_la_ocupacion_es_null():
    PropiedadFactory()

    resumen = resumir_ocupacion(filtros=FiltrosOcupacion(pais=PaisFactory().id))

    assert resumen.totales["elegibles"] == 0
    assert resumen.totales["ocupacion_pct"] is None


def arrendar(moneda, *, dias=10):
    return firmar_arrendamiento(
        datos=dict(
            cliente=ClienteFactory(),
            propiedad=PropiedadFactory(estado="DISPONIBLE"),
            fecha_inicio=HOY - timedelta(days=dias),
            duracion_meses=12,
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


def test_r14_el_ingreso_solo_cuenta_contratos_que_se_cobran_hoy(dolar):
    """Regla 17: fuera un rescindido y un RENOVADO cuya renovación se
    rescindió, aunque sus fechas cubran hoy."""
    vigente = arrendar(dolar)
    rescindido = arrendar(dolar)
    rescindido.estado = EstadoArrendamiento.RESCINDIDO
    rescindido.fecha_rescision = HOY - timedelta(days=1)
    rescindido.save()
    renovado = arrendar(dolar)
    renovado.estado = EstadoArrendamiento.RENOVADO
    renovado.save()
    # La "renovación" de renovado, ya rescindida.
    rescindido.contrato_anterior = renovado
    rescindido.save()

    resumen = resumir_ocupacion(filtros=FiltrosOcupacion())
    filas = {f["id"]: f for f in todas(seleccionar_ocupacion, FiltrosOcupacion())}

    assert resumen.totales["ingreso_por_moneda"] == {"USD": Decimal("100.00")}
    assert filas[vigente.propiedad_id]["ingreso_recurrente"] == "USD 100.00"
    assert filas[renovado.propiedad_id]["ingreso_recurrente"] == ""


# ---------- API ----------


@pytest.mark.parametrize("rol", list(NombreRol.values))
@pytest.mark.parametrize(
    "slug", ["propiedades-por-estado", "evolucion-avaluos", "ocupacion-arrendamientos"]
)
def test_todos_los_roles_consultan_y_descargan_excel(rol, slug):
    """Regla 7: el catálogo no tiene cartera."""
    AvaluoFactory()
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))

    respuesta = cliente.get(f"/api/v1/reportes/{slug}/")
    excel = cliente.get(f"/api/v1/reportes/{slug}/excel/")

    assert respuesta.status_code == 200
    assert respuesta.json()["filas"]["count"] >= 1
    assert excel.status_code == 200


def test_un_filtro_desconocido_responde_400():
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory())

    respuesta = cliente.get("/api/v1/reportes/ocupacion-arrendamientos/?moneda=USD")

    assert respuesta.status_code == 400
