"""Pruebas de los servicios de proyectos de construcción (spec 017, reglas 9 a 18,
23 y 26)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory, tipo
from apps.construccion.enums import EstadoProyecto
from apps.construccion.exceptions import (
    AvanceInvalido,
    ConstructoraConProyectos,
    FechaInvalida,
    PropiedadConProyecto,
    TransicionInvalida,
)
from apps.construccion.services import (
    ENTIDAD_PROYECTO,
    actualizar_proyecto,
    cancelar_proyecto,
    crear_proyecto,
    desactivar_constructora,
    finalizar_proyecto,
    iniciar_proyecto,
    reanudar_proyecto,
    registrar_avance,
    suspender_proyecto,
)
from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.tests.factories import MonedaFactory, TipoCambioFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db

IP = "203.0.113.50"
HOY = timezone.localdate()


@pytest.fixture
def gerente():
    return UsuarioFactory(rol=Rol.objects.get(nombre=NombreRol.GERENTE))


@pytest.fixture
def usd():
    return MonedaFactory(codigo="USD")


@pytest.fixture
def gtq(usd):
    """Quetzal con su tasa al dólar desde hace un mes (regla 11)."""
    moneda = MonedaFactory(codigo="GTQ")
    TipoCambioFactory(
        moneda_origen=moneda,
        moneda_destino=usd,
        tasa=Decimal("0.129032"),
        fecha=HOY - timedelta(days=30),
    )
    return moneda


def adquirida(**cambios):
    return PropiedadFactory(estado=EstadoPropiedad.ADQUIRIDA, **cambios)


def crear(autor, moneda, **cambios):
    datos = {
        "nombre": "Remodelación demo",
        "propiedad": adquirida(),
        "constructora": ConstructoraFactory(),
        "fecha_inicio": HOY,
        "fecha_fin_estimada": HOY + timedelta(days=180),
        "presupuesto_total": Decimal("500000.00"),
        "moneda": moneda,
    }
    datos.update(cambios)
    return crear_proyecto(datos=datos, autor=autor, ip=IP)


def en_ejecucion(autor, moneda, **cambios):
    proyecto = crear(autor, moneda, **cambios)
    return iniciar_proyecto(proyecto=proyecto, autor=autor, ip=IP)


def estado_de(instancia):
    instancia.refresh_from_db()
    return instancia.estado


def mover_a_mano(propiedad, estado):
    """Como /cambiar-estado/ del catálogo, que no conoce los proyectos (regla 26)."""
    propiedad.estado = estado
    propiedad.save(update_fields=["estado"])


# ---------- Registrar (reglas 9 a 11 y 18) ----------


def test_registra_planificado_con_avance_cero_y_codigo(gerente, usd):
    proyecto = crear(gerente, usd)

    assert proyecto.codigo == f"PC-{proyecto.pk:05d}"
    assert proyecto.estado == EstadoProyecto.PLANIFICADO
    assert proyecto.porcentaje_avance == 0
    assert proyecto.presupuesto_total_usd == Decimal("500000.00")
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.ADQUIRIDA


def test_guarda_la_tasa_de_la_fecha_de_inicio(gerente, gtq):
    proyecto = crear(gerente, gtq, presupuesto_total=Decimal("100000.00"))

    assert proyecto.tasa_a_usd == Decimal("0.129032")
    assert proyecto.presupuesto_total_usd == Decimal("12903.20")


def test_sin_tasa_no_se_registra(gerente):
    MonedaFactory(codigo="USD")
    with pytest.raises(TipoCambioNoDisponible):
        crear(gerente, MonedaFactory(codigo="HNL"))


@pytest.mark.parametrize(
    "estado",
    [EstadoPropiedad.EN_NEGOCIACION, EstadoPropiedad.DISPONIBLE],
)
def test_la_propiedad_debe_estar_adquirida(gerente, usd, estado):
    """Regla 9: no se remodela una propiedad ya disponible (§10)."""
    with pytest.raises(PropiedadNoDisponible):
        crear(gerente, usd, propiedad=PropiedadFactory(estado=estado))


def test_un_segundo_proyecto_activo_sobre_la_propiedad_se_rechaza(gerente, usd):
    """Regla 10: tras cancelar el primero, sí se acepta otro."""
    primero = crear(gerente, usd)

    with pytest.raises(PropiedadConProyecto):
        crear(gerente, usd, propiedad=primero.propiedad)

    cancelar_proyecto(proyecto=primero, motivo="Cambio de planes", autor=gerente, ip=IP)
    assert crear(gerente, usd, propiedad=primero.propiedad).estado == "PLANIFICADO"


def test_la_fecha_de_fin_estimada_no_puede_ser_anterior_al_inicio(gerente, usd):
    with pytest.raises(FechaInvalida) as error:
        crear(gerente, usd, fecha_fin_estimada=HOY - timedelta(days=1))
    assert "fecha_fin_estimada" in error.value.detalles


def test_registrar_queda_en_la_bitacora(gerente, usd):
    proyecto = crear(gerente, usd)

    registro = LogAuditoria.objects.get(entidad=ENTIDAD_PROYECTO)
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.valores_nuevos["codigo"] == proyecto.codigo


# ---------- Iniciar (regla 12) ----------


def test_iniciar_deja_la_propiedad_en_construccion(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)

    assert proyecto.estado == EstadoProyecto.EN_EJECUCION
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.EN_CONSTRUCCION


def test_iniciar_dos_veces_se_rechaza(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    with pytest.raises(TransicionInvalida):
        iniciar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)


def test_iniciar_si_la_propiedad_ya_no_esta_adquirida_no_cambia_nada(gerente, usd):
    proyecto = crear(gerente, usd)
    mover_a_mano(proyecto.propiedad, EstadoPropiedad.DISPONIBLE)

    with pytest.raises(PropiedadNoDisponible):
        iniciar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)
    assert estado_de(proyecto) == EstadoProyecto.PLANIFICADO


# ---------- Avance (regla 13) ----------


def test_el_avance_sube_y_queda_en_la_bitacora_con_su_descripcion(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)

    registrar_avance(
        proyecto=proyecto, porcentaje=40, descripcion="Losa", autor=gerente, ip=IP
    )

    proyecto.refresh_from_db()
    assert proyecto.porcentaje_avance == 40
    registro = LogAuditoria.objects.filter(entidad=ENTIDAD_PROYECTO).latest("id")
    assert registro.valores_anteriores == {"porcentaje_avance": 0}
    assert registro.valores_nuevos == {"porcentaje_avance": 40, "descripcion": "Losa"}


def test_el_avance_puede_repetirse_pero_no_bajar(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=40, descripcion="a", autor=gerente, ip=IP
    )
    registrar_avance(
        proyecto=proyecto, porcentaje=40, descripcion="b", autor=gerente, ip=IP
    )

    with pytest.raises(AvanceInvalido):
        registrar_avance(
            proyecto=proyecto, porcentaje=30, descripcion="c", autor=gerente, ip=IP
        )


def test_el_avance_no_pasa_de_100(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    with pytest.raises(AvanceInvalido):
        registrar_avance(
            proyecto=proyecto, porcentaje=101, descripcion="x", autor=gerente, ip=IP
        )


def test_el_avance_solo_en_ejecucion(gerente, usd):
    proyecto = crear(gerente, usd)
    with pytest.raises(TransicionInvalida):
        registrar_avance(
            proyecto=proyecto, porcentaje=10, descripcion="x", autor=gerente, ip=IP
        )


# ---------- Suspender y reanudar (regla 14) ----------


def test_suspender_y_reanudar_no_cambian_la_propiedad(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)

    suspender_proyecto(proyecto=proyecto, motivo="Lluvias", autor=gerente, ip=IP)
    assert estado_de(proyecto) == EstadoProyecto.SUSPENDIDO
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.EN_CONSTRUCCION

    reanudar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)
    assert estado_de(proyecto) == EstadoProyecto.EN_EJECUCION


def test_suspender_guarda_el_motivo(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    suspender_proyecto(proyecto=proyecto, motivo="Lluvias", autor=gerente, ip=IP)

    registro = LogAuditoria.objects.filter(entidad=ENTIDAD_PROYECTO).latest("id")
    assert registro.valores_nuevos["motivo"] == "Lluvias"


def test_reanudar_uno_que_no_esta_suspendido_se_rechaza(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    with pytest.raises(TransicionInvalida):
        reanudar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)


# ---------- Finalizar (regla 15) ----------


def test_finalizar_con_avance_100_deja_la_propiedad_disponible(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=100, descripcion="Fin", autor=gerente, ip=IP
    )

    finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)

    proyecto.refresh_from_db()
    assert proyecto.estado == EstadoProyecto.FINALIZADO
    assert proyecto.fecha_fin_real == HOY
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.DISPONIBLE


def test_finalizar_con_avance_menor_se_rechaza(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=90, descripcion="x", autor=gerente, ip=IP
    )

    with pytest.raises(AvanceInvalido):
        finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)
    assert estado_de(proyecto) == EstadoProyecto.EN_EJECUCION


def test_finalizar_publica_las_unidades_que_no_estaban_a_la_venta(gerente, usd):
    """Regla 15: en un edificio se venden las unidades, no el edificio."""
    edificio = adquirida(tipo=tipo("Apartamentos"))
    en_negociacion = UnidadFactory(
        propiedad=edificio, estado=EstadoPropiedad.EN_NEGOCIACION
    )
    # Como las del hotel de la demo del catálogo.
    en_construccion = UnidadFactory(
        propiedad=edificio, estado=EstadoPropiedad.EN_CONSTRUCCION
    )
    reservada = UnidadFactory(propiedad=edificio, estado=EstadoPropiedad.RESERVADA)
    proyecto = en_ejecucion(gerente, usd, propiedad=edificio)
    registrar_avance(
        proyecto=proyecto, porcentaje=100, descripcion="Fin", autor=gerente, ip=IP
    )

    finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)

    assert estado_de(en_negociacion) == EstadoPropiedad.DISPONIBLE
    assert estado_de(en_construccion) == EstadoPropiedad.DISPONIBLE
    # Las que ya tenían otro estado siguen su propio camino.
    assert estado_de(reservada) == EstadoPropiedad.RESERVADA


def test_finalizar_si_movieron_la_propiedad_responde_su_estado_y_no_cambia_nada(
    gerente, usd
):
    """Regla 26: la salida es devolverla a EN_CONSTRUCCION y volver a finalizar."""
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=100, descripcion="x", autor=gerente, ip=IP
    )
    mover_a_mano(proyecto.propiedad, EstadoPropiedad.BAJA)

    with pytest.raises(PropiedadNoDisponible) as error:
        finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)

    assert error.value.detalles["estado_actual"] == EstadoPropiedad.BAJA
    assert estado_de(proyecto) == EstadoProyecto.EN_EJECUCION


# ---------- Cancelar (regla 16) ----------


def test_cancelar_una_obra_iniciada_devuelve_la_propiedad_a_adquirida(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)

    cancelar_proyecto(proyecto=proyecto, motivo="Sin fondos", autor=gerente, ip=IP)

    assert estado_de(proyecto) == EstadoProyecto.CANCELADO
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.ADQUIRIDA
    registro = LogAuditoria.objects.filter(
        entidad=ENTIDAD_PROYECTO, accion=AccionAuditoria.ANULAR
    ).get()
    assert registro.valores_nuevos["motivo"] == "Sin fondos"


def test_cancelar_si_movieron_la_propiedad_funciona_y_lo_anota(gerente, usd):
    """Regla 26: cancelar siempre es posible."""
    proyecto = en_ejecucion(gerente, usd)
    mover_a_mano(proyecto.propiedad, EstadoPropiedad.DISPONIBLE)

    cancelar_proyecto(
        proyecto=proyecto, motivo="Se vendió sin obra", autor=gerente, ip=IP
    )

    assert estado_de(proyecto) == EstadoProyecto.CANCELADO
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.DISPONIBLE
    registro = LogAuditoria.objects.filter(
        entidad=ENTIDAD_PROYECTO, accion=AccionAuditoria.ANULAR
    ).get()
    assert registro.valores_nuevos["propiedad_sin_cambio"] == EstadoPropiedad.DISPONIBLE


def test_cancelar_un_planificado_no_toca_la_propiedad(gerente, usd):
    proyecto = crear(gerente, usd)
    cancelar_proyecto(proyecto=proyecto, motivo="x", autor=gerente, ip=IP)
    assert estado_de(proyecto.propiedad) == EstadoPropiedad.ADQUIRIDA


def test_cancelar_uno_finalizado_se_rechaza(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=100, descripcion="x", autor=gerente, ip=IP
    )
    finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        cancelar_proyecto(proyecto=proyecto, motivo="x", autor=gerente, ip=IP)


# ---------- Editar (regla 17) ----------


def test_editar_un_activo_cambia_los_tres_campos_y_convierte_con_la_misma_tasa(
    gerente, gtq
):
    proyecto = crear(gerente, gtq, presupuesto_total=Decimal("100000.00"))

    actualizar_proyecto(
        proyecto=proyecto,
        datos={
            "nombre": "Ampliación",
            "fecha_fin_estimada": HOY + timedelta(days=365),
            "presupuesto_total": Decimal("200000.00"),
        },
        autor=gerente,
        ip=IP,
    )

    proyecto.refresh_from_db()
    assert proyecto.nombre == "Ampliación"
    assert proyecto.tasa_a_usd == Decimal("0.129032")
    assert proyecto.presupuesto_total_usd == Decimal("25806.40")


def test_editar_un_finalizado_solo_admite_el_presupuesto(gerente, usd):
    proyecto = en_ejecucion(gerente, usd)
    registrar_avance(
        proyecto=proyecto, porcentaje=100, descripcion="x", autor=gerente, ip=IP
    )
    finalizar_proyecto(proyecto=proyecto, autor=gerente, ip=IP)

    actualizar_proyecto(
        proyecto=proyecto,
        datos={"presupuesto_total": Decimal("600000.00")},
        autor=gerente,
        ip=IP,
    )
    with pytest.raises(TransicionInvalida):
        actualizar_proyecto(
            proyecto=proyecto, datos={"nombre": "Otro"}, autor=gerente, ip=IP
        )
    proyecto.refresh_from_db()
    assert proyecto.presupuesto_total == Decimal("600000.00")


def test_editar_un_cancelado_se_rechaza(gerente, usd):
    proyecto = crear(gerente, usd)
    cancelar_proyecto(proyecto=proyecto, motivo="x", autor=gerente, ip=IP)

    with pytest.raises(TransicionInvalida):
        actualizar_proyecto(
            proyecto=proyecto,
            datos={"presupuesto_total": Decimal("1.00")},
            autor=gerente,
            ip=IP,
        )


def test_editar_audita_solo_lo_que_cambio(gerente, usd):
    proyecto = crear(gerente, usd)

    actualizar_proyecto(
        proyecto=proyecto,
        datos={
            "nombre": "Otro nombre",
            "presupuesto_total": proyecto.presupuesto_total,
        },
        autor=gerente,
        ip=IP,
    )

    registro = LogAuditoria.objects.filter(entidad=ENTIDAD_PROYECTO).latest("id")
    assert registro.valores_nuevos == {"nombre": "Otro nombre"}


def test_editar_la_fecha_de_fin_antes_del_inicio_se_rechaza(gerente, usd):
    proyecto = crear(gerente, usd)
    with pytest.raises(FechaInvalida):
        actualizar_proyecto(
            proyecto=proyecto,
            datos={"fecha_fin_estimada": HOY - timedelta(days=1)},
            autor=gerente,
            ip=IP,
        )


# ---------- Desactivar constructora (regla 23) ----------


def test_una_constructora_con_un_proyecto_activo_no_se_desactiva(gerente, usd):
    proyecto = crear(gerente, usd)

    with pytest.raises(ConstructoraConProyectos):
        desactivar_constructora(
            constructora=proyecto.constructora, autor=gerente, ip=IP
        )


def test_una_constructora_con_proyectos_cerrados_si_se_desactiva(gerente, usd):
    proyecto = crear(gerente, usd)
    cancelar_proyecto(proyecto=proyecto, motivo="x", autor=gerente, ip=IP)

    desactivar_constructora(constructora=proyecto.constructora, autor=gerente, ip=IP)

    proyecto.constructora.refresh_from_db()
    assert not proyecto.constructora.activo
