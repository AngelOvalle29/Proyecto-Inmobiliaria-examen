"""
Reportes comerciales de la spec 021: R01, R02, R03, R04, R10 y R11.

Van aparte de selectors.py porque cada integrante agrega los reportes de sus
datos. Todos parten de los selectores de crm, ventas y arrendamientos, que ya
aplican la cartera por cliente (regla 6): así el detalle y los totales nunca
incluyen clientes ajenos. Cada reporte son dos funciones: una que agrega todo
el filtro y otra que trae solo las filas de la página.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, Concat, TruncMonth
from django.utils import timezone

from apps.arrendamientos.enums import EstadoArrendamiento, EstadoPagoRenta
from apps.arrendamientos.models import ContratoArrendamiento, PagoRenta
from apps.arrendamientos.selectors import listar_pagos_renta_visibles
from apps.crm.enums import EstadoCotizacion, TipoCliente
from apps.crm.models import Agente
from apps.crm.selectors import (
    listar_clientes_visibles,
    listar_cotizaciones_visibles,
    obtener_agente_de_usuario,
)
from apps.usuarios.enums import NombreRol
from apps.ventas.enums import EstadoContrato, EstadoCuota, ModalidadVenta
from apps.ventas.models import ContratoVenta, CuotaPago
from apps.ventas.selectors import listar_contratos_visibles, listar_cuotas_visibles

from .estructuras import (
    FiltrosAgentes,
    FiltrosClientes,
    FiltrosCotizaciones,
    FiltrosEstadoCuenta,
    FiltrosMorosidad,
    FiltrosVentas,
    Grupo,
    ResumenReporte,
)

GUATEMALA = ZoneInfo("America/Guatemala")
CENTAVOS = Decimal("0.01")
MONTO = DecimalField(max_digits=18, decimal_places=2)
TRAMOS = ("1 a 30 días", "31 a 60 días", "61 a 90 días", "Más de 90 días")


def _hoy() -> date:
    return timezone.localdate(timezone=GUATEMALA)


def _filtrar(consulta: QuerySet, condiciones: dict) -> QuerySet:
    """Aplica solo los filtros que el usuario indicó."""
    return consulta.filter(
        **{campo: valor for campo, valor in condiciones.items() if valor is not None}
    )


def _nombre_cliente(prefijo: str = "cliente__") -> Case:
    """Cliente.nombre_mostrado en SQL, para ordenar y agrupar sin cargar filas."""
    return Case(
        When(
            **{prefijo + "tipo": TipoCliente.EMPRESA},
            then=F(prefijo + "razon_social"),
        ),
        default=Concat(F(prefijo + "nombre"), Value(" "), F(prefijo + "apellidos")),
        output_field=CharField(),
    )


def _datos_bien(prefijo: str = "") -> dict:
    """Un contrato o cotización apunta a una propiedad o a una unidad: los datos
    geográficos salen de la propiedad, o del edificio de la unidad."""

    def de_la_propiedad(campo: str) -> Coalesce:
        return Coalesce(
            F(f"{prefijo}propiedad__{campo}"),
            F(f"{prefijo}unidad__propiedad__{campo}"),
        )

    return {
        "bien_codigo": Coalesce(
            F(f"{prefijo}unidad__codigo"), F(f"{prefijo}propiedad__codigo")
        ),
        "pais_id_bien": de_la_propiedad("ciudad__pais_id"),
        "ciudad_id_bien": de_la_propiedad("ciudad_id"),
        "tipo_id_bien": de_la_propiedad("tipo_id"),
        "pais_bien": de_la_propiedad("ciudad__pais__nombre"),
        "ciudad_bien": de_la_propiedad("ciudad__nombre"),
    }


def _porcentaje(parte: int, total: int) -> Decimal | None:
    """Regla 9: con denominador cero no hay tasa, no es cero."""
    if not total:
        return None
    return (Decimal(parte) * 100 / Decimal(total)).quantize(
        CENTAVOS, rounding=ROUND_HALF_UP
    )


def _subconsulta(consulta: QuerySet, agrupar: str, total) -> Coalesce:
    """
    Un total por fila en su propia subconsulta. Regla 4: con varios join, cada
    cotización se multiplicaría por cada contrato y los totales saldrían mal.
    """
    return Coalesce(
        Subquery(
            consulta.order_by().values(agrupar).annotate(t=total).values("t")[:1],
        ),
        Value(0),
        output_field=MONTO,
    )


# ---------- R01 · Ventas por período ----------


def _ventas(filtros: FiltrosVentas, usuario: AbstractBaseUser) -> QuerySet:
    """Regla 5: un contrato anulado no es una venta."""
    consulta = (
        listar_contratos_visibles(usuario=usuario)
        .prefetch_related(None)
        .exclude(estado=EstadoContrato.ANULADO)
        .annotate(**_datos_bien())
    )
    return _filtrar(
        consulta,
        {
            "fecha_firma__gte": filtros.fecha_desde,
            "fecha_firma__lte": filtros.fecha_hasta,
            "pais_id_bien": filtros.pais,
            "ciudad_id_bien": filtros.ciudad,
            "tipo_id_bien": filtros.tipo,
            "agente_id": filtros.agente,
            "modalidad": filtros.modalidad,
            "moneda__codigo": filtros.moneda,
        },
    ).order_by("-fecha_firma", "-id")


def resumir_ventas(
    *, filtros: FiltrosVentas, usuario: AbstractBaseUser
) -> ResumenReporte:
    """
    Totales por moneda: no se suman monedas distintas (regla 3). Bruto y
    descuento solo existen si hubo cotización (regla 8): se informa cuántas
    ventas cubren, para no presentar un descuento desconocido como cero.
    """
    consulta = _ventas(filtros, usuario).order_by()
    por_moneda = {}
    cantidad = cobertura = 0
    for fila in (
        consulta.values(moneda_codigo=F("moneda__codigo"))
        .annotate(
            cantidad=Count("id"),
            con_cotizacion=Count("cotizacion"),
            neto=Sum("monto_total"),
            comision=Sum("comision_agente"),
            bruto=Sum("cotizacion__precio"),
            descuento=Sum("cotizacion__descuento"),
        )
        .order_by("moneda_codigo")
    ):
        moneda = fila.pop("moneda_codigo")
        cantidad += fila["cantidad"]
        cobertura += fila["con_cotizacion"]
        por_moneda[moneda] = fila
    grupos = (
        consulta.annotate(mes=TruncMonth("fecha_firma"))
        .values("mes", "pais_bien", moneda_codigo=F("moneda__codigo"))
        .annotate(
            cantidad=Count("id"),
            neto=Sum("monto_total"),
            comision=Sum("comision_agente"),
        )
        .order_by("mes", "pais_bien", "moneda_codigo")
    )
    return ResumenReporte(
        cantidad,
        dict(cantidad=cantidad, con_cotizacion=cobertura, por_moneda=por_moneda),
        [
            Grupo(
                f"{g['mes']:%Y-%m} / {g['pais_bien']} / {g['moneda_codigo']}",
                dict(cantidad=g["cantidad"], neto=g["neto"], comision=g["comision"]),
            )
            for g in grupos
        ],
    )


def seleccionar_ventas(
    *, filtros: FiltrosVentas, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    """Bruto y descuento quedan en None sin cotización (regla 8)."""
    filas = list(
        _ventas(filtros, usuario).values(
            "codigo",
            "fecha_firma",
            "modalidad",
            "monto_total",
            "comision_agente",
            cliente_nombre=_nombre_cliente(),
            agente_nombre=F("agente__usuario__nombre_completo"),
            bien=F("bien_codigo"),
            pais=F("pais_bien"),
            ciudad=F("ciudad_bien"),
            moneda_codigo=F("moneda__codigo"),
            bruto=F("cotizacion__precio"),
            descuento=F("cotizacion__descuento"),
        )[offset : offset + limite]
    )
    for fila in filas:
        fila["modalidad"] = ModalidadVenta(fila["modalidad"]).label
    return filas


# ---------- R02 · Desempeño por agente ----------


def _agentes(filtros: FiltrosAgentes, usuario: AbstractBaseUser) -> QuerySet:
    """
    Regla 9: la cohorte son las cotizaciones emitidas en el período, sin
    borradores; las ventas se cuentan por fecha de firma. Regla 6: un agente ve
    solo su propia fila, y los conteos respetan la cartera por cliente.
    """
    cotizaciones = _filtrar(
        listar_cotizaciones_visibles(usuario=usuario).filter(agente=OuterRef("pk")),
        {
            "fecha_emision__gte": filtros.fecha_desde,
            "fecha_emision__lte": filtros.fecha_hasta,
        },
    ).exclude(estado=EstadoCotizacion.BORRADOR)
    vinculadas = cotizaciones.filter(contrato_venta__isnull=False).exclude(
        contrato_venta__estado=EstadoContrato.ANULADO
    )
    ventas = _filtrar(
        listar_contratos_visibles(usuario=usuario)
        .prefetch_related(None)
        .filter(agente=OuterRef("pk"))
        .exclude(estado=EstadoContrato.ANULADO),
        {
            "fecha_firma__gte": filtros.fecha_desde,
            "fecha_firma__lte": filtros.fecha_hasta,
        },
    )
    agentes = Agente.objects.filter(activo=True)
    if usuario.rol.nombre == NombreRol.AGENTE:
        propio = obtener_agente_de_usuario(usuario=usuario)
        agentes = agentes.filter(pk=propio.pk if propio else None)
    contar = Count("id")
    return _filtrar(
        agentes, {"usuario__pais_id": filtros.pais, "pk": filtros.agente}
    ).annotate(
        emitidas=_subconsulta(cotizaciones, "agente", contar),
        aprobadas=_subconsulta(
            cotizaciones.filter(estado=EstadoCotizacion.APROBADA), "agente", contar
        ),
        vinculadas=_subconsulta(vinculadas, "agente", contar),
        ventas_directas=_subconsulta(
            ventas.filter(cotizacion__isnull=True), "agente", contar
        ),
        vendido_usd=_subconsulta(ventas, "agente", Sum("monto_total_usd")),
        comision_usd=_subconsulta(
            ventas,
            "agente",
            Sum(F("comision_agente") * F("tasa_a_usd"), output_field=MONTO),
        ),
    )


def resumir_agentes(
    *, filtros: FiltrosAgentes, usuario: AbstractBaseUser
) -> ResumenReporte:
    """La conversión global se pondera: no es el promedio de los porcentajes."""
    # Se suma aquí y no con aggregate(): PostgreSQL no agrega sobre columnas que
    # son subconsultas. Son pocas filas: una por agente.
    campos = (
        "emitidas",
        "aprobadas",
        "vinculadas",
        "ventas_directas",
        "vendido_usd",
        "comision_usd",
    )
    agentes = list(_agentes(filtros, usuario).values(*campos))
    suma = {campo: sum(a[campo] for a in agentes) for campo in campos}
    return ResumenReporte(
        len(agentes),
        dict(
            agentes=len(agentes),
            emitidas=int(suma["emitidas"]),
            aprobadas=int(suma["aprobadas"]),
            vinculadas=int(suma["vinculadas"]),
            ventas_directas=int(suma["ventas_directas"]),
            conversion_pct=_porcentaje(suma["vinculadas"], suma["emitidas"]),
            vendido_usd=Decimal(suma["vendido_usd"]).quantize(CENTAVOS),
            comision_usd=Decimal(suma["comision_usd"]).quantize(
                CENTAVOS, rounding=ROUND_HALF_UP
            ),
        ),
    )


def seleccionar_agentes(
    *, filtros: FiltrosAgentes, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    filas = list(
        _agentes(filtros, usuario)
        .order_by("codigo", "id")
        .values(
            "codigo",
            "emitidas",
            "aprobadas",
            "vinculadas",
            "ventas_directas",
            "vendido_usd",
            "comision_usd",
            nombre=F("usuario__nombre_completo"),
        )[offset : offset + limite]
    )
    for fila in filas:
        for campo in ("emitidas", "aprobadas", "vinculadas", "ventas_directas"):
            fila[campo] = int(fila[campo])
        fila["conversion_pct"] = _porcentaje(fila["vinculadas"], fila["emitidas"])
        fila["comision_usd"] = fila["comision_usd"].quantize(
            CENTAVOS, rounding=ROUND_HALF_UP
        )
    return filas


# ---------- R03 · Embudo de cotizaciones ----------


def _cotizaciones(filtros: FiltrosCotizaciones, usuario: AbstractBaseUser) -> QuerySet:
    consulta = listar_cotizaciones_visibles(usuario=usuario).annotate(**_datos_bien())
    return _filtrar(
        consulta,
        {
            "fecha_emision__gte": filtros.fecha_desde,
            "fecha_emision__lte": filtros.fecha_hasta,
            "agente_id": filtros.agente,
            "pais_id_bien": filtros.pais,
            "estado": filtros.estado,
            "moneda__codigo": filtros.moneda,
            "total__gte": filtros.monto_min,
            "total__lte": filtros.monto_max,
        },
    ).order_by("-fecha_emision", "-id")


def resumir_cotizaciones(
    *, filtros: FiltrosCotizaciones, usuario: AbstractBaseUser
) -> ResumenReporte:
    """
    Conteos por estado y conversión de la cohorte (regla 9). Los borradores se
    muestran como primera etapa, pero nunca llegaron al cliente: la aprobación
    se mide sobre las demás. Los estados son los actuales, no el recorrido.
    """
    consulta = _cotizaciones(filtros, usuario).order_by()
    por_estado = {estado: 0 for estado in EstadoCotizacion.values}
    grupos = []
    for fila in (
        consulta.values("estado", moneda_codigo=F("moneda__codigo"))
        .annotate(cantidad=Count("id"), total_cotizado=Sum("total"))
        .order_by("estado", "moneda_codigo")
    ):
        por_estado[fila["estado"]] += fila["cantidad"]
        grupos.append(
            Grupo(
                f"{EstadoCotizacion(fila['estado']).label} / {fila['moneda_codigo']}",
                dict(cantidad=fila["cantidad"], total=fila["total_cotizado"]),
            )
        )
    cantidad = sum(por_estado.values())
    vinculadas = (
        consulta.filter(contrato_venta__isnull=False)
        .exclude(contrato_venta__estado=EstadoContrato.ANULADO)
        .count()
    )
    enviadas = cantidad - por_estado[EstadoCotizacion.BORRADOR]
    return ResumenReporte(
        cantidad,
        dict(
            cantidad=cantidad,
            por_estado={
                EstadoCotizacion(estado).label: valor
                for estado, valor in por_estado.items()
            },
            con_contrato=vinculadas,
            conversion_pct=_porcentaje(vinculadas, cantidad),
            aprobacion_pct=_porcentaje(por_estado[EstadoCotizacion.APROBADA], enviadas),
        ),
        grupos,
    )


def seleccionar_cotizaciones(
    *, filtros: FiltrosCotizaciones, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    """Vencida se calcula igual que Cotizacion.esta_vencida (spec 007, regla 4)."""
    hoy = _hoy()
    filas = list(
        _cotizaciones(filtros, usuario).values(
            "codigo",
            "fecha_emision",
            "fecha_vencimiento",
            "estado",
            "total",
            cliente_nombre=_nombre_cliente(),
            agente_nombre=F("agente__usuario__nombre_completo"),
            moneda_codigo=F("moneda__codigo"),
            contrato=Case(
                When(
                    Q(contrato_venta__isnull=False)
                    & ~Q(contrato_venta__estado=EstadoContrato.ANULADO),
                    then=F("contrato_venta__codigo"),
                ),
                default=Value(None),
                output_field=CharField(),
            ),
        )[offset : offset + limite]
    )
    for fila in filas:
        sin_decidir = fila["estado"] in (
            EstadoCotizacion.BORRADOR,
            EstadoCotizacion.ENVIADA,
        )
        vencimiento = fila.pop("fecha_vencimiento")
        fila["vencida"] = "Sí" if sin_decidir and vencimiento < hoy else "No"
        fila["estado"] = EstadoCotizacion(fila["estado"]).label
    return filas


# ---------- R04 · Ranking de clientes ----------


def _ventas_de_clientes(filtros: FiltrosClientes) -> QuerySet:
    return _filtrar(
        ContratoVenta.objects.filter(activo=True).exclude(
            estado=EstadoContrato.ANULADO
        ),
        {
            "fecha_firma__gte": filtros.fecha_desde,
            "fecha_firma__lte": filtros.fecha_hasta,
        },
    )


def _arrendamientos_vigentes() -> QuerySet:
    return ContratoArrendamiento.objects.filter(
        activo=True, estado=EstadoArrendamiento.VIGENTE
    )


def _clientes(filtros: FiltrosClientes, usuario: AbstractBaseUser) -> QuerySet:
    """
    Regla 11: el ranking es por ventas en USD, sin mezclar rentas. El período
    filtra ventas; los arrendamientos vigentes y los saldos son los actuales.
    """
    ventas = _ventas_de_clientes(filtros).filter(cliente=OuterRef("pk"))
    arrendamientos = _arrendamientos_vigentes().filter(cliente=OuterRef("pk"))
    contar = Count("id")
    return (
        _filtrar(
            listar_clientes_visibles(usuario=usuario),
            {"pais_id": filtros.pais, "tipo": filtros.tipo},
        )
        .annotate(
            contratos=_subconsulta(ventas, "cliente", contar),
            arrendamientos_vigentes=_subconsulta(arrendamientos, "cliente", contar),
            vendido_usd=_subconsulta(ventas, "cliente", Sum("monto_total_usd")),
        )
        .filter(Q(contratos__gt=0) | Q(arrendamientos_vigentes__gt=0))
        .order_by("-vendido_usd", "id")
    )


def _saldos_por_cliente(clientes: QuerySet) -> dict[int, dict[str, Decimal]]:
    """
    Regla 14: cuotas de contratos vigentes, también las futuras, porque esa
    deuda se firmó; rentas solo vencidas, porque un mes futuro aún no se debe.
    """
    saldos = defaultdict(lambda: defaultdict(lambda: Decimal("0.00")))
    cuotas = (
        CuotaPago.objects.filter(
            contrato__cliente__in=clientes,
            contrato__activo=True,
            contrato__estado=EstadoContrato.VIGENTE,
        )
        .values("contrato__cliente_id", "contrato__moneda__codigo")
        .annotate(saldo=Sum(F("monto_total") - F("monto_pagado")))
    )
    rentas = (
        PagoRenta.objects.filter(
            contrato__cliente__in=clientes,
            contrato__activo=True,
            estado=EstadoPagoRenta.PENDIENTE,
            fecha_vencimiento__lt=_hoy(),
        )
        .values("contrato__cliente_id", "contrato__moneda__codigo")
        .annotate(saldo=Sum("monto"))
    )
    for fila in [*cuotas, *rentas]:
        cliente, moneda = fila["contrato__cliente_id"], fila["contrato__moneda__codigo"]
        saldos[cliente][moneda] += fila["saldo"]
    return saldos


def resumir_clientes(
    *, filtros: FiltrosClientes, usuario: AbstractBaseUser
) -> ResumenReporte:
    """
    Los totales se calculan sobre los contratos de la población, no sobre sus
    columnas: PostgreSQL no agrega sobre columnas que son subconsultas.
    """
    consulta = _clientes(filtros, usuario)
    poblacion = consulta.order_by().values("pk")
    ventas = _ventas_de_clientes(filtros).filter(cliente__in=poblacion)
    cantidad = consulta.count()
    saldos = defaultdict(lambda: Decimal("0.00"))
    for por_moneda in _saldos_por_cliente(poblacion).values():
        for moneda, saldo in por_moneda.items():
            saldos[moneda] += saldo
    return ResumenReporte(
        cantidad,
        dict(
            cantidad=cantidad,
            contratos=ventas.count(),
            arrendamientos_vigentes=_arrendamientos_vigentes()
            .filter(cliente__in=poblacion)
            .count(),
            vendido_usd=ventas.aggregate(t=Sum("monto_total_usd"))["t"]
            or Decimal("0.00"),
            saldos_actuales=dict(sorted(saldos.items())),
        ),
    )


def seleccionar_clientes(
    *, filtros: FiltrosClientes, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    """Los saldos van en texto por moneda: una columna no suma monedas distintas."""
    filas = list(
        _clientes(filtros, usuario).values(
            "id",
            "codigo",
            "contratos",
            "arrendamientos_vigentes",
            "vendido_usd",
            cliente_nombre=_nombre_cliente(prefijo=""),
        )[offset : offset + limite]
    )
    saldos = _saldos_por_cliente([fila["id"] for fila in filas])
    for fila in filas:
        fila["contratos"] = int(fila["contratos"])
        fila["arrendamientos_vigentes"] = int(fila["arrendamientos_vigentes"])
        fila["saldos"] = "; ".join(
            f"{moneda} {saldo:,.2f}"
            for moneda, saldo in sorted(saldos[fila["id"]].items())
            if saldo
        )
    return filas


# ---------- R10 · Estado de cuenta y R11 · Morosidad ----------


def _campos_obligacion(origen: str) -> dict:
    """Las columnas comunes de una cuota y una renta, para unirlas (union)."""
    return dict(
        origen=Value(origen, output_field=CharField()),
        cliente_id_reporte=F("contrato__cliente_id"),
        cliente_nombre=_nombre_cliente("contrato__cliente__"),
        contrato_codigo=F("contrato__codigo"),
        agente_nombre=F("contrato__agente__usuario__nombre_completo"),
        moneda_codigo=F("contrato__moneda__codigo"),
    )


def _fuentes_morosidad(
    filtros: FiltrosMorosidad, usuario: AbstractBaseUser
) -> tuple[QuerySet, QuerySet]:
    """
    Regla 14: solo lo vencido. Cuotas de contratos vigentes, porque un filtro
    en SQL no pasa por CuotaPago.en_mora (#70). Rentas pendientes también de un
    contrato terminado: se siguen debiendo (regla 5).
    """
    hoy = _hoy()
    cuotas = (
        listar_cuotas_visibles(usuario=usuario)
        .filter(contrato__estado=EstadoContrato.VIGENTE, fecha_vencimiento__lt=hoy)
        .exclude(estado=EstadoCuota.PAGADA)
        .annotate(saldo=F("monto_total") - F("monto_pagado"))
    )
    rentas = (
        listar_pagos_renta_visibles(usuario=usuario)
        .filter(estado=EstadoPagoRenta.PENDIENTE, fecha_vencimiento__lt=hoy)
        .annotate(saldo=F("monto"))
    )
    return tuple(
        _filtrar(
            consulta.annotate(**_datos_bien("contrato__")),
            {
                "pais_id_bien": filtros.pais,
                "contrato__agente_id": filtros.agente,
                "contrato__moneda__codigo": filtros.moneda,
                "saldo__gte": filtros.saldo_min,
                "saldo__lte": filtros.saldo_max,
            },
        ).order_by()
        for consulta in (cuotas, rentas)
    )


def _tramo_sql(hoy: date) -> Case:
    return Case(
        When(fecha_vencimiento__gte=hoy - timedelta(days=30), then=Value(TRAMOS[0])),
        When(fecha_vencimiento__gte=hoy - timedelta(days=60), then=Value(TRAMOS[1])),
        When(fecha_vencimiento__gte=hoy - timedelta(days=90), then=Value(TRAMOS[2])),
        default=Value(TRAMOS[3]),
        output_field=CharField(),
    )


def _tramo(dias: int) -> str:
    """Debe coincidir con _tramo_sql: una trae el detalle y la otra los totales."""
    if dias <= 30:
        return TRAMOS[0]
    if dias <= 60:
        return TRAMOS[1]
    return TRAMOS[2] if dias <= 90 else TRAMOS[3]


def resumir_morosidad(
    *, filtros: FiltrosMorosidad, usuario: AbstractBaseUser
) -> ResumenReporte:
    """Conteo y saldo por tramo y moneda: no se suman monedas distintas."""
    tramos = {
        tramo: dict(cantidad=0, saldo_por_moneda=defaultdict(Decimal))
        for tramo in TRAMOS
    }
    for consulta in _fuentes_morosidad(filtros, usuario):
        for fila in (
            consulta.annotate(tramo=_tramo_sql(_hoy()))
            .values("tramo", moneda_codigo=F("contrato__moneda__codigo"))
            .annotate(cantidad=Count("id"), total=Sum("saldo"))
        ):
            tramo = tramos[fila["tramo"]]
            tramo["cantidad"] += fila["cantidad"]
            tramo["saldo_por_moneda"][fila["moneda_codigo"]] += fila["total"]
    cantidad = sum(tramo["cantidad"] for tramo in tramos.values())
    return ResumenReporte(
        cantidad,
        dict(cantidad=cantidad),
        [
            Grupo(
                nombre,
                dict(
                    cantidad=tramo["cantidad"],
                    saldo_por_moneda=dict(sorted(tramo["saldo_por_moneda"].items())),
                ),
            )
            for nombre, tramo in tramos.items()
        ],
    )


def seleccionar_morosidad(
    *, filtros: FiltrosMorosidad, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    """UNION ALL con LIMIT en SQL: cuotas y rentas se paginan como una lista."""
    cuotas, rentas = _fuentes_morosidad(filtros, usuario)
    proyecciones = [
        consulta.values(
            "id", "fecha_vencimiento", "saldo", **_campos_obligacion(origen)
        )
        for consulta, origen in ((cuotas, "Cuota"), (rentas, "Renta"))
    ]
    filas = list(
        proyecciones[0]
        .union(proyecciones[1], all=True)
        .order_by("fecha_vencimiento", "origen", "id")[offset : offset + limite]
    )
    hoy = _hoy()
    for fila in filas:
        fila["dias_atraso"] = (hoy - fila["fecha_vencimiento"]).days
        fila["tramo"] = _tramo(fila["dias_atraso"])
    return filas


def _fuentes_estado_cuenta(
    filtros: FiltrosEstadoCuenta, usuario: AbstractBaseUser
) -> tuple[QuerySet, QuerySet]:
    """
    Regla 14. Cuotas: todas las de contratos no anulados, también las futuras.
    Rentas: las pagadas y las pendientes ya vencidas; un mes futuro todavía no
    es una obligación, y uno cancelado ya no. Lo pagado de una renta incluye el
    recargo, así que lo exigible también: se pide una sola vez.
    """
    hoy = _hoy()
    cuotas = (
        listar_cuotas_visibles(usuario=usuario)
        .exclude(contrato__estado=EstadoContrato.ANULADO)
        .annotate(
            exigible=F("monto_total"),
            pagado=F("monto_pagado"),
            saldo=F("monto_total") - F("monto_pagado"),
            detalle=Concat(
                Value("Cuota "), Cast("numero", CharField()), output_field=CharField()
            ),
            estado_reporte=Case(
                When(estado=EstadoCuota.PAGADA, then=Value("PAGADO")),
                default=F("estado"),
                output_field=CharField(),
            ),
        )
    )
    rentas = (
        listar_pagos_renta_visibles(usuario=usuario)
        .filter(
            Q(estado=EstadoPagoRenta.PAGADO)
            | Q(estado=EstadoPagoRenta.PENDIENTE, fecha_vencimiento__lt=hoy)
        )
        .annotate(
            exigible=F("monto") + F("mora_aplicada"),
            pagado=Coalesce(F("monto_pagado"), Value(0), output_field=MONTO),
            saldo=Case(
                When(estado=EstadoPagoRenta.PENDIENTE, then=F("monto")),
                default=Value(0),
                output_field=MONTO,
            ),
            detalle=Concat(
                Cast("periodo_mes", CharField()),
                Value("/"),
                Cast("periodo_anio", CharField()),
                output_field=CharField(),
            ),
            estado_reporte=F("estado"),
        )
    )
    return tuple(
        _filtrar(
            consulta,
            {
                "contrato__cliente_id": filtros.cliente,
                "fecha_vencimiento__gte": filtros.fecha_desde,
                "fecha_vencimiento__lte": filtros.fecha_hasta,
                "estado_reporte": filtros.estado,
                "contrato__agente_id": filtros.agente,
                "contrato__moneda__codigo": filtros.moneda,
            },
        ).order_by()
        for consulta in (cuotas, rentas)
    )


def resumir_estado_cuenta(
    *, filtros: FiltrosEstadoCuenta, usuario: AbstractBaseUser
) -> ResumenReporte:
    """Exigible, pagado y saldo por moneda, y por cliente, origen y moneda."""
    cantidad = 0
    por_moneda = {}
    por_cliente = {}
    for consulta, origen in zip(
        _fuentes_estado_cuenta(filtros, usuario), ("Cuota", "Renta"), strict=True
    ):
        for fila in consulta.values(
            "contrato__cliente_id",
            moneda_codigo=F("contrato__moneda__codigo"),
            cliente_nombre=_nombre_cliente("contrato__cliente__"),
        ).annotate(
            cantidad=Count("id"),
            total_exigible=Sum("exigible"),
            total_pagado=Sum("pagado"),
            total_saldo=Sum("saldo"),
        ):
            moneda = fila["moneda_codigo"]
            cantidad += fila["cantidad"]
            totales = por_moneda.setdefault(
                moneda,
                dict(exigible=Decimal("0"), pagado=Decimal("0"), saldo=Decimal("0")),
            )
            totales["exigible"] += fila["total_exigible"]
            totales["pagado"] += fila["total_pagado"]
            totales["saldo"] += fila["total_saldo"]
            por_cliente[(fila["cliente_nombre"], origen, moneda)] = dict(
                cantidad=fila["cantidad"],
                exigible=fila["total_exigible"],
                pagado=fila["total_pagado"],
                saldo=fila["total_saldo"],
            )
    return ResumenReporte(
        cantidad,
        dict(cantidad=cantidad, por_moneda=dict(sorted(por_moneda.items()))),
        [
            Grupo(" / ".join(clave), valores)
            for clave, valores in sorted(por_cliente.items())
        ],
    )


def seleccionar_estado_cuenta(
    *, filtros: FiltrosEstadoCuenta, usuario: AbstractBaseUser, offset: int, limite: int
) -> list[dict]:
    cuotas, rentas = _fuentes_estado_cuenta(filtros, usuario)
    proyecciones = [
        consulta.values(
            "id",
            "fecha_vencimiento",
            "exigible",
            "pagado",
            "saldo",
            "detalle",
            "estado_reporte",
            **_campos_obligacion(origen),
        )
        for consulta, origen in ((cuotas, "Cuota"), (rentas, "Renta"))
    ]
    filas = list(
        proyecciones[0]
        .union(proyecciones[1], all=True)
        .order_by("cliente_nombre", "fecha_vencimiento", "origen", "id")[
            offset : offset + limite
        ]
    )
    hoy = _hoy()
    for fila in filas:
        fila["mora"] = (
            "Sí" if fila["saldo"] and fila["fecha_vencimiento"] < hoy else "No"
        )
        fila["estado"] = fila.pop("estado_reporte").capitalize()
    return filas


# Lo que selectors.py llama para cada slug: (resumir, seleccionar filas).
REPORTES_COMERCIALES = {
    "ventas-por-periodo": (resumir_ventas, seleccionar_ventas),
    "desempeno-agentes": (resumir_agentes, seleccionar_agentes),
    "embudo-cotizaciones": (resumir_cotizaciones, seleccionar_cotizaciones),
    "ranking-clientes": (resumir_clientes, seleccionar_clientes),
    "estado-cuenta-clientes": (resumir_estado_cuenta, seleccionar_estado_cuenta),
    "morosidad": (resumir_morosidad, seleccionar_morosidad),
}
