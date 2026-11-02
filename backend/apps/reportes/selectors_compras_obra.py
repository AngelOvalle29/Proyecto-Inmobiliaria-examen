"""
Reportes de compras y construcción de la spec 021: R13 y R15.

Van aparte, como los comerciales y los del catálogo. Los hizo A en el cierre,
con el acuerdo del equipo, sobre los modelos de la spec 017 (rol C). Cada
reporte son dos funciones: una que agrega todo el filtro en PostgreSQL y otra
que trae solo las filas de la página.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import (
    Count,
    DecimalField,
    F,
    OuterRef,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.compras.enums import EstadoContratoCompra
from apps.compras.selectors import listar_contratos_compra
from apps.construccion.enums import ESTADOS_ACTIVOS, ESTADOS_COMPROMETIDOS, EstadoPago
from apps.construccion.models import PagoConstructora
from apps.construccion.selectors import listar_proyectos

from .estructuras import FiltrosCompras, FiltrosObras, Grupo, ResumenReporte

GUATEMALA = ZoneInfo("America/Guatemala")
CENTAVOS = Decimal("0.01")
CERO = Decimal("0.00")
MONTO = DecimalField(max_digits=18, decimal_places=2)


def _filtrar(consulta: QuerySet, condiciones: dict) -> QuerySet:
    """Aplica solo las condiciones que tienen valor."""
    return consulta.filter(**{k: v for k, v in condiciones.items() if v is not None})


# ---------- R13 Compras por proveedor ----------


def _compras(filtros: FiltrosCompras) -> QuerySet:
    """
    Regla 16: solo las compras COMPLETADO; una EN_PROCESO no es una
    adquisición realizada. El país es el de la propiedad comprada, no el del
    proveedor.
    """
    return _filtrar(
        listar_contratos_compra().filter(estado=EstadoContratoCompra.COMPLETADO),
        {
            "fecha_compra__gte": filtros.fecha_desde,
            "fecha_compra__lte": filtros.fecha_hasta,
            "proveedor_id": filtros.proveedor,
            "propiedad__ciudad__pais_id": filtros.pais,
            "moneda__codigo": filtros.moneda,
        },
    )


def resumir_compras(
    *, filtros: FiltrosCompras, usuario: AbstractBaseUser | None = None
) -> ResumenReporte:
    """
    Los componentes del costo por proveedor, mes y moneda. Las monedas no se
    suman entre sí: el consolidado es en dólares, con la tasa guardada en cada
    contrato al registrarlo.
    """
    compras = _compras(filtros)
    grupos = (
        compras.order_by()
        .annotate(mes=TruncMonth("fecha_compra"))
        .values(
            "mes",
            proveedor_nombre=F("proveedor__nombre"),
            moneda_codigo=F("moneda__codigo"),
        )
        .annotate(
            cantidad=Count("id"),
            monto_total=Sum("monto"),
            gastos=Sum("gastos_legales"),
            impuestos_total=Sum("impuestos"),
            costo=Sum("costo_total"),
            costo_usd=Sum("costo_total_usd"),
        )
        .order_by("proveedor_nombre", "mes", "moneda_codigo")
    )
    por_moneda = (
        compras.order_by()
        .values(moneda_codigo=F("moneda__codigo"))
        .annotate(costo=Sum("costo_total"))
        .order_by("moneda_codigo")
    )
    totales = compras.aggregate(
        cantidad=Count("id"), costo_usd=Coalesce(Sum("costo_total_usd"), CERO)
    )
    return ResumenReporte(
        totales["cantidad"],
        dict(
            cantidad=totales["cantidad"],
            costo_por_moneda={m["moneda_codigo"]: m["costo"] for m in por_moneda},
            costo_usd=totales["costo_usd"],
        ),
        [
            Grupo(
                f"{g['proveedor_nombre']} / {g['mes']:%Y-%m} / {g['moneda_codigo']}",
                dict(
                    proveedor=g["proveedor_nombre"],
                    mes=f"{g['mes']:%Y-%m}",
                    moneda=g["moneda_codigo"],
                    cantidad=g["cantidad"],
                    monto=g["monto_total"],
                    gastos_legales=g["gastos"],
                    impuestos=g["impuestos_total"],
                    costo_total=g["costo"],
                    costo_usd=g["costo_usd"],
                ),
            )
            for g in grupos
        ],
    )


def seleccionar_compras(
    *,
    filtros: FiltrosCompras,
    offset: int,
    limite: int,
    usuario: AbstractBaseUser | None = None,
) -> list[dict]:
    return list(
        _compras(filtros)
        .order_by("fecha_compra", "id")
        .values(
            "codigo",
            "fecha_compra",
            "monto",
            "gastos_legales",
            "impuestos",
            "costo_total",
            "costo_total_usd",
            proveedor_nombre=F("proveedor__nombre"),
            propiedad_codigo=F("propiedad__codigo"),
            propiedad_nombre=F("propiedad__nombre"),
            moneda_codigo=F("moneda__codigo"),
        )[offset : offset + limite]
    )


# ---------- R15 Avance y presupuesto de obra ----------


def _suma_pagos(campo: str, estados: list[str]) -> Coalesce:
    """
    La suma de los pagos de cada proyecto en esos estados, como subconsulta.
    No se une la tabla de pagos: al agrupar por constructora, un JOIN repetiría
    el presupuesto una vez por cada pago y lo sumaría de más.
    """
    return Coalesce(
        Subquery(
            PagoConstructora.objects.filter(
                activo=True, proyecto=OuterRef("pk"), estado__in=estados
            )
            .order_by()
            .values("proyecto")
            .annotate(total=Sum(campo))
            .values("total")[:1],
            output_field=MONTO,
        ),
        Value(CERO),
        output_field=MONTO,
    )


def _obras(filtros: FiltrosObras) -> QuerySet:
    """
    Regla 16, con las definiciones del detalle de proyecto de la spec 017:
    comprometido = programado + pagado (ESTADOS_COMPROMETIDOS) y disponible =
    presupuesto − comprometido. Saldo por pagar = presupuesto − pagado, que no
    es lo mismo que disponible. Todo en la moneda del proyecto; solo los pagos
    PAGADO tienen monto en dólares.
    """
    obras = _filtrar(
        listar_proyectos(),
        {
            "constructora_id": filtros.constructora,
            "estado": filtros.estado,
            "propiedad__ciudad__pais_id": filtros.pais,
            "fecha_inicio__gte": filtros.fecha_desde,
            "fecha_inicio__lte": filtros.fecha_hasta,
            "moneda__codigo": filtros.moneda,
        },
    )
    programado = _suma_pagos("monto", [EstadoPago.PROGRAMADO])
    pagado = _suma_pagos("monto", [EstadoPago.PAGADO])
    comprometido = _suma_pagos("monto", ESTADOS_COMPROMETIDOS)
    return obras.order_by().annotate(
        programado=programado,
        pagado=pagado,
        comprometido=comprometido,
        disponible=F("presupuesto_total") - comprometido,
        saldo_por_pagar=F("presupuesto_total") - pagado,
        pagado_usd=_suma_pagos("monto_usd", [EstadoPago.PAGADO]),
    )


def _desviacion(proyecto: dict, hoy) -> int | None:
    """
    Regla 16: días de atraso. Terminada, fin real − fin estimada; activa,
    cuánto pasó de la estimada (nunca negativo). Una cancelada no se califica
    como atrasada.
    """
    if proyecto["fecha_fin_real"] is not None:
        return (proyecto["fecha_fin_real"] - proyecto["fecha_fin_estimada"]).days
    if proyecto["estado"] in ESTADOS_ACTIVOS:
        return max(0, (hoy - proyecto["fecha_fin_estimada"]).days)
    return None


def resumir_obras(
    *, filtros: FiltrosObras, usuario: AbstractBaseUser | None = None
) -> ResumenReporte:
    """
    Presupuesto, programado, pagado, comprometido, disponible y saldo por
    constructora y moneda, sin mezclar monedas. El total en dólares suma solo
    los pagos realizados, con la tasa guardada al pagar.
    """
    obras = _obras(filtros)
    campos = (
        "presupuesto_total",
        "programado",
        "pagado",
        "comprometido",
        "disponible",
        "saldo_por_pagar",
    )
    grupos = (
        obras.values(
            constructora_nombre=F("constructora__nombre"),
            moneda_codigo=F("moneda__codigo"),
        )
        .annotate(cantidad=Count("id"), **{f"suma_{c}": Sum(c) for c in campos})
        .order_by("constructora_nombre", "moneda_codigo")
    )
    por_moneda: dict[str, dict] = defaultdict(lambda: {c: CERO for c in campos})
    filas_grupo = []
    for g in grupos:
        valores = {c: g[f"suma_{c}"] for c in campos}
        for c in campos:
            por_moneda[g["moneda_codigo"]][c] += valores[c]
        filas_grupo.append(
            Grupo(
                f"{g['constructora_nombre']} / {g['moneda_codigo']}",
                dict(
                    constructora=g["constructora_nombre"],
                    moneda=g["moneda_codigo"],
                    cantidad=g["cantidad"],
                    **valores,
                ),
            )
        )
    hoy = timezone.localdate(timezone=GUATEMALA)
    atrasados = sum(
        1
        for proyecto in obras.values("estado", "fecha_fin_real", "fecha_fin_estimada")
        if (_desviacion(proyecto, hoy) or 0) > 0
    )
    # El nombre de la suma no puede repetir el de la anotación.
    totales = obras.aggregate(
        cantidad=Count("id"), total_pagado_usd=Coalesce(Sum("pagado_usd"), CERO)
    )
    return ResumenReporte(
        totales["cantidad"],
        dict(
            cantidad=totales["cantidad"],
            atrasados=atrasados,
            pagado_usd=totales["total_pagado_usd"],
            por_moneda=dict(sorted(por_moneda.items())),
        ),
        filas_grupo,
    )


def seleccionar_obras(
    *,
    filtros: FiltrosObras,
    offset: int,
    limite: int,
    usuario: AbstractBaseUser | None = None,
) -> list[dict]:
    filas = list(
        _obras(filtros)
        .order_by("fecha_inicio", "id")
        .values(
            "codigo",
            "nombre",
            "estado",
            "fecha_inicio",
            "fecha_fin_estimada",
            "fecha_fin_real",
            "presupuesto_total",
            "programado",
            "pagado",
            "comprometido",
            "disponible",
            "saldo_por_pagar",
            "porcentaje_avance",
            constructora_nombre=F("constructora__nombre"),
            propiedad_codigo=F("propiedad__codigo"),
            moneda_codigo=F("moneda__codigo"),
        )[offset : offset + limite]
    )
    hoy = timezone.localdate(timezone=GUATEMALA)
    for fila in filas:
        presupuesto = fila["presupuesto_total"]
        # Avance financiero: lo pagado sobre el presupuesto. No es el físico.
        fila["avance_financiero"] = (
            (fila["pagado"] / presupuesto * 100).quantize(CENTAVOS, ROUND_HALF_UP)
            if presupuesto
            else None
        )
        fila["desviacion_dias"] = _desviacion(fila, hoy)
    return filas


REPORTES_COMPRAS_OBRA = {
    "compras-proveedores": (resumir_compras, seleccionar_compras),
    "avance-presupuesto-obra": (resumir_obras, seleccionar_obras),
}
