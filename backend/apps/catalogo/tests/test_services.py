"""Pruebas de los servicios de catálogo."""

from decimal import Decimal

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import (
    PropiedadConUnidades,
    TipoSinUnidades,
    UnidadDuplicada,
)
from apps.catalogo.models import Propiedad, Unidad
from apps.catalogo.services import (
    actualizar_propiedad,
    actualizar_unidad,
    cambiar_estado_propiedad,
    cambiar_estado_unidad,
    crear_propiedad,
    crear_unidad,
    desactivar_propiedad,
    desactivar_unidad,
)
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.core.tests.factories import CiudadFactory, MonedaFactory
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.7"


def _datos_propiedad(**cambios) -> dict:
    datos = {
        "nombre": "Casa demo",
        "tipo": tipo("Casa"),
        "ciudad": CiudadFactory(),
        "direccion": "Calle demo 1",
        "area_m2": Decimal("300.00"),
        "precio_lista": Decimal("200000.00"),
        "moneda": MonedaFactory(codigo="USD"),
    }
    return {**datos, **cambios}


def _datos_unidad(**cambios) -> dict:
    datos = {
        "codigo": "A-101",
        "nivel": 1,
        "area_m2": Decimal("80.00"),
        "precio_lista": Decimal("95000.00"),
        "moneda": MonedaFactory(codigo="USD"),
    }
    return {**datos, **cambios}


def _ultimo_registro() -> LogAuditoria:
    return LogAuditoria.objects.latest("id")


def test_crear_propiedad_genera_codigo_y_audita_con_el_codigo_final():
    autor = UsuarioFactory()

    propiedad = crear_propiedad(datos=_datos_propiedad(), autor=autor, ip=IP)

    assert propiedad.codigo == f"PROP-{propiedad.pk:05d}"
    assert propiedad.estado == EstadoPropiedad.EN_NEGOCIACION
    assert propiedad.creado_por == autor
    registro = _ultimo_registro()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.entidad == "catalogo_propiedad"
    assert registro.entidad_id == propiedad.pk
    assert registro.usuario == autor
    assert registro.ip == IP
    assert registro.valores_nuevos["codigo"] == propiedad.codigo
    assert registro.valores_nuevos["precio_lista"] == "200000.00"


def test_crear_propiedad_ignora_estado_y_codigo_enviados():
    propiedad = crear_propiedad(
        datos=_datos_propiedad(estado=EstadoPropiedad.VENDIDA, codigo="X"),
        autor=UsuarioFactory(),
        ip=IP,
    )

    assert propiedad.estado == EstadoPropiedad.EN_NEGOCIACION
    assert propiedad.codigo.startswith("PROP-")


def test_actualizar_propiedad_audita_solo_lo_que_cambia_y_no_toca_el_estado():
    propiedad = PropiedadFactory(nombre="Antes")

    actualizar_propiedad(
        propiedad=propiedad,
        datos={"nombre": "Después", "estado": EstadoPropiedad.VENDIDA},
        autor=UsuarioFactory(),
        ip=IP,
    )

    propiedad.refresh_from_db()
    assert propiedad.nombre == "Después"
    assert propiedad.estado == EstadoPropiedad.EN_NEGOCIACION
    registro = _ultimo_registro()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"nombre": "Antes"}
    assert registro.valores_nuevos == {"nombre": "Después"}


def test_actualizar_propiedad_sin_cambios_no_audita():
    propiedad = PropiedadFactory(nombre="Igual")

    actualizar_propiedad(
        propiedad=propiedad, datos={"nombre": "Igual"}, autor=UsuarioFactory(), ip=IP
    )

    assert not LogAuditoria.objects.exists()


def test_cambiar_estado_audita_anterior_nuevo_y_motivo():
    propiedad = PropiedadFactory()

    cambiar_estado_propiedad(
        propiedad=propiedad,
        estado=EstadoPropiedad.DISPONIBLE,
        autor=UsuarioFactory(),
        ip=IP,
        motivo="Escrituras listas",
    )

    propiedad.refresh_from_db()
    assert propiedad.estado == EstadoPropiedad.DISPONIBLE
    registro = _ultimo_registro()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"estado": "EN_NEGOCIACION"}
    assert registro.valores_nuevos == {
        "estado": "DISPONIBLE",
        "motivo": "Escrituras listas",
    }


def test_cambiar_estado_al_mismo_estado_no_audita():
    propiedad = PropiedadFactory()

    cambiar_estado_propiedad(
        propiedad=propiedad,
        estado=EstadoPropiedad.EN_NEGOCIACION,
        autor=None,
        ip=None,
        motivo="Sin cambio",
    )

    assert not LogAuditoria.objects.exists()


def test_cambiar_estado_lo_puede_hacer_el_sistema():
    cambiar_estado_propiedad(
        propiedad=PropiedadFactory(),
        estado=EstadoPropiedad.VENDIDA,
        autor=None,
        ip=None,
        motivo="Venta cerrada",
    )

    assert _ultimo_registro().usuario is None


def test_desactivar_propiedad_con_unidades_activas_se_rechaza():
    unidad = UnidadFactory()

    with pytest.raises(PropiedadConUnidades):
        desactivar_propiedad(propiedad=unidad.propiedad, autor=UsuarioFactory(), ip=IP)

    unidad.propiedad.refresh_from_db()
    assert unidad.propiedad.activo


def test_desactivar_propiedad_sin_unidades_activas_es_borrado_logico():
    unidad = UnidadFactory()
    autor = UsuarioFactory()
    desactivar_unidad(unidad=unidad, autor=autor, ip=IP)

    desactivar_propiedad(propiedad=unidad.propiedad, autor=autor, ip=IP)

    propiedad = Propiedad.objects.get(pk=unidad.propiedad.pk)
    assert not propiedad.activo
    registro = _ultimo_registro()
    assert registro.accion == AccionAuditoria.ELIMINAR
    assert registro.entidad == "catalogo_propiedad"


def test_crear_unidad_en_tipo_sin_unidades_se_rechaza():
    casa = PropiedadFactory(tipo=tipo("Casa"))

    with pytest.raises(TipoSinUnidades):
        crear_unidad(
            propiedad=casa, datos=_datos_unidad(), autor=UsuarioFactory(), ip=IP
        )

    assert not Unidad.objects.exists()


def test_crear_unidad_audita_con_su_propiedad():
    edificio = PropiedadFactory(tipo=tipo("Apartamentos"))

    unidad = crear_unidad(
        propiedad=edificio, datos=_datos_unidad(), autor=UsuarioFactory(), ip=IP
    )

    assert unidad.propiedad == edificio
    registro = _ultimo_registro()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.entidad == "catalogo_unidad"
    assert registro.valores_nuevos["propiedad"] == edificio.pk
    assert registro.valores_nuevos["codigo"] == "A-101"


def test_crear_unidad_con_codigo_repetido_se_rechaza_aunque_este_desactivada():
    existente = UnidadFactory(codigo="A-101", activo=False)

    with pytest.raises(UnidadDuplicada):
        crear_unidad(
            propiedad=existente.propiedad,
            datos=_datos_unidad(codigo="A-101"),
            autor=UsuarioFactory(),
            ip=IP,
        )


def test_actualizar_unidad_a_un_codigo_repetido_se_rechaza():
    primera = UnidadFactory(codigo="A-101")
    segunda = UnidadFactory(codigo="A-102", propiedad=primera.propiedad)

    with pytest.raises(UnidadDuplicada):
        actualizar_unidad(
            unidad=segunda, datos={"codigo": "A-101"}, autor=UsuarioFactory(), ip=IP
        )


def test_actualizar_unidad_con_su_mismo_codigo_no_se_rechaza():
    unidad = UnidadFactory(codigo="A-101", nivel=1)

    actualizar_unidad(
        unidad=unidad,
        datos={"codigo": "A-101", "nivel": 2},
        autor=UsuarioFactory(),
        ip=IP,
    )

    unidad.refresh_from_db()
    assert unidad.nivel == 2


def test_cambiar_estado_de_unidad_audita_y_no_toca_la_propiedad():
    unidad = UnidadFactory()

    cambiar_estado_unidad(
        unidad=unidad,
        estado=EstadoPropiedad.VENDIDA,
        autor=UsuarioFactory(),
        ip=IP,
        motivo="Contrato firmado",
    )

    unidad.refresh_from_db()
    unidad.propiedad.refresh_from_db()
    assert unidad.estado == EstadoPropiedad.VENDIDA
    assert unidad.propiedad.estado == EstadoPropiedad.EN_NEGOCIACION
    registro = _ultimo_registro()
    assert registro.entidad == "catalogo_unidad"
    assert registro.valores_anteriores == {"estado": "EN_NEGOCIACION"}
    assert registro.valores_nuevos == {
        "estado": "VENDIDA",
        "motivo": "Contrato firmado",
    }


def test_cambiar_estado_de_unidad_al_mismo_estado_no_audita():
    cambiar_estado_unidad(
        unidad=UnidadFactory(),
        estado=EstadoPropiedad.EN_NEGOCIACION,
        autor=None,
        ip=None,
        motivo="Sin cambio",
    )

    assert not LogAuditoria.objects.exists()


def test_actualizar_unidad_no_cambia_el_estado():
    unidad = UnidadFactory()

    actualizar_unidad(
        unidad=unidad,
        datos={"estado": EstadoPropiedad.VENDIDA},
        autor=UsuarioFactory(),
        ip=IP,
    )

    unidad.refresh_from_db()
    assert unidad.estado == EstadoPropiedad.EN_NEGOCIACION
