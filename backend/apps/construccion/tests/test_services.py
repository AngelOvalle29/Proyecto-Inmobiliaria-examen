"""Pruebas de los servicios de constructoras (spec 006, reglas 4 a 9)."""

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.construccion.exceptions import ConstructoraDuplicada, NitObligatorio
from apps.construccion.services import (
    ENTIDAD_CONSTRUCTORA,
    actualizar_constructora,
    crear_constructora,
    desactivar_constructora,
)
from apps.core.tests.factories import PaisFactory
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def autor():
    return UsuarioFactory(rol=Rol.objects.get(nombre="ADMINISTRADOR"))


@pytest.fixture
def pais():
    return PaisFactory()


def crear(autor, pais, **cambios):
    datos = {"nombre": "Constructora Demo", "nit": "8000001-1"}
    datos.update(cambios)
    datos.setdefault("pais", pais)
    return crear_constructora(datos=datos, autor=autor, ip=None)


def registros(constructora):
    return LogAuditoria.objects.filter(
        entidad=ENTIDAD_CONSTRUCTORA, entidad_id=constructora.pk
    ).order_by("id")


def test_crear_genera_el_codigo_normaliza_el_nit_y_audita(autor, pais):
    constructora = crear(autor, pais)

    assert constructora.codigo == f"CST-{constructora.pk:04d}"
    assert constructora.nit == "80000011"
    assert constructora.calificacion is None
    registro = registros(constructora).get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["codigo"] == constructora.codigo


def test_un_nit_solo_de_guiones_se_rechaza(autor, pais):
    with pytest.raises(NitObligatorio):
        crear(autor, pais, nit="--")


def test_el_nit_repetido_se_rechaza_aunque_la_primera_este_desactivada(autor, pais):
    primera = crear(autor, pais)
    desactivar_constructora(constructora=primera, autor=autor, ip=None)

    with pytest.raises(ConstructoraDuplicada):
        crear(autor, pais, nit="8000001 1")


def test_el_mismo_nit_en_otro_pais_se_acepta(autor, pais):
    crear(autor, pais)
    assert crear(autor, PaisFactory()).pk


def test_actualizar_audita_solo_lo_que_cambio(autor, pais):
    constructora = crear(autor, pais)

    actualizar_constructora(
        constructora=constructora,
        datos={"calificacion": 4, "contacto": ""},
        autor=autor,
        ip=None,
    )

    registro = registros(constructora).last()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"calificacion": None}
    assert registro.valores_nuevos == {"calificacion": 4}


def test_actualizar_sin_cambios_no_audita(autor, pais):
    constructora = crear(autor, pais)

    actualizar_constructora(
        constructora=constructora, datos={"nit": "8000001-1"}, autor=autor, ip=None
    )

    assert registros(constructora).count() == 1


def test_editar_el_nit_al_de_otra_constructora_se_rechaza(autor, pais):
    crear(autor, pais, nit="111")
    segunda = crear(autor, pais, nit="222", nombre="Otra")

    with pytest.raises(ConstructoraDuplicada):
        actualizar_constructora(
            constructora=segunda, datos={"nit": "111"}, autor=autor, ip=None
        )


def test_desactivar_es_un_borrado_logico_auditado(autor, pais):
    constructora = crear(autor, pais)

    desactivar_constructora(constructora=constructora, autor=autor, ip=None)

    constructora.refresh_from_db()
    assert constructora.activo is False
    assert registros(constructora).last().accion == AccionAuditoria.ELIMINAR
