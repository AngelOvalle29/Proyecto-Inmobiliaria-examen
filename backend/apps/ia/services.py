"""Servicios de IA: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.models import Pais

from . import selectors
from .enums import TipoDocumentoRAG
from .exceptions import (
    AgenteNoDisponible,
    DocumentoRAGDuplicado,
    EmbeddingConDimensionIncorrecta,
)
from .instrucciones import (
    INSTRUCCIONES_SISTEMA,
    MENSAJE_SIN_INFORMACION,
    armar_mensaje_usuario,
)
from .models import DIMENSION_EMBEDDINGS, DocumentoRAG, FragmentoRAG
from .proveedores.base import (
    Mensaje,
    ProveedorIANoDisponible,
    RolMensaje,
    TareaEmbedding,
)
from .proveedores.fabrica import obtener_proveedor
from .troceo import estimar_tokens, trocear_markdown

ENTIDAD_DOCUMENTO = "ia_documento_rag"

# Cuántos fragmentos se le entregan al modelo por pregunta. Cinco de hasta
# 1,500 caracteres son unos 2,000 tokens: suficiente contexto sin gastar de más.
FRAGMENTOS_POR_CONSULTA = 5

# Largo del extracto de cada cita, para que la pantalla muestre la fuente.
LARGO_EXTRACTO = 200


@dataclass(frozen=True)
class Cita:
    numero: int
    documento: str
    seccion: str
    tipo: str
    extracto: str


@dataclass(frozen=True)
class RespuestaAgente:
    respuesta: str
    sin_informacion: bool
    citas: list[Cita]


def crear_documento_rag(
    *,
    titulo: str,
    tipo: TipoDocumentoRAG,
    contenido_fuente: str,
    pais: Pais | None = None,
    autor: AbstractBaseUser | None = None,
) -> DocumentoRAG:
    """Crea el documento sin indexar y lo audita. Indexar es un paso aparte."""
    with transaction.atomic():
        if selectors.obtener_documento_por_titulo(titulo=titulo) is not None:
            raise DocumentoRAGDuplicado(titulo)
        documento = DocumentoRAG.objects.create(
            titulo=titulo,
            tipo=tipo,
            contenido_fuente=contenido_fuente,
            pais=pais,
            creado_por=autor,
            actualizado_por=autor,
        )
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_DOCUMENTO,
            entidad_id=documento.id,
            accion=AccionAuditoria.CREAR,
            valores_nuevos={
                "titulo": titulo,
                "tipo": tipo,
                "pais": pais.nombre if pais else None,
                "version": documento.version,
            },
        )
    return documento


def actualizar_contenido_documento(
    *,
    documento: DocumentoRAG,
    contenido_fuente: str,
    autor: AbstractBaseUser | None = None,
) -> DocumentoRAG:
    """Si el texto cambió, sube la versión y lo audita. Si no, no hace nada.

    No reindexa: quien llama decide cuándo, porque indexar llama a la red.
    Sí borra la fecha de indexación: los fragmentos ya no corresponden al
    texto, y así se sabe que el documento está pendiente de reindexar.
    """
    if documento.contenido_fuente == contenido_fuente:
        return documento

    with transaction.atomic():
        version_anterior = documento.version
        documento.contenido_fuente = contenido_fuente
        documento.version = version_anterior + 1
        documento.fecha_indexacion = None
        documento.actualizado_por = autor
        documento.save(
            update_fields=[
                "contenido_fuente",
                "version",
                "fecha_indexacion",
                "actualizado_por",
                "actualizado_en",
            ]
        )
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_DOCUMENTO,
            entidad_id=documento.id,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores={"version": version_anterior},
            valores_nuevos={"version": documento.version},
        )
    return documento


def indexar_documento(*, documento_id: int) -> int:
    """Trocea el documento, pide los vectores y reemplaza sus fragmentos.

    Devuelve cuántos fragmentos quedaron. Recibe solo un id para que la tarea
    de Celery de la ingesta por cola (#25) la pueda llamar tal cual.

    Los vectores se piden ANTES de abrir la transacción: es una llamada de red
    que puede tardar segundos y no debe mantener filas bloqueadas. Si el
    proveedor falla, se lanza ProveedorIANoDisponible y los fragmentos
    anteriores quedan intactos (regla 7).
    """
    documento = selectors.obtener_documento(documento_id=documento_id)
    trozos = trocear_markdown(documento.contenido_fuente)

    vectores: list[list[float]] = []
    if trozos:
        # Se vectoriza con el título y la sección delante: "Requisitos ·
        # Documentos del comprador" ayuda a encontrar un párrafo que por sí
        # solo no menciona de qué trata. En la base se guarda solo el texto.
        vectores = obtener_proveedor().generar_embeddings_lote(
            textos=[
                f"{documento.titulo} · {t.seccion}\n\n{t.contenido}" for t in trozos
            ],
            tarea=TareaEmbedding.DOCUMENTO,
        )
    _verificar_vectores(vectores, cantidad=len(trozos))

    with transaction.atomic():
        documento = DocumentoRAG.objects.select_for_update().get(pk=documento_id)
        fragmentos_anteriores = documento.fragmentos.count()
        documento.fragmentos.all().delete()
        FragmentoRAG.objects.bulk_create(
            FragmentoRAG(
                documento=documento,
                orden=orden,
                seccion=trozo.seccion[:255],
                contenido=trozo.contenido,
                tokens=estimar_tokens(trozo.contenido),
                embedding=vector,
            )
            for orden, (trozo, vector) in enumerate(zip(trozos, vectores, strict=True))
        )
        documento.fecha_indexacion = timezone.now()
        documento.save(update_fields=["fecha_indexacion", "actualizado_en"])
        registrar_auditoria(
            usuario=None,
            entidad=ENTIDAD_DOCUMENTO,
            entidad_id=documento.id,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores={"fragmentos": fragmentos_anteriores},
            valores_nuevos={"fragmentos": len(trozos), "version": documento.version},
        )
    return len(trozos)


def _verificar_vectores(vectores: list[list[float]], *, cantidad: int) -> None:
    if len(vectores) != cantidad:
        raise EmbeddingConDimensionIncorrecta(
            f"Se pidieron {cantidad} vectores y el proveedor devolvió {len(vectores)}."
        )
    for vector in vectores:
        if len(vector) != DIMENSION_EMBEDDINGS:
            raise EmbeddingConDimensionIncorrecta(
                f"El proveedor devolvió vectores de {len(vector)} valores y el "
                f"campo guarda {DIMENSION_EMBEDDINGS}. Revise IA_DIMENSION_EMBEDDINGS."
            )


def responder_consulta_publica(*, pregunta: str) -> RespuestaAgente:
    """Responde la pregunta de un visitante con los documentos de la agencia.

    1. Convierte la pregunta en vector y busca los fragmentos más cercanos.
    2. Si ninguno pasa el umbral, responde que no tiene información SIN llamar
       al modelo (regla 3): no gasta cuota ni le da ocasión de inventar.
    3. Si hay fragmentos, se los entrega numerados al modelo con la orden de
       citar [n], y devuelve como citas esos mismos fragmentos.

    Va en services y no en selectors porque escribirá la bitácora del agente
    (spec 015) en cuanto exista. Si Gemini falla, lanza AgenteNoDisponible.
    """
    try:
        proveedor = obtener_proveedor()
        vector = proveedor.generar_embedding(
            texto=pregunta, tarea=TareaEmbedding.CONSULTA
        )
        fragmentos = selectors.buscar_fragmentos_similares(
            embedding=vector,
            distancia_maxima=settings.IA_DISTANCIA_MAXIMA,
            limite=FRAGMENTOS_POR_CONSULTA,
        )
        if not fragmentos:
            resultado = RespuestaAgente(
                respuesta=MENSAJE_SIN_INFORMACION, sin_informacion=True, citas=[]
            )
        else:
            respuesta_modelo = proveedor.generar_respuesta(
                mensajes=[
                    Mensaje(RolMensaje.SISTEMA, INSTRUCCIONES_SISTEMA),
                    Mensaje(
                        RolMensaje.USUARIO,
                        armar_mensaje_usuario(pregunta=pregunta, fragmentos=fragmentos),
                    ),
                ]
            )
            resultado = RespuestaAgente(
                respuesta=respuesta_modelo.texto.strip() or MENSAJE_SIN_INFORMACION,
                sin_informacion=False,
                citas=[
                    _cita(numero, fragmento)
                    for numero, fragmento in enumerate(fragmentos, start=1)
                ],
            )
    except ProveedorIANoDisponible as error:
        # Punto de llamada a la bitácora del agente (spec 015, rol D) con
        # exito=False y error=str(error).
        raise AgenteNoDisponible() from error

    # Punto de llamada a la bitácora del agente (spec 015, rol D), acordado en
    # el PR #61: modo PUBLICO, pregunta, respuesta, documentos_recuperados
    # (fragmento_id, documento_id, documento, seccion y distancia de cada
    # fragmento), herramientas_invocadas vacía, tokens de respuesta_modelo (0 y
    # 0 si no se llamó al modelo), duracion_ms medida con time.monotonic()
    # desde el inicio de la función, y exito=True. Se conecta cuando la spec 015
    # esté en develop.
    return resultado


def _cita(numero: int, fragmento: FragmentoRAG) -> Cita:
    contenido = fragmento.contenido
    extracto = contenido[:LARGO_EXTRACTO]
    if len(contenido) > LARGO_EXTRACTO:
        extracto = extracto.rstrip() + "…"
    return Cita(
        numero=numero,
        documento=fragmento.documento.titulo,
        seccion=fragmento.seccion,
        tipo=fragmento.documento.tipo,
        extracto=extracto,
    )
