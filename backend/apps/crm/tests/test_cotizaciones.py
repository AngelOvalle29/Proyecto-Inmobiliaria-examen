"""
Pruebas de las cotizaciones (spec 007, reglas 1 a 6, 19 y 22).

Cubren los cuatro niveles de la §9: constraints del modelo, el flujo en los
servicios (con el estado del bien), la cartera en el selector y la API.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.crm.enums import EstadoCotizacion
from apps.crm.exceptions import (
    CotizacionNoEditable,
    CotizacionVencida,
    DescuentoFueraDeRango,
    SeVendePorUnidades,
    TransicionInvalida,
)
from apps.crm.models import Cotizacion
from apps.crm.selectors import listar_cotizaciones_visibles
from apps.crm.services import (
    actualizar_cotizacion,
    aprobar_cotizacion,
    crear_cotizacion,
    enviar_cotizacion,
    rechazar_cotizacion,
)
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ClienteFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.20"
COTIZACIONES = "/api/v1/cotizaciones/"


def usuario_con_rol(nombre):
    return UsuarioFactory(rol=Rol.objects.get(nombre=nombre))


def disponible(**cambios):
    return PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE, **cambios)


def en_15_dias():
    return timezone.localdate() + timedelta(days=15)


@pytest.fixture
def gerente():
    return usuario_con_rol(NombreRol.GERENTE)


def cotizar(autor, *, bien=None, cliente=None, **datos):
    bien = bien or disponible()
    clave = "unidad" if hasattr(bien, "nivel") else "propiedad"
    return crear_cotizacion(
        datos={
            "cliente": cliente or ClienteFactory(),
            clave: bien,
            "fecha_vencimiento": en_15_dias(),
            **datos,
        },
        autor=autor,
        ip=IP,
    )


def refrescar(*objetos):
    for objeto in objetos:
        objeto.refresh_from_db()


# ---------- Modelo ----------


def test_la_base_exige_exactamente_propiedad_o_unidad(gerente):
    cotizacion = cotizar(gerente)

    with pytest.raises(IntegrityError), transaction.atomic():
        Cotizacion.objects.filter(pk=cotizacion.pk).update(propiedad=None)


def test_la_base_exige_que_el_total_cuadre(gerente):
    cotizacion = cotizar(gerente)

    with pytest.raises(IntegrityError), transaction.atomic():
        Cotizacion.objects.filter(pk=cotizacion.pk).update(total=Decimal("1.00"))


# ---------- Crear (reglas 1 a 3 y 5) ----------


def test_crear_toma_precio_y_moneda_de_lista_y_el_agente_del_cliente(gerente):
    propiedad = disponible(precio_lista=Decimal("200000.00"))
    cliente = ClienteFactory()

    cotizacion = cotizar(
        gerente, bien=propiedad, cliente=cliente, descuento=Decimal("5000.00")
    )

    assert cotizacion.codigo == f"COT-{cotizacion.pk:05d}"
    assert cotizacion.estado == EstadoCotizacion.BORRADOR
    assert cotizacion.precio == Decimal("200000.00")
    assert cotizacion.total == Decimal("195000.00")
    assert cotizacion.moneda == propiedad.moneda
    assert cotizacion.agente == cliente.agente_asignado
    registro = LogAuditoria.objects.get(entidad="crm_cotizacion")
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["codigo"] == cotizacion.codigo


def test_no_se_cotiza_un_edificio_completo(gerente):
    """Regla 1: se cotizan sus unidades."""
    edificio = disponible(tipo=tipo("Apartamentos"))

    with pytest.raises(SeVendePorUnidades):
        cotizar(gerente, bien=edificio)


def test_se_cotiza_una_unidad(gerente):
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)

    cotizacion = cotizar(gerente, bien=unidad)

    assert cotizacion.unidad == unidad
    assert cotizacion.precio == unidad.precio_lista


def test_no_se_cotiza_un_bien_que_no_esta_disponible(gerente):
    """Regla 5."""
    with pytest.raises(PropiedadNoDisponible):
        cotizar(gerente, bien=PropiedadFactory(estado=EstadoPropiedad.RESERVADA))


def test_un_descuento_mayor_que_el_precio_se_rechaza(gerente):
    """Regla 2."""
    with pytest.raises(DescuentoFueraDeRango):
        cotizar(
            gerente,
            bien=disponible(precio_lista=Decimal("100.00")),
            descuento=Decimal("100.01"),
        )


# ---------- Editar (regla 4) ----------


def test_editar_un_borrador_recalcula_el_total(gerente):
    cotizacion = cotizar(gerente, bien=disponible(precio_lista=Decimal("1000.00")))

    actualizar_cotizacion(
        cotizacion=cotizacion,
        datos={"descuento": Decimal("100.00")},
        autor=gerente,
        ip=IP,
    )

    refrescar(cotizacion)
    assert cotizacion.total == Decimal("900.00")


def test_una_cotizacion_enviada_no_se_edita(gerente):
    cotizacion = cotizar(gerente)
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    with pytest.raises(CotizacionNoEditable):
        actualizar_cotizacion(
            cotizacion=cotizacion, datos={"observaciones": "x"}, autor=gerente, ip=IP
        )


# ---------- Flujo y estado del bien (reglas 4 a 6) ----------


def test_aprobar_reserva_el_bien_y_audita_aprobar(gerente):
    propiedad = disponible()
    cotizacion = cotizar(gerente, bien=propiedad)
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    aprobar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    refrescar(cotizacion, propiedad)
    assert cotizacion.estado == EstadoCotizacion.APROBADA
    assert propiedad.estado == EstadoPropiedad.RESERVADA
    assert LogAuditoria.objects.filter(
        entidad="crm_cotizacion", accion=AccionAuditoria.APROBAR
    ).exists()


def test_no_se_aprueba_un_borrador_sin_enviar(gerente):
    cotizacion = cotizar(gerente)

    with pytest.raises(TransicionInvalida):
        aprobar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)


def test_dos_cotizaciones_del_mismo_bien_no_se_aprueban_las_dos(gerente):
    """Regla 5: la segunda encuentra el bien ya RESERVADO."""
    propiedad = disponible()
    primera = cotizar(gerente, bien=propiedad)
    segunda = cotizar(gerente, bien=propiedad)
    for cotizacion in (primera, segunda):
        enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    aprobar_cotizacion(cotizacion=primera, autor=gerente, ip=IP)
    with pytest.raises(PropiedadNoDisponible):
        aprobar_cotizacion(cotizacion=segunda, autor=gerente, ip=IP)

    refrescar(segunda)
    assert segunda.estado == EstadoCotizacion.ENVIADA


def test_rechazar_una_aprobada_libera_el_bien(gerente):
    unidad = UnidadFactory(estado=EstadoPropiedad.DISPONIBLE)
    cotizacion = cotizar(gerente, bien=unidad)
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)
    aprobar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    rechazar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    refrescar(cotizacion, unidad)
    assert cotizacion.estado == EstadoCotizacion.RECHAZADA
    assert unidad.estado == EstadoPropiedad.DISPONIBLE


def test_rechazar_una_enviada_no_toca_el_bien(gerente):
    propiedad = disponible()
    cotizacion = cotizar(gerente, bien=propiedad)
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    rechazar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    refrescar(propiedad)
    assert propiedad.estado == EstadoPropiedad.DISPONIBLE


def test_una_cotizacion_vencida_no_se_envia(gerente):
    """Regla 4: vencida se calcula con la fecha, no se guarda."""
    cotizacion = cotizar(gerente)
    Cotizacion.objects.filter(pk=cotizacion.pk).update(
        fecha_emision=timezone.localdate() - timedelta(days=30),
        fecha_vencimiento=timezone.localdate() - timedelta(days=1),
    )
    refrescar(cotizacion)

    assert cotizacion.esta_vencida()
    with pytest.raises(CotizacionVencida):
        enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)
    refrescar(cotizacion)
    assert cotizacion.estado == EstadoCotizacion.BORRADOR


# ---------- Cartera (regla 22) ----------


def test_un_agente_solo_ve_las_cotizaciones_de_sus_clientes(gerente):
    mia = cotizar(gerente)
    cotizar(gerente)  # de un cliente de otro agente

    agente = mia.cliente.agente_asignado.usuario
    assert list(listar_cotizaciones_visibles(usuario=agente)) == [mia]


# ---------- API ----------


def http(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def test_api_flujo_completo_de_un_agente_sobre_su_cliente():
    cliente = ClienteFactory()
    agente = cliente.agente_asignado.usuario
    propiedad = disponible()
    api = http(agente)

    creada = api.post(
        COTIZACIONES,
        {
            "cliente": cliente.pk,
            "propiedad": propiedad.pk,
            "fecha_vencimiento": en_15_dias().isoformat(),
        },
        format="json",
    )
    assert creada.status_code == 201, creada.json()
    ruta = f"{COTIZACIONES}{creada.json()['id']}/"

    assert api.post(f"{ruta}enviar/").status_code == 200
    aprobada = api.post(f"{ruta}aprobar/")
    assert aprobada.json()["estado"] == "APROBADA"
    assert aprobada.json()["vencida"] is False
    refrescar(propiedad)
    assert propiedad.estado == EstadoPropiedad.RESERVADA


def test_api_un_agente_no_cotiza_a_un_cliente_ajeno():
    """El cliente ajeno no está en su cartera: responde como si no existiera."""
    ajeno = ClienteFactory()
    otro_agente = ClienteFactory().agente_asignado.usuario

    respuesta = http(otro_agente).post(
        COTIZACIONES,
        {
            "cliente": ajeno.pk,
            "propiedad": disponible().pk,
            "fecha_vencimiento": en_15_dias().isoformat(),
        },
        format="json",
    )

    assert respuesta.status_code == 400
    assert "cliente" in respuesta.json()["error"]["detalles"]


def test_api_la_cotizacion_ajena_responde_404(gerente):
    ajena = cotizar(gerente)
    otro_agente = ClienteFactory().agente_asignado.usuario

    respuesta = http(otro_agente).post(f"{COTIZACIONES}{ajena.pk}/enviar/")

    assert respuesta.status_code == 404


@pytest.mark.parametrize("rol", [NombreRol.CONTABILIDAD, NombreRol.CONSULTA])
def test_api_contabilidad_y_consulta_leen_pero_no_cotizan(rol, gerente):
    cotizacion = cotizar(gerente)
    api = http(usuario_con_rol(rol))

    assert api.get(COTIZACIONES).json()["count"] == 1
    assert api.post(f"{COTIZACIONES}{cotizacion.pk}/enviar/").status_code == 403


def test_api_propiedad_y_unidad_a_la_vez_responde_400(gerente):
    respuesta = http(gerente).post(
        COTIZACIONES,
        {
            "cliente": ClienteFactory().pk,
            "propiedad": disponible().pk,
            "unidad": UnidadFactory(estado=EstadoPropiedad.DISPONIBLE).pk,
            "fecha_vencimiento": en_15_dias().isoformat(),
        },
        format="json",
    )

    assert respuesta.status_code == 400


def test_api_editar_una_enviada_responde_409(gerente):
    cotizacion = cotizar(gerente)
    enviar_cotizacion(cotizacion=cotizacion, autor=gerente, ip=IP)

    respuesta = http(gerente).patch(
        f"{COTIZACIONES}{cotizacion.pk}/", {"observaciones": "x"}, format="json"
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "COTIZACION_NO_EDITABLE"


def test_api_filtra_por_estado(gerente):
    enviada = cotizar(gerente)
    enviar_cotizacion(cotizacion=enviada, autor=gerente, ip=IP)
    cotizar(gerente)

    respuesta = http(gerente).get(COTIZACIONES, {"estado": "ENVIADA"})

    assert [c["id"] for c in respuesta.json()["results"]] == [enviada.pk]
