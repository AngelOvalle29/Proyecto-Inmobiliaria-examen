"""Pruebas de los servicios de proveedores (spec 006, reglas 1 a 9)."""

import pytest

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.compras.enums import TipoProveedor
from apps.compras.exceptions import NitObligatorio, ProveedorDuplicado
from apps.compras.services import (
    ENTIDAD_PROVEEDOR,
    actualizar_proveedor,
    crear_proveedor,
    desactivar_proveedor,
)
from apps.core.exceptions import CiudadFueraDelPais
from apps.core.tests.factories import CiudadFactory, PaisFactory
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def autor():
    return UsuarioFactory(rol=Rol.objects.get(nombre="GERENTE"))


@pytest.fixture
def pais():
    return PaisFactory()


def crear(autor, pais, **cambios):
    datos = {"tipo": TipoProveedor.BANCO, "nombre": "Banco Demo", "nit": "1234567-8"}
    datos.update(cambios)
    datos.setdefault("pais", pais)
    return crear_proveedor(datos=datos, autor=autor, ip="203.0.113.5")


def registros(proveedor):
    return LogAuditoria.objects.filter(
        entidad=ENTIDAD_PROVEEDOR, entidad_id=proveedor.pk
    ).order_by("id")


# ---------- Crear ----------


def test_crear_genera_el_codigo_normaliza_el_nit_y_audita(autor, pais):
    proveedor = crear(autor, pais)

    assert proveedor.codigo == f"PRV-{proveedor.pk:04d}"
    assert proveedor.nit == "12345678"
    assert proveedor.creado_por == autor
    registro = registros(proveedor).get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["codigo"] == proveedor.codigo
    assert registro.ip == "203.0.113.5"


def test_un_banco_sin_nit_se_rechaza(autor, pais):
    with pytest.raises(NitObligatorio):
        crear(autor, pais, nit="")


def test_un_nit_solo_de_guiones_cuenta_como_vacio(autor, pais):
    with pytest.raises(NitObligatorio):
        crear(autor, pais, nit=" - ")


def test_un_propietario_particular_puede_no_tener_nit(autor, pais):
    proveedor = crear(autor, pais, tipo=TipoProveedor.PROPIETARIO_PARTICULAR, nit="")
    otro = crear(
        autor, pais, tipo=TipoProveedor.PROPIETARIO_PARTICULAR, nit="", nombre="Otro"
    )

    assert proveedor.nit == otro.nit == ""


def test_el_nit_repetido_se_rechaza_aunque_cambien_los_guiones(autor, pais):
    crear(autor, pais, nit="1234567-8")
    with pytest.raises(ProveedorDuplicado):
        crear(autor, pais, nit="1234567 8")


def test_el_nit_repetido_se_rechaza_aunque_el_primero_este_desactivado(autor, pais):
    primero = crear(autor, pais)
    desactivar_proveedor(proveedor=primero, autor=autor, ip=None)

    with pytest.raises(ProveedorDuplicado):
        crear(autor, pais)


def test_el_mismo_nit_en_otro_pais_se_acepta(autor, pais):
    crear(autor, pais)
    assert crear(autor, PaisFactory()).pk


def test_una_ciudad_de_otro_pais_se_rechaza(autor, pais):
    with pytest.raises(CiudadFueraDelPais):
        crear(autor, pais, ciudad=CiudadFactory())


def test_una_ciudad_de_su_pais_se_acepta(autor, pais):
    ciudad = CiudadFactory(pais=pais)
    assert crear(autor, pais, ciudad=ciudad).ciudad == ciudad


# ---------- Actualizar ----------


def test_actualizar_audita_solo_lo_que_cambio(autor, pais):
    proveedor = crear(autor, pais)

    actualizar_proveedor(
        proveedor=proveedor,
        datos={"nombre": "Banco Nuevo", "telefono": ""},
        autor=autor,
        ip=None,
    )

    registro = registros(proveedor).last()
    assert registro.accion == AccionAuditoria.ACTUALIZAR
    assert registro.valores_anteriores == {"nombre": "Banco Demo"}
    assert registro.valores_nuevos == {"nombre": "Banco Nuevo"}


def test_actualizar_sin_cambios_no_audita(autor, pais):
    proveedor = crear(autor, pais)

    actualizar_proveedor(
        proveedor=proveedor, datos={"nit": "1234567-8"}, autor=autor, ip=None
    )

    assert registros(proveedor).count() == 1


def test_cambiar_un_particular_a_banco_exige_el_nit(autor, pais):
    proveedor = crear(autor, pais, tipo=TipoProveedor.PROPIETARIO_PARTICULAR, nit="")

    with pytest.raises(NitObligatorio):
        actualizar_proveedor(
            proveedor=proveedor,
            datos={"tipo": TipoProveedor.BANCO},
            autor=autor,
            ip=None,
        )


def test_cambiar_solo_el_pais_valida_la_ciudad_que_ya_tenia(autor, pais):
    proveedor = crear(autor, pais, ciudad=CiudadFactory(pais=pais))

    with pytest.raises(CiudadFueraDelPais):
        actualizar_proveedor(
            proveedor=proveedor, datos={"pais": PaisFactory()}, autor=autor, ip=None
        )


def test_editar_el_nit_al_de_otro_proveedor_se_rechaza(autor, pais):
    crear(autor, pais, nit="111")
    segundo = crear(autor, pais, nit="222")

    with pytest.raises(ProveedorDuplicado):
        actualizar_proveedor(
            proveedor=segundo, datos={"nit": "111"}, autor=autor, ip=None
        )


def test_el_codigo_no_cambia_al_editar(autor, pais):
    proveedor = crear(autor, pais)
    codigo = proveedor.codigo

    actualizar_proveedor(
        proveedor=proveedor, datos={"codigo": "OTRO"}, autor=autor, ip=None
    )

    proveedor.refresh_from_db()
    assert proveedor.codigo == codigo


# ---------- Desactivar ----------


def test_desactivar_es_un_borrado_logico_auditado(autor, pais):
    proveedor = crear(autor, pais)

    desactivar_proveedor(proveedor=proveedor, autor=autor, ip=None)

    proveedor.refresh_from_db()
    assert proveedor.activo is False
    registro = registros(proveedor).last()
    assert registro.accion == AccionAuditoria.ELIMINAR
    assert registro.valores_nuevos == {"activo": False}
