"""Servicios de IA: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.models import Pais

from . import selectors
from .enums import TipoDocumentoRAG
from .exceptions import DocumentoRAGDuplicado, EmbeddingConDimensionIncorrecta
from .models import DIMENSION_EMBEDDINGS, DocumentoRAG, FragmentoRAG
from .proveedores.base import TareaEmbedding
from .proveedores.fabrica import obtener_proveedor
from .troceo import estimar_tokens, trocear_markdown

ENTIDAD_DOCUMENTO = "ia_documento_rag"


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
    """
    if documento.contenido_fuente == contenido_fuente:
        return documento

    with transaction.atomic():
        version_anterior = documento.version
        documento.contenido_fuente = contenido_fuente
        documento.version = version_anterior + 1
        documento.actualizado_por = autor
        documento.save(
            update_fields=[
                "contenido_fuente",
                "version",
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
