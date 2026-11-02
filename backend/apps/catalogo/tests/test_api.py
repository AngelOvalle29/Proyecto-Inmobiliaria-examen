"""Pruebas de los endpoints de catálogo."""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.core.tests.factories import CiudadFactory, MonedaFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

PROPIEDADES = "/api/v1/propiedades/"
TIPOS = "/api/v1/tipos-propiedad/"


def cliente_con_rol(rol: str) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return cliente


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


def datos_propiedad(**cambios) -> dict:
    datos = {
        "nombre": "Casa demo",
        "tipo_id": tipo("Casa").pk,
        "ciudad_id": CiudadFactory().pk,
        "direccion": "Calle demo 1",
        "area_m2": "300.00",
        "precio_lista": "200000.00",
        "moneda_id": MonedaFactory(codigo="USD").pk,
    }
    return {**datos, **cambios}


def datos_unidad(**cambios) -> dict:
    datos = {
        "codigo": "A-101",
        "nivel": 1,
        "area_m2": "80.00",
        "precio_lista": "95000.00",
        "moneda_id": MonedaFactory(codigo="USD").pk,
    }
    return {**datos, **cambios}


# ---------- Permisos ----------


def test_sin_sesion_responde_401():
    assert APIClient().get(PROPIEDADES).status_code == 401


@pytest.mark.parametrize(
    ("rol", "esperado"),
    [
        (NombreRol.ADMINISTRADOR, 201),
        (NombreRol.GERENTE, 201),
        (NombreRol.AGENTE, 403),
        (NombreRol.CONTABILIDAD, 403),
        (NombreRol.CONSULTA, 403),
    ],
)
def test_crear_propiedad_por_rol(rol, esperado):
    respuesta = cliente_con_rol(rol).post(PROPIEDADES, datos_propiedad(), format="json")

    assert respuesta.status_code == esperado


@pytest.mark.parametrize("rol", list(NombreRol))
def test_todos_los_roles_leen_propiedades(rol):
    PropiedadFactory()

    assert cliente_con_rol(rol).get(PROPIEDADES).status_code == 200


@pytest.mark.parametrize(
    ("rol", "esperado"), [(NombreRol.ADMINISTRADOR, 201), (NombreRol.GERENTE, 403)]
)
def test_solo_el_administrador_crea_tipos(rol, esperado):
    respuesta = cliente_con_rol(rol).post(TIPOS, {"nombre": "Oficina"}, format="json")

    assert respuesta.status_code == esperado


@pytest.mark.parametrize(
    "peticion",
    [
        lambda c, p, u: c.patch(f"{PROPIEDADES}{p.pk}/", {"nombre": "X"}),
        lambda c, p, u: c.delete(f"{PROPIEDADES}{p.pk}/"),
        lambda c, p, u: c.post(
            f"{PROPIEDADES}{p.pk}/cambiar-estado/",
            {"estado": "DISPONIBLE", "motivo": "X"},
        ),
        lambda c, p, u: c.post(f"{PROPIEDADES}{p.pk}/unidades/", datos_unidad()),
        lambda c, p, u: c.patch(f"/api/v1/unidades/{u.pk}/", {"nivel": 3}),
        lambda c, p, u: c.delete(f"/api/v1/unidades/{u.pk}/"),
        lambda c, p, u: c.post(
            f"/api/v1/unidades/{u.pk}/cambiar-estado/",
            {"estado": "VENDIDA", "motivo": "X"},
        ),
    ],
)
def test_un_agente_no_escribe_en_ningun_endpoint(peticion):
    unidad = UnidadFactory()

    respuesta = peticion(cliente_con_rol(NombreRol.AGENTE), unidad.propiedad, unidad)

    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["codigo"] == "SIN_PERMISO"


def test_put_se_rechaza_incluso_al_administrador():
    """PUT no está declarado en roles_por_metodo: TieneRol lo cierra con 403
    antes de que DRF llegue a responder 405 (los permisos se revisan primero)."""
    propiedad = PropiedadFactory(nombre="Original")
    administrador = cliente_con_rol(NombreRol.ADMINISTRADOR)

    respuesta = administrador.put(
        f"{PROPIEDADES}{propiedad.pk}/", datos_propiedad(), format="json"
    )

    assert respuesta.status_code == 403
    propiedad.refresh_from_db()
    assert propiedad.nombre == "Original"


# ---------- Propiedades ----------


def test_crear_propiedad_devuelve_codigo_y_resumenes(gerente):
    respuesta = gerente.post(PROPIEDADES, datos_propiedad(), format="json")

    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == f"PROP-{cuerpo['id']:05d}"
    assert cuerpo["estado"] == "EN_NEGOCIACION"
    assert cuerpo["tipo"] == {"id": tipo("Casa").pk, "nombre": "Casa"}
    assert cuerpo["moneda"]["codigo"] == "USD"
    assert "pais" in cuerpo["ciudad"]
    assert LogAuditoria.objects.filter(entidad_id=cuerpo["id"]).count() == 1


def test_crear_propiedad_con_precio_cero_responde_400(gerente):
    respuesta = gerente.post(
        PROPIEDADES, datos_propiedad(precio_lista="0"), format="json"
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_patch_no_cambia_el_estado(gerente):
    propiedad = PropiedadFactory()

    respuesta = gerente.patch(
        f"{PROPIEDADES}{propiedad.pk}/",
        {"nombre": "Nuevo nombre", "estado": "VENDIDA"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Nuevo nombre"
    assert respuesta.json()["estado"] == "EN_NEGOCIACION"


def test_cambiar_estado_lo_cambia_y_lo_audita(gerente):
    propiedad = PropiedadFactory()

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/cambiar-estado/",
        {"estado": "DISPONIBLE", "motivo": "Escrituras listas"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "DISPONIBLE"
    registro = LogAuditoria.objects.latest("id")
    assert registro.valores_nuevos["motivo"] == "Escrituras listas"


def test_cambiar_estado_sin_motivo_responde_400(gerente):
    propiedad = PropiedadFactory()

    respuesta = gerente.post(
        f"{PROPIEDADES}{propiedad.pk}/cambiar-estado/",
        {"estado": "DISPONIBLE"},
        format="json",
    )

    assert respuesta.status_code == 400


def test_borrar_propiedad_la_desactiva_y_deja_de_listarse(gerente):
    propiedad = PropiedadFactory()

    assert gerente.delete(f"{PROPIEDADES}{propiedad.pk}/").status_code == 204

    propiedad.refresh_from_db()
    assert not propiedad.activo
    assert gerente.get(f"{PROPIEDADES}{propiedad.pk}/").status_code == 404


def test_borrar_propiedad_con_unidades_activas_responde_409(gerente):
    unidad = UnidadFactory()

    respuesta = gerente.delete(f"{PROPIEDADES}{unidad.propiedad.pk}/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROPIEDAD_CON_UNIDADES"


# ---------- Unidades ----------


def test_agregar_unidad_a_una_casa_responde_409(gerente):
    casa = PropiedadFactory(tipo=tipo("Casa"))

    respuesta = gerente.post(
        f"{PROPIEDADES}{casa.pk}/unidades/", datos_unidad(), format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TIPO_SIN_UNIDADES"


def test_unidad_duplicada_responde_409(gerente):
    existente = UnidadFactory(codigo="A-101")

    respuesta = gerente.post(
        f"{PROPIEDADES}{existente.propiedad.pk}/unidades/",
        datos_unidad(codigo="A-101"),
        format="json",
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "UNIDAD_DUPLICADA"


def test_crear_y_listar_unidades_de_una_propiedad(gerente):
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))
    url = f"{PROPIEDADES}{edificio.pk}/unidades/"

    creada = gerente.post(url, datos_unidad(), format="json")
    listado = gerente.get(url)

    assert creada.status_code == 201
    assert creada.json()["propiedad"] == {"id": edificio.pk, "codigo": edificio.codigo}
    assert [u["codigo"] for u in listado.json()["results"]] == ["A-101"]


def test_buscar_unidades_filtra_por_codigo_en_todas_las_paginas(gerente):
    """Spec 014, regla 11: la búsqueda la hace la API, no el navegador sobre la
    primera página. Con 30 unidades, la A-129 está en la segunda página."""
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))
    for numero in range(100, 130):
        UnidadFactory(propiedad=edificio, codigo=f"A-{numero}")
    url = f"{PROPIEDADES}{edificio.pk}/unidades/"

    respuesta = gerente.get(url, {"buscar": "a-129"})

    assert [u["codigo"] for u in respuesta.json()["results"]] == ["A-129"]


def test_unidades_de_una_propiedad_inexistente_responde_404(gerente):
    assert gerente.get(f"{PROPIEDADES}999999/unidades/").status_code == 404


def test_una_propiedad_inexistente_responde_404_en_espanol(gerente):
    """De punta a punta: sin el texto en inglés de Django ni el nombre del
    modelo (manejador de errores de core)."""
    respuesta = gerente.get(f"{PROPIEDADES}999999/")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["mensaje"] == "No se encontró el recurso."


# ---------- Filtros y consultas ----------


def test_filtros_de_propiedades(gerente):
    barata = PropiedadFactory(precio_lista=Decimal("50000"), es_publica=True)
    cara = PropiedadFactory(precio_lista=Decimal("900000"), tipo=tipo("Hotel"))

    def codigos(parametros: str) -> list[str]:
        resultados = gerente.get(PROPIEDADES + parametros).json()["results"]
        return [propiedad["codigo"] for propiedad in resultados]

    assert codigos("?precio_max=100000") == [barata.codigo]
    assert codigos("?precio_min=100000") == [cara.codigo]
    assert codigos(f"?tipo={tipo('Hotel').pk}") == [cara.codigo]
    assert codigos("?es_publica=true") == [barata.codigo]
    assert codigos(f"?pais={cara.ciudad.pais_id}") == [cara.codigo]
    assert codigos(f"?buscar={cara.codigo.lower()}") == [cara.codigo]
    assert codigos("?estado=VENDIDA") == []


def test_filtro_con_estado_invalido_responde_400(gerente):
    respuesta = gerente.get(PROPIEDADES + "?estado=INVENTADO")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "VALIDACION"


def test_listado_no_hace_una_consulta_por_propiedad(gerente):
    """Sin select_related, cada propiedad agregaría consultas de tipo, ciudad,
    país y moneda (N+1)."""

    def consultas_del_listado() -> int:
        with CaptureQueriesContext(connection) as consultas:
            assert gerente.get(PROPIEDADES).status_code == 200
        return len(consultas)

    PropiedadFactory()
    con_una = consultas_del_listado()
    PropiedadFactory.create_batch(5)

    assert consultas_del_listado() == con_una


def test_tipos_de_propiedad_lista_los_siete(gerente):
    assert gerente.get(TIPOS).json()["count"] == 7


def test_estado_inicial_de_una_propiedad_es_en_negociacion(gerente):
    respuesta = gerente.post(PROPIEDADES, datos_propiedad(), format="json")

    assert respuesta.json()["estado"] == EstadoPropiedad.EN_NEGOCIACION


def test_cambiar_estado_de_unidad_por_la_api(gerente):
    unidad = UnidadFactory()

    respuesta = gerente.post(
        f"/api/v1/unidades/{unidad.pk}/cambiar-estado/",
        {"estado": "RESERVADA", "motivo": "Cotización aprobada"},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RESERVADA"


def test_patch_de_unidad_no_cambia_el_estado(gerente):
    unidad = UnidadFactory()

    respuesta = gerente.patch(
        f"/api/v1/unidades/{unidad.pk}/", {"estado": "VENDIDA"}, format="json"
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "EN_NEGOCIACION"
