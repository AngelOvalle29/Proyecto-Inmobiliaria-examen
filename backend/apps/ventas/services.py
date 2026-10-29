"""Servicios de ventas: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.forms.models import model_to_dict

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.services import cambiar_estado_propiedad, cambiar_estado_unidad
from apps.core.exceptions import TipoCambioNoDisponible
from apps.core.fechas import sumar_meses
from apps.core.selectors import obtener_tipo_cambio
from apps.crm.enums import EstadoCotizacion
from apps.crm.exceptions import CotizacionYaContratada, SeVendePorUnidades
from apps.crm.selectors import cotizacion_tiene_contrato
from apps.usuarios.models import Usuario

from .enums import EstadoContrato, EstadoCuota, ModalidadVenta
from .exceptions import (
    ContratoConPagos,
    ContratoNoVigente,
    CotizacionNoAprobada,
    EngancheFueraDeRango,
    PagoExcedeSaldo,
)
from .models import ContratoVenta, CuotaPago
from .selectors import contrato_esta_pagado, contrato_tiene_pagos, obtener_dolar

CENTAVOS = Decimal("0.01")


def calcular_cuotas(
    *, saldo: Decimal, tasa_anual: Decimal, numero_cuotas: int, primera: date
) -> list[dict]:
    """
    Plan de cuotas fijas de una venta financiada (spec 007, regla 12; sistema
    francés, decidido por B).

    Todas las cuotas valen lo mismo. Con tasa mensual i = tasa anual / 12 / 100:

        cuota = saldo · i / (1 − (1 + i)^−n)        (con i = 0: saldo / n)

    En cada mes, el interés es lo que todavía se debe por i, y el capital es
    el resto de la cuota. Al principio se debe mucho, así que la cuota es casi
    todo interés; al final, casi todo capital.

    Cada monto se redondea a centavos con ROUND_HALF_UP, y la última cuota
    ajusta los centavos que el redondeo dejó: su capital es exactamente lo que
    falta, así el capital de todas las cuotas suma el saldo sin un centavo de
    diferencia.

    Es una función pura (no toca la base): recibe números y devuelve la lista,
    y se prueba sola. La cuota k vence en primera + k − 1 meses (core/fechas).
    """
    tasa_mensual = tasa_anual / Decimal(12) / Decimal(100)
    if tasa_mensual == 0:
        cuota = saldo / numero_cuotas
    else:
        cuota = saldo * tasa_mensual / (1 - (1 + tasa_mensual) ** -numero_cuotas)
    cuota = _a_centavos(cuota)

    cuotas = []
    pendiente = saldo
    for numero in range(1, numero_cuotas + 1):
        interes = _a_centavos(pendiente * tasa_mensual)
        if numero == numero_cuotas:
            capital = pendiente
        else:
            capital = cuota - interes
        cuotas.append(
            {
                "numero": numero,
                "fecha_vencimiento": sumar_meses(primera, numero - 1),
                "monto_capital": capital,
                "monto_interes": interes,
                "monto_total": capital + interes,
            }
        )
        pendiente -= capital
    return cuotas


def _a_centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


# ---------- Firma y anulación ----------

CAMPOS_CONTRATO_AUDITADOS = [
    "codigo",
    "cotizacion",
    "cliente",
    "agente",
    "propiedad",
    "unidad",
    "fecha_firma",
    "monto_total",
    "moneda",
    "tasa_a_usd",
    "monto_total_usd",
    "modalidad",
    "enganche",
    "numero_cuotas",
    "tasa_interes_anual",
    "fecha_primera_cuota",
    "comision_agente",
    "estado",
]


@transaction.atomic
def firmar_contrato(*, datos: dict, autor: Usuario, ip: str | None) -> ContratoVenta:
    """
    Firma un contrato de venta (spec 007, reglas 7 a 14).

    - Desde una cotización (regla 7): toma su cliente, bien, moneda y total.
      Debe estar APROBADA, sin otro contrato, y su bien RESERVADO (regla 8).
    - Sin cotización: el bien debe estar DISPONIBLE (regla 8).
    - Un edificio no se vende completo: se venden sus unidades (regla 9).
    - El bien pasa a VENDIDA (regla 10). El catálogo comprueba el estado
      requerido bajo el bloqueo de su fila, como al aprobar una cotización.
    - Contado: nace LIQUIDADO, sin cuotas. Financiado: genera sus cuotas fijas
      con calcular_cuotas (reglas 11 y 12).
    - Guarda la comisión del agente (regla 13) y la tasa al dólar de la fecha
      de firma, con el monto convertido (regla 14). Sin tasa, se rechaza.

    datos ya viene validado: cotización y cliente visibles para el autor
    (cartera), y los datos del plan en rango si es financiado.
    """
    cotizacion = datos.get("cotizacion")
    if cotizacion is not None:
        if cotizacion.estado != EstadoCotizacion.APROBADA:
            raise CotizacionNoAprobada(
                cotizacion=cotizacion.codigo, estado=cotizacion.estado
            )
        if cotizacion_tiene_contrato(cotizacion=cotizacion):
            raise CotizacionYaContratada(cotizacion=cotizacion.codigo)
        cliente = cotizacion.cliente
        propiedad, unidad = cotizacion.propiedad, cotizacion.unidad
        monto_total, moneda = cotizacion.total, cotizacion.moneda
        estado_requerido = EstadoPropiedad.RESERVADA
    else:
        cliente = datos["cliente"]
        propiedad, unidad = datos.get("propiedad"), datos.get("unidad")
        monto_total, moneda = datos["monto_total"], datos["moneda"]
        estado_requerido = EstadoPropiedad.DISPONIBLE

    if propiedad is not None and propiedad.tipo.requiere_unidades:
        raise SeVendePorUnidades(propiedad=propiedad.codigo)

    financiado = datos["modalidad"] == ModalidadVenta.FINANCIADO
    enganche = datos.get("enganche", Decimal("0")) if financiado else Decimal("0")
    if not (0 <= enganche < monto_total):
        raise EngancheFueraDeRango()

    fecha_firma = datos["fecha_firma"]
    tasa_a_usd = _tasa_a_dolar(moneda=moneda, fecha=fecha_firma)
    agente = cliente.agente_asignado
    codigo_bien = (propiedad or unidad).codigo

    _cambiar_estado_bien(
        propiedad=propiedad,
        unidad=unidad,
        estado=EstadoPropiedad.VENDIDA,
        requerido=estado_requerido,
        motivo=f"Venta a {cliente.codigo}",
        autor=autor,
        ip=ip,
    )

    contrato = ContratoVenta.objects.create(
        cotizacion=cotizacion,
        cliente=cliente,
        agente=agente,
        propiedad=propiedad,
        unidad=unidad,
        fecha_firma=fecha_firma,
        monto_total=monto_total,
        moneda=moneda,
        tasa_a_usd=tasa_a_usd,
        monto_total_usd=_a_centavos(monto_total * tasa_a_usd),
        modalidad=datos["modalidad"],
        enganche=enganche,
        numero_cuotas=datos.get("numero_cuotas") if financiado else None,
        tasa_interes_anual=datos.get("tasa_interes_anual") if financiado else None,
        fecha_primera_cuota=datos.get("fecha_primera_cuota") if financiado else None,
        comision_agente=_a_centavos(monto_total * agente.porcentaje_comision / 100),
        estado=EstadoContrato.VIGENTE if financiado else EstadoContrato.LIQUIDADO,
        observaciones=datos.get("observaciones", ""),
        creado_por=autor,
        actualizado_por=autor,
    )
    contrato.codigo = f"CV-{contrato.pk:05d}"
    contrato.save(update_fields=["codigo"])

    cuotas = []
    if financiado:
        cuotas = calcular_cuotas(
            saldo=monto_total - enganche,
            tasa_anual=contrato.tasa_interes_anual,
            numero_cuotas=contrato.numero_cuotas,
            primera=contrato.fecha_primera_cuota,
        )
        CuotaPago.objects.bulk_create(
            CuotaPago(contrato=contrato, creado_por=autor, actualizado_por=autor, **c)
            for c in cuotas
        )

    # Las cuotas no se auditan una por una (spec 007, §7): el registro del
    # contrato dice cuántas se generaron, y se pueden recalcular.
    registrar_auditoria(
        usuario=autor,
        entidad=ContratoVenta._meta.db_table,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos={
            **model_to_dict(contrato, fields=CAMPOS_CONTRATO_AUDITADOS),
            "bien": codigo_bien,
            "cuotas_generadas": len(cuotas),
        },
        ip=ip,
    )
    return contrato


@transaction.atomic
def anular_contrato(
    *, contrato: ContratoVenta, autor: Usuario, ip: str | None
) -> ContratoVenta:
    """
    Regla 15: un contrato VIGENTE sin ningún pago pasa a ANULADO y su bien
    vuelve a DISPONIBLE. Conserva sus registros: no se borra nada.

    Con pagos no se anula, porque habría que devolver dinero, y esa regla no
    está en el alcance. Un contrato de contado nace LIQUIDADO (ya pagado), así
    que tampoco se anula.
    """
    contrato = ContratoVenta.objects.select_for_update().get(pk=contrato.pk)
    if contrato.estado != EstadoContrato.VIGENTE:
        raise ContratoNoVigente(contrato=contrato.codigo, estado=contrato.estado)
    if contrato_tiene_pagos(contrato=contrato):
        raise ContratoConPagos(contrato=contrato.codigo)

    _cambiar_estado_bien(
        propiedad=contrato.propiedad,
        unidad=contrato.unidad,
        estado=EstadoPropiedad.DISPONIBLE,
        requerido=EstadoPropiedad.VENDIDA,
        motivo=f"Contrato {contrato.codigo} anulado",
        autor=autor,
        ip=ip,
    )
    contrato.estado = EstadoContrato.ANULADO
    contrato.actualizado_por = autor
    contrato.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ContratoVenta._meta.db_table,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.ANULAR,
        valores_anteriores={"estado": EstadoContrato.VIGENTE},
        valores_nuevos={"estado": EstadoContrato.ANULADO},
        ip=ip,
    )
    return contrato


# ---------- Pagos de cuotas ----------


@transaction.atomic
def registrar_pago_cuota(
    *,
    cuota: CuotaPago,
    monto: Decimal,
    fecha: date,
    referencia: str,
    autor: Usuario,
    ip: str | None,
) -> CuotaPago:
    """
    Registra un pago, total o parcial, de una cuota (spec 007, reglas 14 y
    16 a 18).

    - Solo en un contrato VIGENTE, y nunca por más de lo que falta de la cuota.
    - La cuota queda PARCIAL hasta completar su total, y entonces PAGADA.
    - Guarda la tasa al dólar de la fecha del pago (regla 14).
    - Si con este pago todas las cuotas quedan pagadas, el contrato pasa a
      LIQUIDADO (regla 18).

    Bloquea primero el contrato y después la cuota, siempre en ese orden: dos
    pagos simultáneos del mismo contrato se ordenan, y el segundo ve el saldo
    que dejó el primero.
    """
    contrato = ContratoVenta.objects.select_for_update().get(pk=cuota.contrato_id)
    cuota = CuotaPago.objects.select_for_update().get(pk=cuota.pk)
    if contrato.estado != EstadoContrato.VIGENTE:
        raise ContratoNoVigente(contrato=contrato.codigo, estado=contrato.estado)
    if monto > cuota.saldo:
        raise PagoExcedeSaldo(cuota=cuota.numero, saldo=cuota.saldo, monto=monto)

    tasa = _tasa_a_dolar(moneda=contrato.moneda, fecha=fecha)
    antes = {"monto_pagado": cuota.monto_pagado, "estado": cuota.estado}

    cuota.monto_pagado += monto
    cuota.estado = (
        EstadoCuota.PAGADA
        if cuota.monto_pagado == cuota.monto_total
        else EstadoCuota.PARCIAL
    )
    cuota.fecha_ultimo_pago = fecha
    cuota.referencia_ultimo_pago = referencia
    cuota.tasa_a_usd_ultimo_pago = tasa
    cuota.actualizado_por = autor
    cuota.save()

    # La historia de los pagos parciales vive en la bitácora: cada pago deja
    # su monto, fecha, referencia y tasa, y el acumulado antes y después.
    registrar_auditoria(
        usuario=autor,
        entidad=CuotaPago._meta.db_table,
        entidad_id=cuota.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores=antes,
        valores_nuevos={
            "monto_pagado": cuota.monto_pagado,
            "estado": cuota.estado,
            "pago": monto,
            "fecha": fecha,
            "referencia": referencia,
            "tasa_a_usd": tasa,
        },
        ip=ip,
    )

    if cuota.estado == EstadoCuota.PAGADA and contrato_esta_pagado(contrato=contrato):
        contrato.estado = EstadoContrato.LIQUIDADO
        contrato.actualizado_por = autor
        contrato.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ContratoVenta._meta.db_table,
            entidad_id=contrato.pk,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores={"estado": EstadoContrato.VIGENTE},
            valores_nuevos={"estado": EstadoContrato.LIQUIDADO},
            ip=ip,
        )
    return cuota


# ---------- Apoyo ----------


def _tasa_a_dolar(*, moneda, fecha: date) -> Decimal:
    """
    Tasa de la moneda al dólar vigente en la fecha (regla 14). Para un
    contrato en dólares es 1 (regla 7 de la spec 001). Sin tasa registrada, o
    sin el dólar en el catálogo, se rechaza con TIPO_CAMBIO_NO_DISPONIBLE.
    """
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
