"""Servicios de compras: escrituras con reglas de negocio, transacciones y
auditoría (specs 006 y 017, §6 y §7).

No conocen request ni hablan HTTP. Cada escritura registra su auditoría dentro
de la misma transacción: si algo falla, se revierten las dos.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.selectors import listar_propiedades
from apps.catalogo.services import cambiar_estado_propiedad
from apps.core.exceptions import (
    CiudadFueraDelPais,
    ErrorDominio,
    TipoCambioNoDisponible,
)
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_ciudades, listar_paises, obtener_tipo_cambio
from apps.usuarios.models import Usuario

from . import datos_demo
from .enums import EstadoContratoCompra, TipoProveedor
from .exceptions import (
    FechaInvalida,
    NitObligatorio,
    PropiedadConContrato,
    ProveedorConContratos,
    ProveedorDuplicado,
    TransicionInvalida,
)
from .models import ContratoCompra, Proveedor
from .selectors import (
    existe_contrato_no_anulado,
    existe_proveedor_con_nit,
    obtener_dolar,
    proveedor_tiene_contratos_en_proceso,
)

ENTIDAD_PROVEEDOR = "compras_proveedor"
ENTIDAD_CONTRATO = ContratoCompra._meta.db_table  # "compras_contratocompra"
CENTAVOS = Decimal("0.01")

# Campos que se guardan en la bitácora y que se pueden editar. El código no
# está: lo genera el sistema y no cambia nunca (regla 8).
CAMPOS_EDITABLES = [
    "tipo",
    "nombre",
    "nit",
    "email",
    "telefono",
    "pais",
    "ciudad",
    "direccion",
]


def crear_proveedor(*, datos: dict, autor: Usuario, ip: str | None) -> Proveedor:
    """
    Registra un proveedor y le asigna su código PRV-0001.

    - El NIT se guarda normalizado y solo puede faltar en un propietario
      particular (reglas 2 y 3).
    - No puede repetirse el NIT en el mismo país, aunque el otro proveedor
      esté desactivado (regla 3).
    - La ciudad, si se indica, debe ser del país (regla 7).

    datos ya viene validado por el serializador: pais y ciudad son instancias.
    """
    datos = {**datos, "nit": normalizar_documento(datos.get("nit", ""))}
    _validar(datos)

    with transaction.atomic():
        _validar_no_duplicado(pais=datos["pais"], nit=datos["nit"])
        proveedor = Proveedor.objects.create(
            **datos, creado_por=autor, actualizado_por=autor
        )
        # El código sale del id que da PostgreSQL: dos proveedores creados al
        # mismo tiempo nunca reciben el mismo (mismo patrón que la spec 004).
        proveedor.codigo = f"PRV-{proveedor.pk:04d}"
        proveedor.save(update_fields=["codigo"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.CREAR,
            valores_nuevos=_foto(proveedor),
            ip=ip,
        )
    return proveedor


def actualizar_proveedor(
    *, proveedor: Proveedor, datos: dict, autor: Usuario, ip: str | None
) -> Proveedor:
    """
    Edita los campos enviados y audita solo los que cambiaron.

    Las reglas se revisan sobre el resultado final: si cambia solo el tipo a
    BANCO, el NIT que ya tenía debe existir; si cambia solo el país, la ciudad
    que ya tenía debe seguir siendo de ese país. Si nada cambia, no se guarda
    ni se audita.
    """
    if "nit" in datos:
        datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    final = {
        campo: datos.get(campo, getattr(proveedor, campo)) for campo in CAMPOS_EDITABLES
    }
    _validar(final)

    cambios = [
        campo for campo in CAMPOS_EDITABLES if final[campo] != getattr(proveedor, campo)
    ]
    if not cambios:
        return proveedor

    with transaction.atomic():
        if "pais" in cambios or "nit" in cambios:
            _validar_no_duplicado(
                pais=final["pais"], nit=final["nit"], excluir_id=proveedor.pk
            )
        anteriores = _foto(proveedor, cambios)
        for campo in cambios:
            setattr(proveedor, campo, final[campo])
        proveedor.actualizado_por = autor
        proveedor.save(update_fields=[*cambios, "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores=anteriores,
            valores_nuevos=_foto(proveedor, cambios),
            ip=ip,
        )
    return proveedor


def desactivar_proveedor(
    *, proveedor: Proveedor, autor: Usuario, ip: str | None
) -> None:
    """
    Borrado lógico (spec 006, regla 9): el proveedor deja de listarse, no se
    borra.

    Con un contrato de compra EN_PROCESO no se desactiva (spec 017, regla 22):
    el contrato quedaría a nombre de un proveedor que ya no aparece en ninguna
    lista. Los completados y anulados no lo impiden, porque ya están cerrados.
    """
    if proveedor_tiene_contratos_en_proceso(proveedor=proveedor):
        raise ProveedorConContratos(proveedor=proveedor.codigo)
    with transaction.atomic():
        proveedor.activo = False
        proveedor.actualizado_por = autor
        proveedor.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.ELIMINAR,
            valores_anteriores={"activo": True},
            valores_nuevos={"activo": False},
            ip=ip,
        )


# ---------- Contratos de compra (spec 017) ----------

# Campos que se guardan en la bitácora al registrar un contrato.
CAMPOS_CONTRATO_AUDITADOS = [
    "codigo",
    "proveedor",
    "propiedad",
    "fecha_compra",
    "monto",
    "gastos_legales",
    "impuestos",
    "costo_total",
    "moneda",
    "tasa_a_usd",
    "costo_total_usd",
    "estado",
    "observaciones",
]


@transaction.atomic
def crear_contrato_compra(
    *, datos: dict, autor: Usuario, ip: str | None
) -> ContratoCompra:
    """
    Registra la compra de una propiedad a un proveedor (spec 017, reglas 1 a 5
    y 8).

    - La propiedad debe estar EN_NEGOCIACION y sin otro contrato que no esté
      anulado. El contrato nace EN_PROCESO y la propiedad no cambia: pasa a
      ADQUIRIDA solo al completar (reglas 1, 2 y 6).
    - El costo total es monto + gastos legales + impuestos; lo calcula el
      sistema, no lo manda el usuario (regla 3).
    - La fecha de compra no puede ser futura (regla 4).
    - Guarda la tasa al dólar de la fecha de compra y el costo convertido. Sin
      tasa registrada, se rechaza (regla 5).

    datos ya viene validado por el serializador: proveedor activo, propiedad
    activa, moneda, montos en rango.
    """
    propiedad = datos["propiedad"]
    fecha_compra = datos["fecha_compra"]
    if fecha_compra > timezone.localdate():
        raise FechaInvalida(
            campo="fecha_compra", mensaje="La fecha de compra no puede ser futura."
        )
    if propiedad.estado != EstadoPropiedad.EN_NEGOCIACION:
        raise PropiedadNoDisponible(
            codigo=propiedad.codigo,
            estado_actual=propiedad.estado,
            estado_requerido=EstadoPropiedad.EN_NEGOCIACION,
        )
    if existe_contrato_no_anulado(propiedad=propiedad):
        raise PropiedadConContrato(propiedad=propiedad.codigo)

    monto = datos["monto"]
    gastos_legales = datos.get("gastos_legales", Decimal("0"))
    impuestos = datos.get("impuestos", Decimal("0"))
    costo_total = monto + gastos_legales + impuestos
    moneda = datos["moneda"]
    tasa_a_usd = _tasa_a_dolar(moneda=moneda, fecha=fecha_compra)

    contrato = ContratoCompra.objects.create(
        proveedor=datos["proveedor"],
        propiedad=propiedad,
        fecha_compra=fecha_compra,
        monto=monto,
        gastos_legales=gastos_legales,
        impuestos=impuestos,
        costo_total=costo_total,
        moneda=moneda,
        tasa_a_usd=tasa_a_usd,
        costo_total_usd=_a_centavos(costo_total * tasa_a_usd),
        observaciones=datos.get("observaciones", ""),
        creado_por=autor,
        actualizado_por=autor,
    )
    # Regla 8: el código sale del id, como CV-00001 en ventas.
    contrato.codigo = f"CC-{contrato.pk:05d}"
    contrato.save(update_fields=["codigo"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_CONTRATO,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=model_to_dict(contrato, fields=CAMPOS_CONTRATO_AUDITADOS),
        ip=ip,
    )
    return contrato


@transaction.atomic
def completar_contrato_compra(
    *, contrato: ContratoCompra, autor: Usuario, ip: str | None
) -> ContratoCompra:
    """
    Cierra la compra: el contrato pasa a COMPLETADO y la propiedad de
    EN_NEGOCIACION a ADQUIRIDA (regla 6).

    La fila del contrato se bloquea antes de revisar su estado: dos peticiones
    que completan a la vez no pasan las dos (spec 017, §6). Si la propiedad ya
    no está en negociación, cambiar_estado_propiedad lanza
    PropiedadNoDisponible y la transacción revierte todo: el contrato sigue
    EN_PROCESO.
    """
    contrato = ContratoCompra.objects.select_for_update().get(pk=contrato.pk)
    _exigir_en_proceso(contrato, accion="completar")
    cambiar_estado_propiedad(
        propiedad=contrato.propiedad,
        estado=EstadoPropiedad.ADQUIRIDA,
        autor=autor,
        ip=ip,
        motivo=f"Compra {contrato.codigo} completada",
        estado_requerido=EstadoPropiedad.EN_NEGOCIACION,
    )
    contrato.estado = EstadoContratoCompra.COMPLETADO
    contrato.actualizado_por = autor
    contrato.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_CONTRATO,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"estado": EstadoContratoCompra.EN_PROCESO},
        valores_nuevos={"estado": EstadoContratoCompra.COMPLETADO},
        ip=ip,
    )
    return contrato


@transaction.atomic
def anular_contrato_compra(
    *, contrato: ContratoCompra, motivo: str, autor: Usuario, ip: str | None
) -> ContratoCompra:
    """
    Anula un contrato EN_PROCESO con su motivo (regla 7). La propiedad no
    cambia: sigue en negociación y puede tener otro contrato (regla 2).

    Un contrato completado no se anula: la propiedad ya es de la agencia, y
    deshacer la compra no está en el alcance.
    """
    contrato = ContratoCompra.objects.select_for_update().get(pk=contrato.pk)
    _exigir_en_proceso(contrato, accion="anular")
    contrato.estado = EstadoContratoCompra.ANULADO
    contrato.actualizado_por = autor
    contrato.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_CONTRATO,
        entidad_id=contrato.pk,
        accion=AccionAuditoria.ANULAR,
        valores_anteriores={"estado": EstadoContratoCompra.EN_PROCESO},
        valores_nuevos={"estado": EstadoContratoCompra.ANULADO, "motivo": motivo},
        ip=ip,
    )
    return contrato


def _exigir_en_proceso(contrato: ContratoCompra, *, accion: str) -> None:
    if contrato.estado != EstadoContratoCompra.EN_PROCESO:
        raise TransicionInvalida(
            codigo=contrato.codigo, estado=contrato.estado, accion=accion
        )


def _tasa_a_dolar(*, moneda, fecha: date) -> Decimal:
    """
    Tasa de la moneda al dólar vigente en la fecha (regla 5), como en ventas.
    Para un contrato en dólares es 1. Sin tasa registrada, o sin el dólar en
    el catálogo, se rechaza con TIPO_CAMBIO_NO_DISPONIBLE.
    """
    dolar = obtener_dolar()
    if dolar is None:
        raise TipoCambioNoDisponible(origen=moneda.codigo, destino="USD", fecha=fecha)
    return obtener_tipo_cambio(origen=moneda, destino=dolar, fecha=fecha)


def _a_centavos(valor: Decimal) -> Decimal:
    """Redondeo comercial a dos decimales, el mismo de ventas."""
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def cargar_demo_compras() -> dict[str, int]:
    """
    Carga los proveedores y contratos de compra ficticios de datos_demo.py y
    devuelve cuántos creó de cada uno.

    Es idempotente: busca cada proveedor por su país y su NIT (o por su nombre
    si es un particular sin NIT) y solo crea lo que falta. Necesita los países
    de core, que seed_demo carga antes; si un país no existe, ese proveedor se
    omite. No registra auditoría: es la foto inicial de la demostración, no una
    operación del negocio (mismo criterio que la spec 004).

    Los contratos (spec 017) necesitan además las propiedades de
    cargar_demo_catalogo. Ver _cargar_contratos_demo.
    """
    paises = {pais.codigo_iso: pais for pais in listar_paises()}
    ciudades = {(c.pais.codigo_iso, c.nombre): c for c in listar_ciudades()}
    creados = 0
    for tipo, nombre, nit, email, codigo_pais, nombre_ciudad in datos_demo.PROVEEDORES:
        pais = paises.get(codigo_pais)
        if pais is None:
            continue
        nit = normalizar_documento(nit)
        existentes = Proveedor.objects.filter(pais=pais)
        existentes = (
            existentes.filter(nit=nit) if nit else existentes.filter(nombre=nombre)
        )
        if existentes.exists():
            continue
        proveedor = Proveedor.objects.create(
            tipo=tipo,
            nombre=nombre,
            nit=nit,
            email=email,
            pais=pais,
            ciudad=ciudades.get((codigo_pais, nombre_ciudad)),
        )
        proveedor.codigo = f"PRV-{proveedor.pk:04d}"
        proveedor.save(update_fields=["codigo"])
        creados += 1
    return {"proveedores": creados, "contratos": _cargar_contratos_demo()}


def _cargar_contratos_demo() -> int:
    """
    Contratos de compra de la demostración (spec 017). Devuelve cuántos creó.

    Son una foto, como el resto de la demo: se guardan con el estado que ya
    tienen sus propiedades en la demo del catálogo (el terreno en negociación,
    la gasolinera y el hotel ya comprados), sin pasar por completar ni cambiar
    el estado de nada, y sin auditoría. Calculan su costo total y su tasa igual
    que el servicio.

    Se salta un contrato si su propiedad o su proveedor no existen, si la
    propiedad ya tiene un contrato no anulado (así no duplica), o si falta la
    tasa al dólar.
    """
    hoy = timezone.localdate()
    creados = 0
    for datos in datos_demo.CONTRATOS:
        propiedad = listar_propiedades().filter(nombre=datos["propiedad"]).first()
        nit = normalizar_documento(datos["proveedor_nit"])
        proveedor = Proveedor.objects.filter(nit=nit).first()
        if propiedad is None or proveedor is None:
            continue
        if existe_contrato_no_anulado(propiedad=propiedad):
            continue
        fecha = hoy - timedelta(days=datos["dias_desde_compra"])
        try:
            tasa = _tasa_a_dolar(moneda=propiedad.moneda, fecha=fecha)
        except ErrorDominio:
            continue
        monto = Decimal(datos["monto"])
        gastos = Decimal(datos["gastos_legales"])
        impuestos = Decimal(datos["impuestos"])
        costo_total = monto + gastos + impuestos
        contrato = ContratoCompra.objects.create(
            proveedor=proveedor,
            propiedad=propiedad,
            fecha_compra=fecha,
            monto=monto,
            gastos_legales=gastos,
            impuestos=impuestos,
            costo_total=costo_total,
            moneda=propiedad.moneda,
            tasa_a_usd=tasa,
            costo_total_usd=_a_centavos(costo_total * tasa),
            estado=datos["estado"],
            observaciones=datos["observaciones"],
        )
        contrato.codigo = f"CC-{contrato.pk:05d}"
        contrato.save(update_fields=["codigo"])
        creados += 1
    return creados


def _validar(datos: dict) -> None:
    if not datos["nit"] and datos["tipo"] != TipoProveedor.PROPIETARIO_PARTICULAR:
        raise NitObligatorio()
    ciudad, pais = datos.get("ciudad"), datos["pais"]
    if ciudad is not None and ciudad.pais_id != pais.pk:
        raise CiudadFueraDelPais(ciudad=ciudad.nombre, pais=pais.nombre)


def _validar_no_duplicado(*, pais, nit: str, excluir_id: int | None = None) -> None:
    # Sin NIT no hay duplicado posible: varios particulares pueden no tenerlo.
    if nit and existe_proveedor_con_nit(pais=pais, nit=nit, excluir_id=excluir_id):
        raise ProveedorDuplicado(nit=nit, pais=pais.nombre)


def _foto(proveedor: Proveedor, campos: list[str] | None = None) -> dict:
    """Valores para la bitácora; las relaciones quedan como su id."""
    return model_to_dict(proveedor, fields=campos or ["codigo", *CAMPOS_EDITABLES])
