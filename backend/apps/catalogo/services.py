"""Servicios de catálogo: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models, transaction
from django.forms.models import model_to_dict

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.selectors import listar_ciudades, listar_monedas

from . import datos_demo
from .enums import EstadoPropiedad
from .exceptions import PropiedadConUnidades, TipoSinUnidades, UnidadDuplicada
from .models import Propiedad, TipoPropiedad, Unidad
from .selectors import (
    contar_unidades_activas,
    existe_unidad,
    listar_tipos_propiedad,
)

# Campos que se pueden editar. Quedan fuera codigo (lo genera el sistema),
# estado (solo cambia por cambiar_estado_propiedad, regla 7), activo (solo
# cambia al desactivar) y los campos de rastro.
CAMPOS_TIPO = ["nombre", "descripcion", "requiere_unidades"]
CAMPOS_PROPIEDAD = [
    "nombre",
    "tipo",
    "ciudad",
    "direccion",
    "latitud",
    "longitud",
    "area_m2",
    "area_construida_m2",
    "precio_lista",
    "moneda",
    "es_publica",
    "descripcion",
]
# La propiedad de una unidad no se cambia: se desactiva y se crea otra.
CAMPOS_UNIDAD = [
    "codigo",
    "nivel",
    "area_m2",
    "habitaciones",
    "banos",
    "estado",
    "precio_lista",
    "moneda",
]


# --- Ayudantes comunes a los tres modelos -----------------------------------
#
# Crear, editar y desactivar siguen los mismos pasos en los tres modelos. Se
# escriben una vez aquí y cada servicio público agrega solo su regla propia.


def _valores(instancia: models.Model, campos: list[str]) -> dict:
    """
    Los campos como se guardan en la bitácora. model_to_dict entrega el id de
    las llaves foráneas (ciudad: 3), no el objeto, que no cabe en JSON.
    """
    return model_to_dict(instancia, fields=campos)


def _auditar(
    *,
    instancia: models.Model,
    accion: AccionAuditoria,
    autor: AbstractBaseUser | None,
    ip: str | None,
    anteriores: dict | None = None,
    nuevos: dict | None = None,
) -> None:
    registrar_auditoria(
        usuario=autor,
        entidad=instancia._meta.db_table,
        entidad_id=instancia.pk,
        accion=accion,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
        ip=ip,
    )


def _crear(
    modelo: type[models.Model],
    *,
    datos: dict,
    campos: list[str],
    autor: AbstractBaseUser,
    ip: str | None,
) -> models.Model:
    """Inserta con los campos permitidos y audita CREAR con lo guardado."""
    instancia = modelo(
        **{campo: datos[campo] for campo in campos if campo in datos},
        creado_por=autor,
        actualizado_por=autor,
    )
    instancia.save()
    _auditar(
        instancia=instancia,
        accion=AccionAuditoria.CREAR,
        autor=autor,
        ip=ip,
        nuevos=_valores(instancia, campos),
    )
    return instancia


def _actualizar(
    instancia: models.Model,
    *,
    datos: dict,
    campos: list[str],
    autor: AbstractBaseUser,
    ip: str | None,
) -> models.Model:
    """
    Aplica solo los campos permitidos y audita ACTUALIZAR con los que cambian,
    antes y después. Si nada cambia, no escribe ni audita: un PATCH con los
    mismos valores no es una modificación.
    """
    anteriores = _valores(instancia, campos)
    for campo in campos:
        if campo in datos:
            setattr(instancia, campo, datos[campo])
    nuevos = _valores(instancia, campos)
    cambiados = [campo for campo in campos if anteriores[campo] != nuevos[campo]]
    if not cambiados:
        return instancia

    instancia.actualizado_por = autor
    # actualizado_en tiene auto_now, pero con update_fields solo se guarda si
    # se nombra.
    instancia.save(update_fields=[*cambiados, "actualizado_por", "actualizado_en"])
    _auditar(
        instancia=instancia,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        anteriores={campo: anteriores[campo] for campo in cambiados},
        nuevos={campo: nuevos[campo] for campo in cambiados},
    )
    return instancia


def _desactivar(
    instancia: models.Model, *, autor: AbstractBaseUser, ip: str | None
) -> None:
    """Borrado lógico (CLAUDE.md §7), auditado como ELIMINAR."""
    instancia.activo = False
    instancia.actualizado_por = autor
    instancia.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
    _auditar(
        instancia=instancia,
        accion=AccionAuditoria.ELIMINAR,
        autor=autor,
        ip=ip,
        anteriores={"activo": True},
        nuevos={"activo": False},
    )


# --- Tipos de propiedad -----------------------------------------------------


@transaction.atomic
def crear_tipo_propiedad(
    *, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> TipoPropiedad:
    """Agrega un tipo a los siete que crea la migración."""
    return _crear(TipoPropiedad, datos=datos, campos=CAMPOS_TIPO, autor=autor, ip=ip)


@transaction.atomic
def actualizar_tipo_propiedad(
    *, tipo: TipoPropiedad, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> TipoPropiedad:
    """Edita nombre, descripción o si el tipo admite unidades."""
    return _actualizar(tipo, datos=datos, campos=CAMPOS_TIPO, autor=autor, ip=ip)


@transaction.atomic
def desactivar_tipo_propiedad(
    *, tipo: TipoPropiedad, autor: AbstractBaseUser, ip: str | None
) -> None:
    """
    Deja de ofrecer el tipo para propiedades nuevas. Las que ya lo tienen lo
    conservan: el tipo no se borra de la base.
    """
    _desactivar(tipo, autor=autor, ip=ip)


# --- Propiedades ------------------------------------------------------------


@transaction.atomic
def crear_propiedad(
    *, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Propiedad:
    """
    Registra una propiedad en EN_NEGOCIACION (regla 7) y le asigna PROP-NNNNN.

    Regla 3: el código sale del id, y el id solo existe después de insertar.
    Por eso se inserta con el código nulo, se asigna y luego se audita, para
    que la bitácora guarde el código final y no un nulo. Todo va en la misma
    transacción: nadie llega a ver la propiedad sin código.
    """
    propiedad = Propiedad(
        **{campo: datos[campo] for campo in CAMPOS_PROPIEDAD if campo in datos},
        creado_por=autor,
        actualizado_por=autor,
    )
    propiedad.save()
    propiedad.codigo = f"PROP-{propiedad.pk:05d}"
    propiedad.save(update_fields=["codigo"])
    _auditar(
        instancia=propiedad,
        accion=AccionAuditoria.CREAR,
        autor=autor,
        ip=ip,
        # codigo va aparte porque model_to_dict omite los campos con
        # editable=False.
        nuevos={
            "codigo": propiedad.codigo,
            **_valores(propiedad, ["estado", *CAMPOS_PROPIEDAD]),
        },
    )
    return propiedad


@transaction.atomic
def actualizar_propiedad(
    *, propiedad: Propiedad, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Propiedad:
    """
    Edita los datos de la propiedad. Ignora codigo y estado aunque vengan en
    datos: el estado cambia solo con cambiar_estado_propiedad (regla 7).
    """
    return _actualizar(
        propiedad, datos=datos, campos=CAMPOS_PROPIEDAD, autor=autor, ip=ip
    )


@transaction.atomic
def desactivar_propiedad(
    *, propiedad: Propiedad, autor: AbstractBaseUser, ip: str | None
) -> None:
    """
    Regla 6: borrado lógico, y solo si no tiene unidades activas. Si se
    permitiera, quedarían unidades vivas colgando de una propiedad dada de baja.
    """
    unidades_activas = contar_unidades_activas(propiedad=propiedad)
    if unidades_activas:
        raise PropiedadConUnidades(
            propiedad=propiedad.codigo, unidades_activas=unidades_activas
        )
    _desactivar(propiedad, autor=autor, ip=ip)


@transaction.atomic
def cambiar_estado_propiedad(
    *,
    propiedad: Propiedad,
    estado: EstadoPropiedad,
    autor: AbstractBaseUser | None,
    ip: str | None,
    motivo: str,
) -> Propiedad:
    """
    Punto único de cambio de estado (regla 7). Lo usan la vista
    /cambiar-estado/ y los servicios de ventas, arrendamientos, compras y
    construcción. autor es None cuando lo hace el sistema.

    Audita ACTUALIZAR con el estado anterior, el nuevo y el motivo. Si el
    estado no cambia, no escribe ni audita.

    select_for_update bloquea la fila hasta el fin de la transacción: si una
    venta y un arrendamiento cambian la misma propiedad a la vez, el segundo
    espera y lee el estado que dejó el primero, en vez de pisarlo.
    """
    propiedad = Propiedad.objects.select_for_update().get(pk=propiedad.pk)
    anterior = propiedad.estado
    if anterior == estado:
        return propiedad

    propiedad.estado = estado
    propiedad.actualizado_por = autor
    propiedad.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    _auditar(
        instancia=propiedad,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        anteriores={"estado": anterior},
        nuevos={"estado": estado, "motivo": motivo},
    )
    return propiedad


# --- Unidades ---------------------------------------------------------------


@transaction.atomic
def crear_unidad(
    *, propiedad: Propiedad, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Unidad:
    """
    Agrega una unidad a una propiedad cuyo tipo las admite (regla 2), con un
    código que no se repita dentro de la propiedad (regla 3).

    El duplicado se revisa antes de insertar para responder 409 con un mensaje
    claro; la restricción única de la base sigue siendo la garantía final.
    """
    if not propiedad.tipo.requiere_unidades:
        raise TipoSinUnidades(tipo=propiedad.tipo.nombre)
    if existe_unidad(propiedad=propiedad, codigo=datos["codigo"]):
        raise UnidadDuplicada(propiedad=propiedad.codigo, unidad=datos["codigo"])
    return _crear(
        Unidad,
        datos={**datos, "propiedad": propiedad},
        campos=["propiedad", *CAMPOS_UNIDAD],
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def actualizar_unidad(
    *, unidad: Unidad, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Unidad:
    """Edita la unidad. Si cambia el código, revisa que no se repita (regla 3)."""
    codigo = datos.get("codigo", unidad.codigo)
    if codigo != unidad.codigo and existe_unidad(
        propiedad=unidad.propiedad, codigo=codigo, excluir_id=unidad.pk
    ):
        raise UnidadDuplicada(propiedad=unidad.propiedad.codigo, unidad=codigo)
    return _actualizar(unidad, datos=datos, campos=CAMPOS_UNIDAD, autor=autor, ip=ip)


@transaction.atomic
def desactivar_unidad(
    *, unidad: Unidad, autor: AbstractBaseUser, ip: str | None
) -> None:
    """Borrado lógico de la unidad."""
    _desactivar(unidad, autor=autor, ip=ip)


# --- Datos de demostración --------------------------------------------------


@transaction.atomic
def cargar_demo_catalogo() -> dict[str, int]:
    """
    Carga las propiedades y unidades ficticias de datos_demo.py y devuelve
    cuántas creó de cada una.

    Es idempotente, como cargar_catalogos_demo de core: busca cada propiedad
    por su nombre y cada unidad por su código, y solo crea lo que falta. Nunca
    modifica lo que ya existe, así que correrlo en cada arranque (spec 002,
    §5.8) no duplica nada ni deshace cambios hechos desde la API.

    Necesita las ciudades y monedas de demostración de core; seed_demo las
    carga antes.

    Asigna el estado directamente y no con cambiar_estado_propiedad, y no
    registra auditoría (spec 003, §7): es la foto inicial de la demostración,
    no una operación del negocio.
    """
    creados = {"propiedades": 0, "unidades": 0}

    for datos in datos_demo.PROPIEDADES:
        codigo_pais, nombre_ciudad = datos["ciudad"]
        propiedad, creada = Propiedad.objects.get_or_create(
            nombre=datos["nombre"],
            defaults={
                "tipo": listar_tipos_propiedad().get(nombre=datos["tipo"]),
                "ciudad": listar_ciudades().get(
                    pais__codigo_iso=codigo_pais, nombre=nombre_ciudad
                ),
                "direccion": datos["direccion"],
                "area_m2": datos["area_m2"],
                "area_construida_m2": datos["area_construida_m2"],
                "precio_lista": datos["precio_lista"],
                "moneda": listar_monedas().get(codigo=datos["moneda"]),
                "estado": datos["estado"],
                "es_publica": datos["es_publica"],
                "descripcion": datos["descripcion"],
            },
        )
        if creada:
            # Mismo formato que crear_propiedad (regla 3).
            propiedad.codigo = f"PROP-{propiedad.pk:05d}"
            propiedad.save(update_fields=["codigo"])
            creados["propiedades"] += 1

        unidades = datos_demo.UNIDADES.get(datos["nombre"], [])
        for codigo, nivel, area, habitaciones, banos, precio, estado in unidades:
            _, creada = Unidad.objects.get_or_create(
                propiedad=propiedad,
                codigo=codigo,
                defaults={
                    "nivel": nivel,
                    "area_m2": area,
                    "habitaciones": habitaciones,
                    "banos": banos,
                    "precio_lista": precio,
                    "moneda": propiedad.moneda,
                    "estado": estado,
                },
            )
            if creada:
                creados["unidades"] += 1

    return creados
