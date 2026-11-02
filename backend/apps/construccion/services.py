"""Servicios de construcción: escrituras con reglas de negocio, transacciones y
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
from apps.catalogo.exceptions import DocumentoDeOtraPropiedad, PropiedadNoDisponible
from apps.catalogo.selectors import listar_propiedades, listar_unidades
from apps.catalogo.services import cambiar_estado_propiedad, cambiar_estado_unidad
from apps.core.exceptions import ErrorDominio, TipoCambioNoDisponible
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_paises, obtener_tipo_cambio
from apps.usuarios.models import Usuario

from . import datos_demo
from .enums import ESTADOS_ACTIVOS, EstadoPago, EstadoProyecto, TipoPagoConstructora
from .exceptions import (
    AvanceInvalido,
    ConstructoraConProyectos,
    ConstructoraDuplicada,
    FechaInvalida,
    NitObligatorio,
    PresupuestoExcedido,
    PropiedadConProyecto,
    TransicionInvalida,
)
from .models import Constructora, PagoConstructora, ProyectoConstruccion
from .selectors import (
    constructora_tiene_proyectos_activos,
    existe_constructora_con_nit,
    existe_proyecto_activo,
    obtener_dolar,
    total_comprometido,
)

ENTIDAD_CONSTRUCTORA = "construccion_constructora"
ENTIDAD_PROYECTO = ProyectoConstruccion._meta.db_table
ENTIDAD_PAGO = PagoConstructora._meta.db_table
# Regla 15: las unidades que finalizar una obra pone a la venta.
UNIDADES_POR_PUBLICAR = [
    EstadoPropiedad.EN_NEGOCIACION,
    EstadoPropiedad.EN_CONSTRUCCION,
]
CENTAVOS = Decimal("0.01")

# Campos que se guardan en la bitácora y que se pueden editar. El código no
# está: lo genera el sistema y no cambia nunca (regla 8).
CAMPOS_EDITABLES = [
    "nombre",
    "nit",
    "contacto",
    "email",
    "telefono",
    "pais",
    "calificacion",
]


def crear_constructora(*, datos: dict, autor: Usuario, ip: str | None) -> Constructora:
    """
    Registra una constructora y le asigna su código CST-0001.

    - El NIT es obligatorio y se guarda normalizado (reglas 4 y 5).
    - No puede repetirse en el mismo país, aunque la otra constructora esté
      desactivada (regla 5).
    - La calificación, si se indica, va de 1 a 5; la valida el serializador y
      la base (regla 6).
    """
    datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    _validar(datos)

    with transaction.atomic():
        _validar_no_duplicado(pais=datos["pais"], nit=datos["nit"])
        constructora = Constructora.objects.create(
            **datos, creado_por=autor, actualizado_por=autor
        )
        # El código sale del id que da PostgreSQL (mismo patrón que la spec 004).
        constructora.codigo = f"CST-{constructora.pk:04d}"
        constructora.save(update_fields=["codigo"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.CREAR,
            valores_nuevos=_foto(constructora),
            ip=ip,
        )
    return constructora


def actualizar_constructora(
    *, constructora: Constructora, datos: dict, autor: Usuario, ip: str | None
) -> Constructora:
    """Edita los campos enviados y audita solo los que cambiaron.

    Si nada cambia, no se guarda ni se audita.
    """
    if "nit" in datos:
        datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    final = {
        campo: datos.get(campo, getattr(constructora, campo))
        for campo in CAMPOS_EDITABLES
    }
    _validar(final)

    cambios = [
        campo
        for campo in CAMPOS_EDITABLES
        if final[campo] != getattr(constructora, campo)
    ]
    if not cambios:
        return constructora

    with transaction.atomic():
        if "pais" in cambios or "nit" in cambios:
            _validar_no_duplicado(
                pais=final["pais"], nit=final["nit"], excluir_id=constructora.pk
            )
        anteriores = _foto(constructora, cambios)
        for campo in cambios:
            setattr(constructora, campo, final[campo])
        constructora.actualizado_por = autor
        constructora.save(update_fields=[*cambios, "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores=anteriores,
            valores_nuevos=_foto(constructora, cambios),
            ip=ip,
        )
    return constructora


def desactivar_constructora(
    *, constructora: Constructora, autor: Usuario, ip: str | None
) -> None:
    """
    Borrado lógico (spec 006, regla 9): deja de listarse, no se borra.

    Con un proyecto activo no se desactiva (spec 017, regla 23): la obra
    quedaría a cargo de una constructora que ya no aparece en ninguna lista.
    """
    if constructora_tiene_proyectos_activos(constructora=constructora):
        raise ConstructoraConProyectos(constructora=constructora.codigo)
    with transaction.atomic():
        constructora.activo = False
        constructora.actualizado_por = autor
        constructora.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.ELIMINAR,
            valores_anteriores={"activo": True},
            valores_nuevos={"activo": False},
            ip=ip,
        )


# ---------- Proyectos de construcción (spec 017) ----------

CAMPOS_PROYECTO_AUDITADOS = [
    "codigo",
    "nombre",
    "propiedad",
    "constructora",
    "fecha_inicio",
    "fecha_fin_estimada",
    "presupuesto_total",
    "moneda",
    "tasa_a_usd",
    "presupuesto_total_usd",
    "estado",
    "porcentaje_avance",
]


@transaction.atomic
def crear_proyecto(
    *, datos: dict, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """
    Registra una obra sobre una propiedad (spec 017, reglas 9 a 11 y 18).

    - La propiedad debe estar ADQUIRIDA y sin otro proyecto activo (reglas 9 y
      10). El proyecto nace PLANIFICADO con avance 0; la propiedad no cambia
      hasta iniciar la obra.
    - La fecha de fin estimada no es anterior a la de inicio (regla 11).
    - Guarda la tasa al dólar de la fecha de inicio y el presupuesto
      convertido. Sin tasa registrada, se rechaza (regla 11).

    datos ya viene validado por el serializador: constructora activa,
    propiedad activa, moneda y presupuesto mayor que cero.
    """
    propiedad = datos["propiedad"]
    _validar_fechas(datos["fecha_inicio"], datos["fecha_fin_estimada"])
    if propiedad.estado != EstadoPropiedad.ADQUIRIDA:
        raise PropiedadNoDisponible(
            codigo=propiedad.codigo,
            estado_actual=propiedad.estado,
            estado_requerido=EstadoPropiedad.ADQUIRIDA,
        )
    if existe_proyecto_activo(propiedad=propiedad):
        raise PropiedadConProyecto(propiedad=propiedad.codigo)

    presupuesto = datos["presupuesto_total"]
    tasa_a_usd = _tasa_a_dolar(moneda=datos["moneda"], fecha=datos["fecha_inicio"])
    proyecto = ProyectoConstruccion.objects.create(
        nombre=datos["nombre"],
        propiedad=propiedad,
        constructora=datos["constructora"],
        fecha_inicio=datos["fecha_inicio"],
        fecha_fin_estimada=datos["fecha_fin_estimada"],
        presupuesto_total=presupuesto,
        moneda=datos["moneda"],
        tasa_a_usd=tasa_a_usd,
        presupuesto_total_usd=_a_centavos(presupuesto * tasa_a_usd),
        creado_por=autor,
        actualizado_por=autor,
    )
    # Regla 18: el código sale del id, como CC-00001 en compras.
    proyecto.codigo = f"PC-{proyecto.pk:05d}"
    proyecto.save(update_fields=["codigo"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PROYECTO,
        entidad_id=proyecto.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=model_to_dict(proyecto, fields=CAMPOS_PROYECTO_AUDITADOS),
        ip=ip,
    )
    return proyecto


@transaction.atomic
def actualizar_proyecto(
    *, proyecto: ProyectoConstruccion, datos: dict, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """
    Edita el nombre, la fecha de fin estimada y el presupuesto (regla 17).

    - Un proyecto activo admite los tres.
    - Uno FINALIZADO, solo el presupuesto: subirlo es la forma de pagar un
      finiquito que no cabía (§10). Uno CANCELADO, nada.
    - Si cambia el presupuesto, se convierte con la tasa que el proyecto ya
      tiene (regla 11), no con la de hoy.
    - El presupuesto nunca queda por debajo de lo ya programado y pagado
      (reglas 17 y 19). Se revisa con la fila bloqueada, para que un pago que
      se programa al mismo tiempo no se cuele.

    Audita solo lo que cambió; si nada cambia, no guarda ni audita.
    """
    proyecto = ProyectoConstruccion.objects.select_for_update().get(pk=proyecto.pk)
    editables = _campos_editables(proyecto)
    no_permitidos = [campo for campo in datos if campo not in editables]
    if no_permitidos:
        raise TransicionInvalida(
            codigo=proyecto.codigo,
            estado=proyecto.estado,
            accion=f"editar {', '.join(no_permitidos)}",
        )

    cambios = [c for c in datos if datos[c] != getattr(proyecto, c)]
    if not cambios:
        return proyecto
    fin_estimada = datos.get("fecha_fin_estimada", proyecto.fecha_fin_estimada)
    _validar_fechas(proyecto.fecha_inicio, fin_estimada)
    if "presupuesto_total" in cambios:
        comprometido = total_comprometido(proyecto=proyecto)
        if datos["presupuesto_total"] < comprometido:
            raise PresupuestoExcedido(
                proyecto=proyecto.codigo,
                presupuesto=datos["presupuesto_total"],
                comprometido=comprometido,
            )

    campos_bitacora = list(cambios)
    if "presupuesto_total" in cambios:
        campos_bitacora.append("presupuesto_total_usd")
    anteriores = model_to_dict(proyecto, fields=campos_bitacora)
    for campo in cambios:
        setattr(proyecto, campo, datos[campo])
    if "presupuesto_total" in cambios:
        proyecto.presupuesto_total_usd = _a_centavos(
            proyecto.presupuesto_total * proyecto.tasa_a_usd
        )
    proyecto.actualizado_por = autor
    proyecto.save(update_fields=[*campos_bitacora, "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PROYECTO,
        entidad_id=proyecto.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores=anteriores,
        valores_nuevos=model_to_dict(proyecto, fields=campos_bitacora),
        ip=ip,
    )
    return proyecto


@transaction.atomic
def iniciar_proyecto(
    *, proyecto: ProyectoConstruccion, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """
    Empieza la obra: el proyecto pasa de PLANIFICADO a EN_EJECUCION y la
    propiedad de ADQUIRIDA a EN_CONSTRUCCION (regla 12). Si la propiedad ya no
    está adquirida, el catálogo lo rechaza y no cambia nada.
    """
    proyecto = _bloquear(
        proyecto, exigir=[EstadoProyecto.PLANIFICADO], accion="iniciar"
    )
    cambiar_estado_propiedad(
        propiedad=proyecto.propiedad,
        estado=EstadoPropiedad.EN_CONSTRUCCION,
        autor=autor,
        ip=ip,
        motivo=f"Inicio de la obra {proyecto.codigo}",
        estado_requerido=EstadoPropiedad.ADQUIRIDA,
    )
    return _cambiar_estado(proyecto, EstadoProyecto.EN_EJECUCION, autor=autor, ip=ip)


@transaction.atomic
def registrar_avance(
    *,
    proyecto: ProyectoConstruccion,
    porcentaje: int,
    descripcion: str,
    autor: Usuario,
    ip: str | None,
) -> ProyectoConstruccion:
    """
    Registra cuánto lleva la obra (regla 13): solo EN_EJECUCION, de 0 a 100 y
    nunca menos que el anterior. Puede repetirse el mismo porcentaje con otra
    descripción. El historial queda en la bitácora con su descripción, porque
    no hay entidad AvanceObra (§10).
    """
    proyecto = _bloquear(
        proyecto, exigir=[EstadoProyecto.EN_EJECUCION], accion="registrar avance"
    )
    if porcentaje > 100:
        raise AvanceInvalido("El avance no puede pasar de 100.")
    if porcentaje < proyecto.porcentaje_avance:
        raise AvanceInvalido(
            f"El avance no puede bajar: el proyecto ya va en "
            f"{proyecto.porcentaje_avance} %."
        )
    anterior = proyecto.porcentaje_avance
    proyecto.porcentaje_avance = porcentaje
    proyecto.actualizado_por = autor
    proyecto.save(
        update_fields=["porcentaje_avance", "actualizado_por", "actualizado_en"]
    )
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PROYECTO,
        entidad_id=proyecto.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"porcentaje_avance": anterior},
        valores_nuevos={"porcentaje_avance": porcentaje, "descripcion": descripcion},
        ip=ip,
    )
    return proyecto


@transaction.atomic
def suspender_proyecto(
    *, proyecto: ProyectoConstruccion, motivo: str, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """Pausa la obra con su motivo (regla 14). La propiedad sigue en construcción."""
    proyecto = _bloquear(
        proyecto, exigir=[EstadoProyecto.EN_EJECUCION], accion="suspender"
    )
    return _cambiar_estado(
        proyecto, EstadoProyecto.SUSPENDIDO, autor=autor, ip=ip, motivo=motivo
    )


@transaction.atomic
def reanudar_proyecto(
    *, proyecto: ProyectoConstruccion, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """Retoma una obra suspendida (regla 14)."""
    proyecto = _bloquear(
        proyecto, exigir=[EstadoProyecto.SUSPENDIDO], accion="reanudar"
    )
    return _cambiar_estado(proyecto, EstadoProyecto.EN_EJECUCION, autor=autor, ip=ip)


@transaction.atomic
def finalizar_proyecto(
    *, proyecto: ProyectoConstruccion, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """
    Termina la obra (regla 15): solo EN_EJECUCION y con avance 100. La fecha
    de fin real es la de hoy.

    La propiedad pasa de EN_CONSTRUCCION a DISPONIBLE, y con ella sus unidades
    activas que todavía no estaban a la venta (EN_NEGOCIACION o
    EN_CONSTRUCCION): en un edificio lo que se cotiza y se vende son las
    unidades (revisión de Marco, §10). Las EN_CONSTRUCCION se agregaron al
    preparar la demo: el catálogo deja marcar así las unidades de una obra.
    Las que ya tienen otro estado (reservada, vendida) no se tocan.

    Si alguien movió la propiedad a mano durante la obra, el catálogo responde
    409 con su estado actual y no cambia nada (regla 26). La salida es
    devolverla a EN_CONSTRUCCION con /cambiar-estado/ y volver a finalizar.
    """
    proyecto = _bloquear(
        proyecto, exigir=[EstadoProyecto.EN_EJECUCION], accion="finalizar"
    )
    if proyecto.porcentaje_avance < 100:
        raise AvanceInvalido(
            f"Solo se finaliza con avance 100; el proyecto va en "
            f"{proyecto.porcentaje_avance} %."
        )
    motivo = f"Fin de la obra {proyecto.codigo}"
    cambiar_estado_propiedad(
        propiedad=proyecto.propiedad,
        estado=EstadoPropiedad.DISPONIBLE,
        autor=autor,
        ip=ip,
        motivo=motivo,
        estado_requerido=EstadoPropiedad.EN_CONSTRUCCION,
    )
    unidades = listar_unidades(propiedad=proyecto.propiedad).filter(
        estado__in=UNIDADES_POR_PUBLICAR
    )
    for unidad in unidades:
        cambiar_estado_unidad(
            unidad=unidad,
            estado=EstadoPropiedad.DISPONIBLE,
            autor=autor,
            ip=ip,
            motivo=motivo,
            # El que tenía al leerla: si alguien la cambió entre la lectura y
            # el bloqueo, el catálogo lo rechaza y se revierte todo.
            estado_requerido=unidad.estado,
        )
    proyecto.fecha_fin_real = timezone.localdate()
    return _cambiar_estado(
        proyecto,
        EstadoProyecto.FINALIZADO,
        autor=autor,
        ip=ip,
        extra={"fecha_fin_real": proyecto.fecha_fin_real},
        otros_campos=["fecha_fin_real"],
    )


@transaction.atomic
def cancelar_proyecto(
    *, proyecto: ProyectoConstruccion, motivo: str, autor: Usuario, ip: str | None
) -> ProyectoConstruccion:
    """
    Cancela la obra con su motivo, desde cualquier estado activo (regla 16).

    - Si la propiedad está EN_CONSTRUCCION, vuelve a ADQUIRIDA.
    - Si alguien ya la movió a mano a otro estado, se cancela sin tocarla y la
      bitácora lo anota: cancelar siempre es posible, para que un proyecto
      nunca quede atascado (regla 26).
    - Un proyecto PLANIFICADO nunca cambió la propiedad, así que no hay nada que
      devolver.
    - Sus pagos programados se anulan con él: ya no se van a pagar. Los pagados
      quedan como están, porque ese dinero ya salió.
    """
    proyecto = _bloquear(proyecto, exigir=ESTADOS_ACTIVOS, accion="cancelar")
    propiedad = proyecto.propiedad
    propiedad.refresh_from_db(fields=["estado"])
    extra = {"motivo": motivo}
    if propiedad.estado == EstadoPropiedad.EN_CONSTRUCCION:
        cambiar_estado_propiedad(
            propiedad=propiedad,
            estado=EstadoPropiedad.ADQUIRIDA,
            autor=autor,
            ip=ip,
            motivo=f"Obra {proyecto.codigo} cancelada",
            estado_requerido=EstadoPropiedad.EN_CONSTRUCCION,
        )
    elif proyecto.estado != EstadoProyecto.PLANIFICADO:
        extra["propiedad_sin_cambio"] = propiedad.estado
    # select_for_update: si alguien paga uno de estos pagos al mismo tiempo,
    # se espera a que termine. PostgreSQL vuelve a revisar el filtro sobre la
    # fila ya pagada y la deja fuera, así un pago PAGADO nunca se anula.
    programados = PagoConstructora.objects.select_for_update().filter(
        proyecto=proyecto, estado=EstadoPago.PROGRAMADO
    )
    for pago in programados:
        _anular(pago, motivo=f"Obra {proyecto.codigo} cancelada", autor=autor, ip=ip)
    return _cambiar_estado(
        proyecto,
        EstadoProyecto.CANCELADO,
        autor=autor,
        ip=ip,
        accion=AccionAuditoria.ANULAR,
        extra=extra,
    )


# ---------- Pagos a constructoras (spec 017) ----------

CAMPOS_PAGO_AUDITADOS = [
    "codigo",
    "proyecto",
    "tipo",
    "monto",
    "moneda",
    "fecha_programada",
    "estado",
    "documento",
    "observaciones",
]


@transaction.atomic
def programar_pago(
    *, proyecto: ProyectoConstruccion, datos: dict, autor: Usuario, ip: str | None
) -> PagoConstructora:
    """
    Programa un pago a la constructora de la obra (spec 017, reglas 19 a 21).

    - En la moneda del proyecto: la asigna el sistema (regla 20).
    - No para un proyecto cancelado. Un FINIQUITO, solo para uno FINALIZADO
      (regla 20).
    - El documento, si lo lleva, debe ser de la misma propiedad (regla 20).
    - Lo programado y pagado, con este pago, no supera el presupuesto (regla
      19). La fila del proyecto se bloquea antes de sumar: dos pagos
      simultáneos no pueden pasar juntos el presupuesto (§6).

    datos ya viene validado: tipo, monto mayor que cero, documento activo.
    """
    proyecto = ProyectoConstruccion.objects.select_for_update().get(pk=proyecto.pk)
    tipo = datos["tipo"]
    if proyecto.estado == EstadoProyecto.CANCELADO:
        raise TransicionInvalida(
            codigo=proyecto.codigo, estado=proyecto.estado, accion="programar pagos"
        )
    if tipo == TipoPagoConstructora.FINIQUITO and (
        proyecto.estado != EstadoProyecto.FINALIZADO
    ):
        raise TransicionInvalida(
            codigo=proyecto.codigo,
            estado=proyecto.estado,
            accion="programar un finiquito antes de finalizar",
        )
    documento = datos.get("documento")
    if documento is not None and documento.propiedad_id != proyecto.propiedad_id:
        raise DocumentoDeOtraPropiedad(
            documento=documento.nombre,
            propiedad=proyecto.propiedad.codigo,
            propiedad_documento=documento.propiedad.codigo,
        )
    comprometido = total_comprometido(proyecto=proyecto) + datos["monto"]
    if comprometido > proyecto.presupuesto_total:
        raise PresupuestoExcedido(
            proyecto=proyecto.codigo,
            presupuesto=proyecto.presupuesto_total,
            comprometido=comprometido,
        )

    pago = PagoConstructora.objects.create(
        proyecto=proyecto,
        tipo=tipo,
        monto=datos["monto"],
        moneda=proyecto.moneda,
        fecha_programada=datos["fecha_programada"],
        documento=documento,
        observaciones=datos.get("observaciones", ""),
        creado_por=autor,
        actualizado_por=autor,
    )
    # Regla 21: el código sale del id, como los contratos y proyectos.
    pago.codigo = f"PG-{pago.pk:05d}"
    pago.save(update_fields=["codigo"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PAGO,
        entidad_id=pago.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=model_to_dict(pago, fields=CAMPOS_PAGO_AUDITADOS),
        ip=ip,
    )
    return pago


@transaction.atomic
def pagar(
    *,
    pago: PagoConstructora,
    fecha_pago: date,
    referencia: str,
    autor: Usuario,
    ip: str | None,
) -> PagoConstructora:
    """
    Registra que el pago salió (regla 21): de PROGRAMADO a PAGADO, con su fecha
    y su referencia, y la tasa al dólar de esa fecha con el monto convertido.

    La fecha de pago no puede ser futura ni anterior al inicio de la obra,
    salvo un ANTICIPO, que se paga justamente antes de empezar (decidido en la
    revisión de Marco, §10).
    """
    pago = _bloquear_pago(pago, accion="pagar")
    if fecha_pago > timezone.localdate():
        raise FechaInvalida(
            campo="fecha_pago", mensaje="La fecha de pago no puede ser futura."
        )
    inicio = pago.proyecto.fecha_inicio
    if fecha_pago < inicio and pago.tipo != TipoPagoConstructora.ANTICIPO:
        raise FechaInvalida(
            campo="fecha_pago",
            mensaje=(
                "Solo un anticipo se paga antes del inicio de la obra "
                f"({inicio.isoformat()})."
            ),
        )
    tasa_a_usd = _tasa_a_dolar(moneda=pago.moneda, fecha=fecha_pago)
    pago.estado = EstadoPago.PAGADO
    pago.fecha_pago = fecha_pago
    pago.referencia_pago = referencia
    pago.tasa_a_usd = tasa_a_usd
    pago.monto_usd = _a_centavos(pago.monto * tasa_a_usd)
    pago.actualizado_por = autor
    campos = ["estado", "fecha_pago", "referencia_pago", "tasa_a_usd", "monto_usd"]
    pago.save(update_fields=[*campos, "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PAGO,
        entidad_id=pago.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"estado": EstadoPago.PROGRAMADO},
        valores_nuevos=model_to_dict(pago, fields=campos),
        ip=ip,
    )
    return pago


@transaction.atomic
def anular_pago(
    *, pago: PagoConstructora, motivo: str, autor: Usuario, ip: str | None
) -> PagoConstructora:
    """
    Anula un pago PROGRAMADO con su motivo (regla 21): deja de contar contra
    el presupuesto. Un pago pagado no se anula, porque el dinero ya salió.
    """
    pago = _bloquear_pago(pago, accion="anular")
    return _anular(pago, motivo=motivo, autor=autor, ip=ip)


def _bloquear_pago(pago: PagoConstructora, *, accion: str) -> PagoConstructora:
    """Bloquea la fila del pago y exige que esté PROGRAMADO (spec 017, §6)."""
    pago = (
        PagoConstructora.objects.select_for_update()
        .select_related("proyecto")
        .get(pk=pago.pk)
    )
    if pago.estado != EstadoPago.PROGRAMADO:
        raise TransicionInvalida(codigo=pago.codigo, estado=pago.estado, accion=accion)
    return pago


def _anular(
    pago: PagoConstructora, *, motivo: str, autor: Usuario, ip: str | None
) -> PagoConstructora:
    """Pasos de anular un pago; los usan anular_pago y cancelar_proyecto."""
    pago.estado = EstadoPago.ANULADO
    pago.actualizado_por = autor
    pago.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PAGO,
        entidad_id=pago.pk,
        accion=AccionAuditoria.ANULAR,
        valores_anteriores={"estado": EstadoPago.PROGRAMADO},
        valores_nuevos={"estado": EstadoPago.ANULADO, "motivo": motivo},
        ip=ip,
    )
    return pago


def _bloquear(
    proyecto: ProyectoConstruccion, *, exigir: list[str], accion: str
) -> ProyectoConstruccion:
    """
    Bloquea la fila del proyecto y comprueba su estado (spec 017, §6). Así dos
    peticiones que inician o finalizan a la vez no pasan las dos: la segunda
    espera y lee el estado que dejó la primera.
    """
    proyecto = ProyectoConstruccion.objects.select_for_update().get(pk=proyecto.pk)
    if proyecto.estado not in exigir:
        raise TransicionInvalida(
            codigo=proyecto.codigo, estado=proyecto.estado, accion=accion
        )
    return proyecto


def _cambiar_estado(
    proyecto: ProyectoConstruccion,
    nuevo: str,
    *,
    autor: Usuario,
    ip: str | None,
    motivo: str | None = None,
    accion: str = AccionAuditoria.ACTUALIZAR,
    extra: dict | None = None,
    otros_campos: list[str] | None = None,
) -> ProyectoConstruccion:
    """
    Guarda el estado nuevo y lo audita con el anterior y lo propio de la acción
    (el motivo, la fecha de fin real). otros_campos son los que la acción ya
    cambió en el proyecto y hay que guardar junto con el estado.
    """
    anterior = proyecto.estado
    proyecto.estado = nuevo
    proyecto.actualizado_por = autor
    proyecto.save(
        update_fields=[
            "estado",
            *(otros_campos or []),
            "actualizado_por",
            "actualizado_en",
        ]
    )
    nuevos = {"estado": nuevo, **(extra or {})}
    if motivo is not None:
        nuevos["motivo"] = motivo
    registrar_auditoria(
        usuario=autor,
        entidad=ENTIDAD_PROYECTO,
        entidad_id=proyecto.pk,
        accion=accion,
        valores_anteriores={"estado": anterior},
        valores_nuevos=nuevos,
        ip=ip,
    )
    return proyecto


def _campos_editables(proyecto: ProyectoConstruccion) -> list[str]:
    """Qué se puede editar según el estado (regla 17)."""
    if proyecto.estado in ESTADOS_ACTIVOS:
        return ["nombre", "fecha_fin_estimada", "presupuesto_total"]
    if proyecto.estado == EstadoProyecto.FINALIZADO:
        return ["presupuesto_total"]
    return []


def _validar_fechas(inicio: date, fin_estimada: date) -> None:
    if fin_estimada < inicio:
        raise FechaInvalida(
            campo="fecha_fin_estimada",
            mensaje="La fecha de fin estimada no puede ser anterior a la de inicio.",
        )


def _tasa_a_dolar(*, moneda, fecha: date) -> Decimal:
    """
    Tasa de la moneda al dólar vigente en la fecha (regla 11), como en ventas
    y compras. Sin tasa registrada, o sin el dólar, TIPO_CAMBIO_NO_DISPONIBLE.
    """
    dolar = obtener_dolar()
    if dolar is None:
        raise TipoCambioNoDisponible(origen=moneda.codigo, destino="USD", fecha=fecha)
    return obtener_tipo_cambio(origen=moneda, destino=dolar, fecha=fecha)


def _a_centavos(valor: Decimal) -> Decimal:
    """Redondeo comercial a dos decimales, el mismo de ventas y compras."""
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def cargar_demo_construccion() -> dict[str, int]:
    """
    Carga las constructoras, los proyectos y los pagos ficticios de
    datos_demo.py y devuelve cuántos creó de cada uno.

    Es idempotente: busca cada una por su país y su NIT y solo crea lo que
    falta. Si un país no existe todavía, esa constructora se omite. No registra
    auditoría: es la foto inicial de la demostración (mismo criterio que la
    spec 004).
    """
    paises = {pais.codigo_iso: pais for pais in listar_paises()}
    creadas = 0
    for (
        nombre,
        nit,
        contacto,
        email,
        codigo_pais,
        calificacion,
    ) in datos_demo.CONSTRUCTORAS:
        pais = paises.get(codigo_pais)
        nit = normalizar_documento(nit)
        if pais is None or Constructora.objects.filter(pais=pais, nit=nit).exists():
            continue
        constructora = Constructora.objects.create(
            nombre=nombre,
            nit=nit,
            contacto=contacto,
            email=email,
            pais=pais,
            calificacion=calificacion,
        )
        constructora.codigo = f"CST-{constructora.pk:04d}"
        constructora.save(update_fields=["codigo"])
        creadas += 1
    proyectos, pagos = _cargar_proyectos_demo()
    return {"constructoras": creadas, "proyectos": proyectos, "pagos": pagos}


def _cargar_proyectos_demo() -> tuple[int, int]:
    """
    Proyectos y pagos de la demostración (spec 017). Devuelve cuántos creó de
    cada uno.

    Son una foto, como el resto de la demo: se guardan con el estado que ya
    tienen sus propiedades en la demo del catálogo (el hotel en obra, la
    gasolinera adquirida), sin pasar por iniciar ni cambiar el estado de nada,
    y sin auditoría. Calculan su tasa y sus montos en dólares igual que los
    servicios, y los pagos de cada proyecto caben en su presupuesto (regla 19).

    Se salta un proyecto si su propiedad o su constructora no existen, si la
    propiedad ya tiene un proyecto activo (así no duplica), o si falta la tasa.
    Los pagos solo se crean junto con su proyecto.
    """
    hoy = timezone.localdate()
    proyectos = pagos = 0
    for datos in datos_demo.PROYECTOS:
        propiedad = listar_propiedades().filter(nombre=datos["propiedad"]).first()
        nit = normalizar_documento(datos["constructora_nit"])
        constructora = Constructora.objects.filter(nit=nit).first()
        if propiedad is None or constructora is None:
            continue
        if existe_proyecto_activo(propiedad=propiedad):
            continue
        inicio = hoy + timedelta(days=datos["dias_inicio"])
        moneda = propiedad.moneda
        try:
            tasa = _tasa_a_dolar(moneda=moneda, fecha=inicio)
            tasas_pago = {
                dias_pago: _tasa_a_dolar(
                    moneda=moneda, fecha=hoy + timedelta(days=dias_pago)
                )
                for _, _, _, dias_pago in datos["pagos"]
                if dias_pago is not None
            }
        except ErrorDominio:
            continue
        presupuesto = Decimal(datos["presupuesto_total"])
        proyecto = ProyectoConstruccion.objects.create(
            nombre=datos["nombre"],
            propiedad=propiedad,
            constructora=constructora,
            fecha_inicio=inicio,
            fecha_fin_estimada=hoy + timedelta(days=datos["dias_fin_estimada"]),
            presupuesto_total=presupuesto,
            moneda=moneda,
            tasa_a_usd=tasa,
            presupuesto_total_usd=_a_centavos(presupuesto * tasa),
            estado=datos["estado"],
            porcentaje_avance=datos["porcentaje_avance"],
        )
        proyecto.codigo = f"PC-{proyecto.pk:05d}"
        proyecto.save(update_fields=["codigo"])
        proyectos += 1

        for tipo, monto, dias_programada, dias_pago in datos["pagos"]:
            monto = Decimal(monto)
            pagado = dias_pago is not None
            pago = PagoConstructora.objects.create(
                proyecto=proyecto,
                tipo=tipo,
                monto=monto,
                moneda=moneda,
                fecha_programada=hoy + timedelta(days=dias_programada),
                estado=EstadoPago.PAGADO if pagado else EstadoPago.PROGRAMADO,
                fecha_pago=hoy + timedelta(days=dias_pago) if pagado else None,
                referencia_pago=f"DEMO-{proyecto.pk}-{pagos + 1}" if pagado else "",
                tasa_a_usd=tasas_pago[dias_pago] if pagado else None,
                monto_usd=_a_centavos(monto * tasas_pago[dias_pago])
                if pagado
                else None,
            )
            pago.codigo = f"PG-{pago.pk:05d}"
            pago.save(update_fields=["codigo"])
            pagos += 1
    return proyectos, pagos


def _validar(datos: dict) -> None:
    if not datos["nit"]:
        raise NitObligatorio()


def _validar_no_duplicado(*, pais, nit: str, excluir_id: int | None = None) -> None:
    if existe_constructora_con_nit(pais=pais, nit=nit, excluir_id=excluir_id):
        raise ConstructoraDuplicada(nit=nit, pais=pais.nombre)


def _foto(constructora: Constructora, campos: list[str] | None = None) -> dict:
    """Valores para la bitácora; el país queda como su id."""
    return model_to_dict(constructora, fields=campos or ["codigo", *CAMPOS_EDITABLES])
