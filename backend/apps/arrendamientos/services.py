"""Servicios de arrendamientos: escrituras con reglas de negocio,
transacciones y auditoría (spec 008).

No conocen request ni hablan HTTP. Sigue el patrón de ventas (spec 007):
estado del bien por el catálogo con estado_requerido, tasa al dólar y cartera.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.selectors import listar_propiedades, listar_unidades
from apps.catalogo.services import cambiar_estado_propiedad, cambiar_estado_unidad
from apps.core.exceptions import ErrorDominio, TipoCambioNoDisponible
from apps.core.fechas import sumar_meses
from apps.core.selectors import obtener_tipo_cambio
from apps.crm.selectors import obtener_cliente_por_email
from apps.usuarios.models import Usuario

from . import datos_demo
from .enums import EstadoArrendamiento, EstadoPagoRenta
from .exceptions import (
    ArrendamientoNoVigente,
    ContratoNoTerminado,
    ContratoYaRenovado,
    FechaPagoRentaInvalida,
    FechaRescisionInvalida,
    MontoIncorrecto,
    PagoNoPendiente,
    SeArriendaPorUnidades,
)
from .models import ContratoArrendamiento, PagoRenta
from .selectors import obtener_dolar

CENTAVOS = Decimal("0.01")
CAMPOS_AUDITADOS = [
    "codigo",
    "cliente",
    "agente",
    "propiedad",
    "unidad",
    "fecha_inicio",
    "duracion_meses",
    "fecha_fin",
    "renta_mensual",
    "moneda",
    "tasa_a_usd",
    "deposito",
    "dia_cobro",
    "dias_gracia",
    "porcentaje_mora",
    "estado",
    "contrato_anterior",
]


# ---------- Funciones puras ----------


def calcular_fecha_fin(*, inicio: date, duracion_meses: int) -> date:
    """
    Regla 3: inicio + duración − 1 día, con la regla de fin de mes de
    core/fechas. Del 1 de enero con 12 meses: 31 de diciembre.
    """
    return sumar_meses(inicio, duracion_meses) - timedelta(days=1)


def calcular_calendario(
    *, inicio: date, duracion_meses: int, dia_cobro: int
) -> list[date]:
    """
    Regla 4: la fecha de vencimiento de cada mes de renta.

    El primer cobro es la primera fecha con el día de cobro igual o posterior
    al inicio; los demás, ese mismo día de cada mes siguiente. Como el día de
    cobro va del 1 al 28, todos los meses lo tienen y nunca hay que ajustarlo.
    """
    primera = inicio.replace(day=dia_cobro)
    if primera < inicio:
        primera = sumar_meses(primera, 1)
    return [sumar_meses(primera, mes) for mes in range(duracion_meses)]


def calcular_recargo(
    *,
    renta: Decimal,
    porcentaje: Decimal,
    vencimiento: date,
    dias_gracia: int,
    fecha_pago: date,
) -> Decimal:
    """
    Regla 6: recargo fijo por pagar tarde (decidido por B).

    Si el pago llega después del vencimiento más los días de gracia, se cobra
    renta · porcentaje, redondeado a centavos con ROUND_HALF_UP. Dentro de la
    gracia, nada: el último día de gracia todavía no tiene recargo.
    """
    if fecha_pago <= vencimiento + timedelta(days=dias_gracia):
        return Decimal("0.00")
    return (renta * porcentaje / 100).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


# ---------- Firmar y renovar ----------


@transaction.atomic
def firmar_arrendamiento(
    *, datos: dict, autor: Usuario | None, ip: str | None
) -> ContratoArrendamiento:
    """
    Firma un contrato de arrendamiento (spec 008, reglas 1 a 5).

    - Un edificio no se arrienda completo: se arriendan sus unidades (regla 1).
    - El bien debe estar DISPONIBLE y pasa a ARRENDADA. El catálogo lo
      comprueba bajo el bloqueo de su fila (estado_requerido), como en ventas.
    - El agente es el asignado al cliente (regla 2).
    - La fecha de fin se calcula y se generan todos los pagos de renta, uno por
      mes, sin prorrateo (reglas 3 y 4).
    - Guarda la tasa al dólar de la fecha de firma, que es hoy (regla 5).

    datos ya viene validado: cliente visible para el autor (cartera) y los
    rangos de la regla 3.
    """
    propiedad, unidad = datos.get("propiedad"), datos.get("unidad")
    if propiedad is not None and propiedad.tipo.requiere_unidades:
        raise SeArriendaPorUnidades(propiedad=propiedad.codigo)

    cliente = datos["cliente"]
    _cambiar_estado_bien(
        propiedad=propiedad,
        unidad=unidad,
        estado=EstadoPropiedad.ARRENDADA,
        requerido=EstadoPropiedad.DISPONIBLE,
        motivo=f"Arrendamiento a {cliente.codigo}",
        autor=autor,
        ip=ip,
    )
    contrato = _crear_contrato(datos=datos, autor=autor)
    _auditar_creacion(contrato, autor=autor, ip=ip)
    return contrato


@transaction.atomic
def renovar_arrendamiento(
    *,
    contrato: ContratoArrendamiento,
    renta_mensual: Decimal,
    duracion_meses: int,
    autor: Usuario | None,
    ip: str | None,
) -> ContratoArrendamiento:
    """
    Regla 9: crea un contrato nuevo para el mismo cliente y el mismo bien, que
    empieza el día siguiente al fin del anterior, con su propia renta y
    duración. El anterior queda RENOVADO y el bien sigue ARRENDADA.

    Solo se renueva un contrato VIGENTE, y una sola vez: un contrato vencido
    ya liberó su bien, que pudo arrendarse a otro. Los demás datos (moneda,
    depósito, día de cobro, gracia y mora) se copian del anterior.
    """
    contrato = ContratoArrendamiento.objects.select_for_update().get(pk=contrato.pk)
    if contrato.estado != EstadoArrendamiento.VIGENTE:
        raise ContratoYaRenovado(contrato=contrato.codigo, estado=contrato.estado)

    nuevo = _crear_contrato(
        datos={
            "cliente": contrato.cliente,
            "propiedad": contrato.propiedad,
            "unidad": contrato.unidad,
            "fecha_inicio": contrato.fecha_fin + timedelta(days=1),
            "duracion_meses": duracion_meses,
            "renta_mensual": renta_mensual,
            "moneda": contrato.moneda,
            "deposito": contrato.deposito,
            "dia_cobro": contrato.dia_cobro,
            "dias_gracia": contrato.dias_gracia,
            "porcentaje_mora": contrato.porcentaje_mora,
        },
        autor=autor,
        anterior=contrato,
    )
    _cambiar_estado_contrato(
        contrato, EstadoArrendamiento.RENOVADO, AccionAuditoria.ACTUALIZAR, autor, ip
    )
    _auditar_creacion(nuevo, autor=autor, ip=ip)
    return nuevo


# ---------- Rescindir y finalizar ----------


@transaction.atomic
def rescindir_arrendamiento(
    *,
    contrato: ContratoArrendamiento,
    fecha_rescision: date,
    autor: Usuario | None,
    ip: str | None,
) -> ContratoArrendamiento:
    """
    Regla 10: el inquilino se va antes de terminar.

    - El contrato VIGENTE pasa a RESCINDIDO con su fecha de rescisión, que va
      del inicio a hoy: registra algo que ya pasó.
    - Los pagos PENDIENTE que vencen después de esa fecha se cancelan; los
      anteriores se siguen debiendo.
    - El bien vuelve a DISPONIBLE.

    Si es una renovación que todavía no empieza, el inquilino se va durante el
    contrato anterior (RENOVADO): el límite inferior de la fecha es el inicio
    del anterior, y también se cancelan los pagos pendientes del anterior que
    vencen después de la fecha. Un RENOVADO no se rescinde por sí solo: se
    rescinde siempre el más nuevo.
    """
    contrato = ContratoArrendamiento.objects.select_for_update().get(pk=contrato.pk)
    if contrato.estado != EstadoArrendamiento.VIGENTE:
        raise ArrendamientoNoVigente(contrato=contrato.codigo, estado=contrato.estado)

    anterior = contrato.contrato_anterior
    desde = anterior.fecha_inicio if anterior else contrato.fecha_inicio
    hoy = timezone.localdate()
    if not (desde <= fecha_rescision <= hoy):
        raise FechaRescisionInvalida(fecha=fecha_rescision, desde=desde, hasta=hoy)

    cancelados = _cancelar_pagos_posteriores(contrato, fecha_rescision, autor)
    if anterior is not None:
        cancelados += _cancelar_pagos_posteriores(anterior, fecha_rescision, autor)

    _cambiar_estado_bien(
        propiedad=contrato.propiedad,
        unidad=contrato.unidad,
        estado=EstadoPropiedad.DISPONIBLE,
        requerido=EstadoPropiedad.ARRENDADA,
        motivo=f"Arrendamiento {contrato.codigo} rescindido",
        autor=autor,
        ip=ip,
    )
    contrato.fecha_rescision = fecha_rescision
    contrato.save(update_fields=["fecha_rescision"])
    return _cambiar_estado_contrato(
        contrato,
        EstadoArrendamiento.RESCINDIDO,
        AccionAuditoria.ANULAR,
        autor,
        ip,
        extra={"fecha_rescision": fecha_rescision, "pagos_cancelados": cancelados},
    )


@transaction.atomic
def finalizar_arrendamiento(
    *, contrato: ContratoArrendamiento, autor: Usuario | None, ip: str | None
) -> ContratoArrendamiento:
    """
    Regla 11: un contrato VIGENTE cuya fecha de fin ya pasó pasa a VENCIDO y
    el bien vuelve a DISPONIBLE. Los pagos pendientes se siguen debiendo.

    Es una acción y no una tarea diaria (sin Celery beat): mientras nadie lo
    finalice, la consulta muestra que su fecha de fin ya pasó.
    """
    contrato = ContratoArrendamiento.objects.select_for_update().get(pk=contrato.pk)
    if contrato.estado != EstadoArrendamiento.VIGENTE:
        raise ArrendamientoNoVigente(contrato=contrato.codigo, estado=contrato.estado)
    if contrato.fecha_fin >= timezone.localdate():
        raise ContratoNoTerminado(
            contrato=contrato.codigo, fecha_fin=contrato.fecha_fin
        )

    _cambiar_estado_bien(
        propiedad=contrato.propiedad,
        unidad=contrato.unidad,
        estado=EstadoPropiedad.DISPONIBLE,
        requerido=EstadoPropiedad.ARRENDADA,
        motivo=f"Arrendamiento {contrato.codigo} finalizado",
        autor=autor,
        ip=ip,
    )
    return _cambiar_estado_contrato(
        contrato, EstadoArrendamiento.VENCIDO, AccionAuditoria.ACTUALIZAR, autor, ip
    )


# ---------- Pagos ----------


@transaction.atomic
def registrar_pago_renta(
    *,
    pago: PagoRenta,
    fecha: date,
    monto: Decimal,
    referencia: str,
    autor: Usuario | None,
    ip: str | None,
) -> PagoRenta:
    """
    Registra el pago de un mes de renta (spec 008, reglas 6 y 7).

    - Se paga completo y una sola vez: el pago debe estar PENDIENTE.
    - Si llega después de la gracia, lleva el recargo fijo (calcular_recargo).
    - El monto recibido debe ser exactamente renta más recargo; si no, 400
      MONTO_INCORRECTO con el esperado, para que un error de digitación no
      quede como pago válido.
    - La fecha no puede ser futura, por la tasa al dólar (mismo criterio que
      en ventas). Se permite pagar por adelantado, antes del vencimiento.
    - Guarda la tasa al dólar de la fecha del pago.

    Los pagos de un contrato rescindido o vencido se siguen pudiendo pagar: son
    deuda (reglas 10 y 11). Los cancelados, no.

    La fila del pago se bloquea: dos registros simultáneos del mismo mes no
    pasan los dos.
    """
    pago = (
        PagoRenta.objects.select_for_update().select_related("contrato").get(pk=pago.pk)
    )
    if pago.estado != EstadoPagoRenta.PENDIENTE:
        raise PagoNoPendiente(estado=pago.estado)
    hoy = timezone.localdate()
    if fecha > hoy:
        raise FechaPagoRentaInvalida(fecha=fecha, hoy=hoy)

    contrato = pago.contrato
    recargo = calcular_recargo(
        renta=pago.monto,
        porcentaje=contrato.porcentaje_mora,
        vencimiento=pago.fecha_vencimiento,
        dias_gracia=contrato.dias_gracia,
        fecha_pago=fecha,
    )
    if monto != pago.monto + recargo:
        raise MontoIncorrecto(recibido=monto, renta=pago.monto, recargo=recargo)

    pago.estado = EstadoPagoRenta.PAGADO
    pago.fecha_pago = fecha
    pago.monto_pagado = monto
    pago.mora_aplicada = recargo
    pago.referencia_pago = referencia
    pago.tasa_a_usd = _tasa_a_dolar(moneda=contrato.moneda, fecha=fecha)
    pago.actualizado_por = autor
    pago.save()

    registrar_auditoria(
        usuario=autor,
        entidad=PagoRenta._meta.db_table,
        entidad_id=pago.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"estado": EstadoPagoRenta.PENDIENTE},
        valores_nuevos={
            "estado": pago.estado,
            "fecha_pago": fecha,
            "monto_pagado": monto,
            "mora_aplicada": recargo,
            "referencia_pago": referencia,
            "tasa_a_usd": pago.tasa_a_usd,
        },
        ip=ip,
    )
    return pago


# ---------- Apoyo ----------


def _crear_contrato(*, datos: dict, autor, anterior=None) -> ContratoArrendamiento:
    """Crea el contrato, su código y todos sus pagos de renta (reglas 3 a 5)."""
    cliente = datos["cliente"]
    inicio, meses = datos["fecha_inicio"], datos["duracion_meses"]
    contrato = ContratoArrendamiento.objects.create(
        cliente=cliente,
        agente=cliente.agente_asignado,
        propiedad=datos.get("propiedad"),
        unidad=datos.get("unidad"),
        fecha_inicio=inicio,
        duracion_meses=meses,
        fecha_fin=calcular_fecha_fin(inicio=inicio, duracion_meses=meses),
        renta_mensual=datos["renta_mensual"],
        moneda=datos["moneda"],
        tasa_a_usd=_tasa_a_dolar(moneda=datos["moneda"], fecha=timezone.localdate()),
        deposito=datos.get("deposito", Decimal("0")),
        dia_cobro=datos["dia_cobro"],
        dias_gracia=datos["dias_gracia"],
        porcentaje_mora=datos["porcentaje_mora"],
        contrato_anterior=anterior,
        creado_por=autor,
        actualizado_por=autor,
    )
    contrato.codigo = f"ARR-{contrato.pk:05d}"
    contrato.save(update_fields=["codigo"])

    PagoRenta.objects.bulk_create(
        PagoRenta(
            contrato=contrato,
            periodo_anio=vencimiento.year,
            periodo_mes=vencimiento.month,
            fecha_vencimiento=vencimiento,
            monto=contrato.renta_mensual,
            creado_por=autor,
            actualizado_por=autor,
        )
        for vencimiento in calcular_calendario(
            inicio=inicio, duracion_meses=meses, dia_cobro=contrato.dia_cobro
        )
    )
    return contrato


def _auditar_creacion(contrato, *, autor, ip) -> None:
    """CREAR con el número de pagos generados: no se auditan uno por uno (§7)."""
    registrar_auditoria(
        usuario=autor,
        entidad=ContratoArrendamiento._meta.db_table,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos={
            **model_to_dict(contrato, fields=CAMPOS_AUDITADOS),
            "pagos_generados": contrato.duracion_meses,
        },
        ip=ip,
    )


def _cancelar_pagos_posteriores(contrato, fecha: date, autor) -> int:
    """Regla 10: cancela los pagos pendientes que vencen después de la fecha."""
    return contrato.pagos.filter(
        estado=EstadoPagoRenta.PENDIENTE, fecha_vencimiento__gt=fecha
    ).update(
        estado=EstadoPagoRenta.CANCELADO,
        actualizado_por=autor,
        # auto_now solo actúa con save(); update() no pasa por ahí.
        actualizado_en=timezone.now(),
    )


def _cambiar_estado_contrato(contrato, estado, accion, autor, ip, extra=None):
    anterior = contrato.estado
    contrato.estado = estado
    contrato.actualizado_por = autor
    contrato.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ContratoArrendamiento._meta.db_table,
        entidad_id=contrato.pk,
        accion=accion,
        valores_anteriores={"estado": anterior},
        valores_nuevos={"estado": estado, **(extra or {})},
        ip=ip,
    )
    return contrato


def _tasa_a_dolar(*, moneda, fecha: date) -> Decimal:
    """Tasa de la moneda al dólar en la fecha; 1 si ya es dólar (spec 001)."""
    dolar = obtener_dolar()
    if dolar is None:
        raise TipoCambioNoDisponible(origen=moneda.codigo, destino="USD", fecha=fecha)
    return obtener_tipo_cambio(origen=moneda, destino=dolar, fecha=fecha)


def _cambiar_estado_bien(*, propiedad, unidad, estado, requerido, motivo, autor, ip):
    """Cambia el estado de la propiedad o la unidad con el servicio del catálogo."""
    if propiedad is not None:
        cambiar_estado_propiedad(
            propiedad=propiedad,
            estado=estado,
            autor=autor,
            ip=ip,
            motivo=motivo,
            estado_requerido=requerido,
        )
    else:
        cambiar_estado_unidad(
            unidad=unidad,
            estado=estado,
            autor=autor,
            ip=ip,
            motivo=motivo,
            estado_requerido=requerido,
        )


# ---------- Datos de demostración ----------


@transaction.atomic
def cargar_demo_arrendamientos() -> dict[str, int]:
    """
    Carga los contratos ficticios de datos_demo.py con sus pagos, y devuelve
    cuántos creó.

    Como la demo de ventas, usa los mismos servicios que la API para que cada
    contrato quede coherente (pagos generados, bien ARRENDADO, recargo y tasa),
    así que sus escrituras quedan en la bitácora con usuario nulo. Es
    idempotente: salta un bien que ya tiene un contrato, y si el bien ya no
    está disponible, se salta sin detener la carga (punto de guardado propio).
    """
    creados = {"contratos": 0}
    hoy = timezone.localdate()

    for datos in datos_demo.CONTRATOS:
        cliente = obtener_cliente_por_email(email=datos["cliente"])
        nombre, codigo_unidad = datos["bien"]
        if codigo_unidad is None:
            propiedad = listar_propiedades().filter(nombre=nombre).first()
            unidad = None
        else:
            propiedad = None
            unidad = (
                listar_unidades()
                .filter(propiedad__nombre=nombre, codigo=codigo_unidad)
                .first()
            )
        if cliente is None or (propiedad or unidad) is None:
            continue
        if ContratoArrendamiento.objects.filter(
            propiedad=propiedad, unidad=unidad
        ).exists():
            continue
        try:
            with transaction.atomic():
                bien = propiedad or unidad
                contrato = firmar_arrendamiento(
                    datos={
                        "cliente": cliente,
                        "propiedad": propiedad,
                        "unidad": unidad,
                        "fecha_inicio": hoy
                        - timedelta(days=datos["dias_desde_inicio"]),
                        "duracion_meses": datos["duracion_meses"],
                        "renta_mensual": datos["renta_mensual"],
                        "moneda": bien.moneda,
                        "deposito": datos["deposito"],
                        "dia_cobro": datos["dia_cobro"],
                        "dias_gracia": datos["dias_gracia"],
                        "porcentaje_mora": datos["porcentaje_mora"],
                    },
                    autor=None,
                    ip=None,
                )
                pagos = list(contrato.pagos.order_by("fecha_vencimiento"))
                for numero, dias_tarde in datos["pagos"]:
                    pago = pagos[numero - 1]
                    fecha = pago.fecha_vencimiento + timedelta(days=dias_tarde)
                    recargo = calcular_recargo(
                        renta=pago.monto,
                        porcentaje=contrato.porcentaje_mora,
                        vencimiento=pago.fecha_vencimiento,
                        dias_gracia=contrato.dias_gracia,
                        fecha_pago=fecha,
                    )
                    registrar_pago_renta(
                        pago=pago,
                        fecha=fecha,
                        monto=pago.monto + recargo,
                        referencia=f"DEMO-{contrato.codigo}-{numero}",
                        autor=None,
                        ip=None,
                    )
                creados["contratos"] += 1
        except ErrorDominio:
            continue
    return creados
