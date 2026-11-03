"""Servicios de catálogo: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from contextlib import suppress
from pathlib import Path

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import models, transaction
from django.db.models.fields.files import FieldFile
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.selectors import listar_ciudades, listar_monedas

from . import datos_demo
from .enums import EstadoPropiedad
from .exceptions import (
    ArchivoNoPermitido,
    DocumentoDeOtraPropiedad,
    DocumentoEnUso,
    FechaAvaluoFutura,
    LimiteImagenes,
    PropiedadConUnidades,
    PropiedadNoDisponible,
    TipoSinUnidades,
    UnidadDuplicada,
)
from .models import (
    TAMANO_MAXIMO_DOCUMENTO,
    TAMANO_MAXIMO_IMAGEN,
    Avaluo,
    DocumentoOficial,
    ImagenPropiedad,
    Propiedad,
    TipoPropiedad,
    Unidad,
    ruta_documento,
    ruta_imagen,
)
from .selectors import (
    avaluo_activo_usa_documento,
    contar_imagenes_activas,
    contar_unidades_activas,
    existe_unidad,
    listar_tipos_propiedad,
    obtener_portada,
    primera_imagen_sin_portada,
    siguiente_orden_imagen,
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
# La propiedad de una unidad no se cambia: se desactiva y se crea otra. Su
# estado, como el de la propiedad, solo cambia con cambiar_estado_unidad.
CAMPOS_UNIDAD = [
    "codigo",
    "nivel",
    "area_m2",
    "habitaciones",
    "banos",
    "precio_lista",
    "moneda",
]
# Un avalúo no se edita (regla 3): estos campos solo se usan al registrarlo.
CAMPOS_AVALUO = [
    "propiedad",
    "fecha",
    "valor",
    "moneda",
    "perito",
    "metodologia",
    "documento",
    "observaciones",
]
# El archivo no se reemplaza (regla 7): al crear se arma en el servicio y al
# editar solo cambian estos cuatro campos.
CAMPOS_DOCUMENTO = [
    "propiedad",
    "tipo",
    "nombre",
    "archivo",
    "nombre_original",
    "tipo_contenido",
    "tamano_bytes",
    "fecha_emision",
    "fecha_vencimiento",
    "emisor",
]
CAMPOS_DOCUMENTO_EDITABLES = [
    "nombre",
    "fecha_emision",
    "fecha_vencimiento",
    "emisor",
]
SEGUNDOS_URL_DESCARGA = 300

# Regla 6: el tipo se deduce de los primeros bytes, no del nombre del archivo.
# La extensión es la que se usa al guardarlo: un PNG llamado .txt se guarda
# como .png.
FIRMAS_ARCHIVO = {
    "pdf": (b"%PDF-", "application/pdf"),
    "jpg": (b"\xff\xd8\xff", "image/jpeg"),
    "png": (b"\x89PNG\r\n\x1a\n", "image/png"),
}
# Spec 019, regla 1: una foto es JPG o PNG, con las mismas firmas.
FIRMAS_IMAGEN = {extension: FIRMAS_ARCHIVO[extension] for extension in ("jpg", "png")}
MAXIMO_IMAGENES = 10
# Al subir, el archivo y lo que se audita se arman en el servicio; al editar
# solo cambian estos dos campos (regla 4).
CAMPOS_IMAGEN = [
    "propiedad",
    "archivo",
    "nombre_original",
    "tipo_contenido",
    "tamano_bytes",
    "descripcion",
    "orden",
    "es_portada",
]
CAMPOS_IMAGEN_EDITABLES = ["descripcion", "orden"]


# --- Ayudantes comunes a los modelos de catálogo -----------------------------
#
# Crear, editar y desactivar siguen los mismos pasos en todos los modelos. Se
# escriben una vez aquí y cada servicio público agrega solo su regla propia.


def _valores(instancia: models.Model, campos: list[str]) -> dict:
    """
    Los campos como se guardan en la bitácora. model_to_dict entrega el id de
    las llaves foráneas (ciudad: 3), no el objeto, que no cabe en JSON. Un
    FileField se guarda como la ruta, nunca con el contenido del archivo.
    """
    return {
        campo: valor.name if isinstance(valor, FieldFile) else valor
        for campo, valor in model_to_dict(instancia, fields=campos).items()
    }


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


def _cambiar_estado(
    modelo: type[models.Model],
    *,
    instancia_id: int,
    estado: EstadoPropiedad,
    autor: AbstractBaseUser | None,
    ip: str | None,
    motivo: str,
    estado_requerido: EstadoPropiedad | None = None,
) -> models.Model:
    """
    Pasos comunes de cambiar_estado_propiedad y cambiar_estado_unidad.

    select_for_update bloquea la fila hasta el fin de la transacción: si una
    venta y un arrendamiento cambian la misma propiedad a la vez, el segundo
    espera y lee el estado que dejó el primero, en vez de pisarlo.

    Audita ACTUALIZAR con el estado anterior, el nuevo y el motivo. Si el
    estado no cambia, no escribe ni audita.

    Con estado_requerido, el estado actual se comprueba después de bloquear la
    fila: comprobar y cambiar quedan en el mismo paso. Si se comprobara antes
    del bloqueo, dos aprobaciones simultáneas de cotizaciones sobre la misma
    propiedad podrían pasar las dos (spec 007, regla 5).
    """
    instancia = modelo.objects.select_for_update().get(pk=instancia_id)
    anterior = instancia.estado
    if estado_requerido is not None and anterior != estado_requerido:
        raise PropiedadNoDisponible(
            codigo=str(instancia.codigo),
            estado_actual=anterior,
            estado_requerido=estado_requerido,
        )
    if anterior == estado:
        return instancia

    instancia.estado = estado
    instancia.actualizado_por = autor
    instancia.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    _auditar(
        instancia=instancia,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
        anteriores={"estado": anterior},
        nuevos={"estado": estado, "motivo": motivo},
    )
    return instancia


@transaction.atomic
def cambiar_estado_propiedad(
    *,
    propiedad: Propiedad,
    estado: EstadoPropiedad,
    autor: AbstractBaseUser | None,
    ip: str | None,
    motivo: str,
    estado_requerido: EstadoPropiedad | None = None,
) -> Propiedad:
    """
    Punto único de cambio de estado de una propiedad (regla 7). Lo usan la
    vista /cambiar-estado/ y los servicios de ventas, arrendamientos, compras y
    construcción. autor es None cuando lo hace el sistema.
    """
    return _cambiar_estado(
        Propiedad,
        instancia_id=propiedad.pk,
        estado=estado,
        autor=autor,
        ip=ip,
        motivo=motivo,
        estado_requerido=estado_requerido,
    )


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
def cambiar_estado_unidad(
    *,
    unidad: Unidad,
    estado: EstadoPropiedad,
    autor: AbstractBaseUser | None,
    ip: str | None,
    motivo: str,
    estado_requerido: EstadoPropiedad | None = None,
) -> Unidad:
    """
    Punto único de cambio de estado de una unidad (regla 7), con el mismo
    bloqueo y la misma auditoría que cambiar_estado_propiedad. Lo pidió la spec
    de ventas: en un edificio se vende o arrienda cada apartamento por
    separado, no el edificio.

    No toca el estado de la propiedad: si vender el último apartamento debe
    cambiar el del edificio, lo decide el servicio de ventas que lo llama.
    """
    return _cambiar_estado(
        Unidad,
        instancia_id=unidad.pk,
        estado=estado,
        autor=autor,
        ip=ip,
        motivo=motivo,
        estado_requerido=estado_requerido,
    )


@transaction.atomic
def desactivar_unidad(
    *, unidad: Unidad, autor: AbstractBaseUser, ip: str | None
) -> None:
    """Borrado lógico de la unidad."""
    _desactivar(unidad, autor=autor, ip=ip)


# --- Avalúos ----------------------------------------------------------------


@transaction.atomic
def registrar_avaluo(
    *, propiedad: Propiedad, datos: dict, autor: AbstractBaseUser, ip: str | None
) -> Avaluo:
    """
    Registra un avalúo de la propiedad (regla 1).

    Valida la fecha no futura (regla 2) y que el documento adjunto, si lo hay,
    sea de la misma propiedad (regla 4). El avalúo nunca se edita: si hay un
    error, se desactiva y se registra el correcto (regla 3).
    """
    if datos["fecha"] > timezone.localdate():
        raise FechaAvaluoFutura()

    documento = datos.get("documento")
    if documento is not None and documento.propiedad_id != propiedad.pk:
        raise DocumentoDeOtraPropiedad(
            documento=documento.nombre,
            propiedad=propiedad.codigo,
            propiedad_documento=documento.propiedad.codigo,
        )

    return _crear(
        Avaluo,
        datos={**datos, "propiedad": propiedad},
        campos=CAMPOS_AVALUO,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def desactivar_avaluo(
    *, avaluo: Avaluo, autor: AbstractBaseUser, ip: str | None
) -> None:
    """Borrado lógico del avalúo (regla 3), auditado como ELIMINAR."""
    _desactivar(avaluo, autor=autor, ip=ip)


# --- Documentos oficiales ---------------------------------------------------


def _validar_archivo(
    archivo: UploadedFile,
    *,
    firmas: dict[str, tuple[bytes, str]] = FIRMAS_ARCHIVO,
    tamano_maximo: int = TAMANO_MAXIMO_DOCUMENTO,
) -> tuple[str, str, int]:
    """
    Regla 6 de la spec 011: devuelve (tipo de contenido, extensión, tamaño) si
    el archivo es de uno de los tipos de firmas y no pasa de tamano_maximo. Por
    omisión, PDF, JPG o PNG de hasta 10 MB; las imágenes (spec 019, regla 1)
    pasan solo JPG y PNG y 5 MB. Mira los primeros bytes y vuelve a dejar el
    puntero al inicio para poder guardarlo después.
    """
    tamano = archivo.size
    if tamano <= 0 or tamano > tamano_maximo:
        megas = tamano_maximo // (1024 * 1024)
        raise ArchivoNoPermitido(
            motivo=f"El archivo debe pesar entre 1 byte y {megas} MB."
        )

    encabezado = archivo.read(16)
    archivo.seek(0)
    for extension, (firma, tipo_contenido) in firmas.items():
        if encabezado.startswith(firma):
            return tipo_contenido, extension, tamano

    # "PDF, JPG o PNG" o "JPG o PNG", según los tipos aceptados.
    nombres = [extension.upper() for extension in firmas]
    aceptados = ", ".join(nombres[:-1]) + f" o {nombres[-1]}"
    raise ArchivoNoPermitido(motivo=f"Solo se aceptan archivos {aceptados}.")


@transaction.atomic
def subir_documento(
    *,
    propiedad: Propiedad,
    archivo: UploadedFile,
    datos: dict,
    autor: AbstractBaseUser,
    ip: str | None,
) -> DocumentoOficial:
    """
    Sube el archivo y registra el documento (reglas 5 a 8).

    El almacenamiento no participa en la transacción de la base, así que se
    sube primero y, si el registro falla, se intenta borrar el archivo para no
    dejar uno huérfano (spec 011, §6).
    """
    tipo_contenido, extension, tamano = _validar_archivo(archivo)
    nombre_original = Path(archivo.name).name
    archivo.name = f"documento.{extension}"

    ruta = ruta_documento(DocumentoOficial(propiedad=propiedad), archivo.name)
    guardado = default_storage.save(ruta, archivo)

    try:
        return _crear(
            DocumentoOficial,
            datos={
                **datos,
                "propiedad": propiedad,
                "archivo": guardado,
                "nombre_original": nombre_original,
                "tipo_contenido": tipo_contenido,
                "tamano_bytes": tamano,
            },
            campos=CAMPOS_DOCUMENTO,
            autor=autor,
            ip=ip,
        )
    except Exception:
        # Si además falla el borrado, queda un archivo huérfano, nunca un
        # registro que apunte a un archivo inexistente. El error original se
        # propaga igual.
        with suppress(Exception):
            default_storage.delete(guardado)
        raise


@transaction.atomic
def actualizar_documento(
    *,
    documento: DocumentoOficial,
    datos: dict,
    autor: AbstractBaseUser,
    ip: str | None,
) -> DocumentoOficial:
    """Edita nombre, fechas y emisor; el archivo no se reemplaza (regla 7)."""
    return _actualizar(
        documento,
        datos=datos,
        campos=CAMPOS_DOCUMENTO_EDITABLES,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def desactivar_documento(
    *, documento: DocumentoOficial, autor: AbstractBaseUser, ip: str | None
) -> None:
    """
    Borrado lógico (regla 9). El archivo no se borra y un documento que
    respalda un avalúo activo no se puede desactivar.
    """
    if avaluo_activo_usa_documento(documento=documento):
        raise DocumentoEnUso(documento=documento.nombre)
    _desactivar(documento, autor=autor, ip=ip)


def generar_url_descarga(*, documento: DocumentoOficial) -> str:
    """
    Regla 10: URL firmada de 5 minutos con S3. En desarrollo y pruebas el
    almacenamiento es local y devuelve la ruta de media, sin firma.
    """
    return default_storage.url(documento.archivo.name)


# --- Imágenes de las propiedades (spec 019) ---------------------------------


def _bloquear_propiedad(propiedad: Propiedad) -> Propiedad:
    """
    Bloquea la fila de la propiedad hasta el fin de la transacción. Así dos
    subidas al mismo tiempo no pasan juntas del límite de 10 (regla 2), y la
    portada no se mueve en dos pasos cruzados (regla 6): la segunda petición
    espera y lee lo que dejó la primera.
    """
    return Propiedad.objects.select_for_update().get(pk=propiedad.pk)


@transaction.atomic
def subir_imagen(
    *,
    propiedad: Propiedad,
    archivo: UploadedFile,
    descripcion: str,
    autor: AbstractBaseUser,
    ip: str | None,
) -> ImagenPropiedad:
    """
    Sube una foto a la galería (reglas 1 a 3, 6 y 7).

    La primera imagen de la propiedad queda como portada y cada imagen nueva va
    al final de la galería. Como en los documentos, el archivo se sube antes
    de crear el registro y se intenta borrar si el registro falla.
    """
    tipo_contenido, extension, tamano = _validar_archivo(
        archivo, firmas=FIRMAS_IMAGEN, tamano_maximo=TAMANO_MAXIMO_IMAGEN
    )
    _bloquear_propiedad(propiedad)
    activas = contar_imagenes_activas(propiedad=propiedad)
    if activas >= MAXIMO_IMAGENES:
        raise LimiteImagenes(propiedad=propiedad.codigo, maximo=MAXIMO_IMAGENES)

    nombre_original = Path(archivo.name).name
    archivo.name = f"imagen.{extension}"
    ruta = ruta_imagen(ImagenPropiedad(propiedad=propiedad), archivo.name)
    guardado = default_storage.save(ruta, archivo)

    try:
        return _crear(
            ImagenPropiedad,
            datos={
                "propiedad": propiedad,
                "archivo": guardado,
                "nombre_original": nombre_original,
                "tipo_contenido": tipo_contenido,
                "tamano_bytes": tamano,
                "descripcion": descripcion,
                "orden": siguiente_orden_imagen(propiedad=propiedad),
                "es_portada": activas == 0,
            },
            campos=CAMPOS_IMAGEN,
            autor=autor,
            ip=ip,
        )
    except Exception:
        with suppress(Exception):
            default_storage.delete(guardado)
        raise


@transaction.atomic
def actualizar_imagen(
    *,
    imagen: ImagenPropiedad,
    datos: dict,
    autor: AbstractBaseUser,
    ip: str | None,
) -> ImagenPropiedad:
    """Edita la descripción y el orden; el archivo no se reemplaza (regla 4)."""
    return _actualizar(
        imagen, datos=datos, campos=CAMPOS_IMAGEN_EDITABLES, autor=autor, ip=ip
    )


@transaction.atomic
def marcar_portada(
    *, imagen: ImagenPropiedad, autor: AbstractBaseUser, ip: str | None
) -> ImagenPropiedad:
    """
    Regla 6: la elegida pasa a ser la portada y la anterior deja de serlo, en
    la misma transacción. Primero se quita la marca de la anterior: si se
    pusiera antes la nueva, el constraint de una sola portada lo rechazaría.
    """
    _bloquear_propiedad(imagen.propiedad)
    anterior = obtener_portada(propiedad=imagen.propiedad)
    if anterior is not None and anterior.pk == imagen.pk:
        return imagen
    if anterior is not None:
        _actualizar(
            anterior,
            datos={"es_portada": False},
            campos=["es_portada"],
            autor=autor,
            ip=ip,
        )
    return _actualizar(
        imagen, datos={"es_portada": True}, campos=["es_portada"], autor=autor, ip=ip
    )


@transaction.atomic
def desactivar_imagen(
    *, imagen: ImagenPropiedad, autor: AbstractBaseUser, ip: str | None
) -> None:
    """
    Borrado lógico; el archivo no se borra (regla 5). Si era la portada, la
    marca pasa a la primera de la galería según el orden; si no queda
    ninguna, la propiedad se queda sin portada (regla 6).
    """
    _bloquear_propiedad(imagen.propiedad)
    _desactivar(imagen, autor=autor, ip=ip)
    if not imagen.es_portada:
        return
    siguiente = primera_imagen_sin_portada(propiedad=imagen.propiedad)
    if siguiente is not None:
        _actualizar(
            siguiente,
            datos={"es_portada": True},
            campos=["es_portada"],
            autor=autor,
            ip=ip,
        )


# --- Datos de demostración --------------------------------------------------


@transaction.atomic
def cargar_demo_catalogo() -> dict[str, int]:
    """
    Carga las propiedades, unidades y avalúos ficticios de datos_demo.py y
    devuelve cuántos creó de cada uno.

    Es idempotente, como cargar_catalogos_demo de core: busca cada propiedad
    por su nombre, cada unidad por su código y cada avalúo por su propiedad,
    fecha y perito, y solo crea lo que falta. Nunca modifica lo que ya existe,
    así que correrlo en cada arranque (spec 002, §5.8) no duplica nada ni
    deshace cambios hechos desde la API.

    Necesita las ciudades y monedas de demostración de core; seed_demo las
    carga antes.

    Asigna el estado directamente y no con cambiar_estado_propiedad, y no
    registra auditoría (spec 003, §7): es la foto inicial de la demostración,
    no una operación del negocio.
    """
    creados = {"propiedades": 0, "unidades": 0, "avaluos": 0}

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

        avaluos = datos_demo.AVALUOS.get(datos["nombre"], [])
        for fecha, valor, perito, metodologia, observaciones in avaluos:
            _, creado = Avaluo.objects.get_or_create(
                propiedad=propiedad,
                fecha=fecha,
                perito=perito,
                defaults={
                    "valor": valor,
                    "moneda": propiedad.moneda,
                    "metodologia": metodologia,
                    "observaciones": observaciones,
                },
            )
            if creado:
                creados["avaluos"] += 1

    return creados
