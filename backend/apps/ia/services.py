"""Servicios de IA: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

import re
import time
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria, ModoAgente
from apps.auditoria.services import registrar_auditoria, registrar_consulta_agente
from apps.core.models import Pais

from . import selectors
from .enums import TipoDocumentoRAG
from .exceptions import (
    AgenteNoDisponible,
    DocumentoModificadoDuranteIndexacion,
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

# Marcadores de cita en la respuesta del modelo: [1], [2]...
_MARCADOR_CITA = re.compile(r"\[(\d+)\]")


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

    Compara y calcula la versión sobre la fila recién bloqueada, no sobre el
    objeto recibido: si ese objeto es antiguo, su versión ya no es la de la
    base y repetiría un número que la indexación usa para detectar cambios
    (revisión del PR #62). El objeto recibido se actualiza con el resultado.
    """
    with transaction.atomic():
        # Bloquea la fila: si una indexación está guardando en este momento,
        # espera a que termine y lee la versión que dejó.
        actual = DocumentoRAG.objects.select_for_update().get(pk=documento.pk)
        if actual.contenido_fuente != contenido_fuente:
            version_anterior = actual.version
            actual.contenido_fuente = contenido_fuente
            actual.version = version_anterior + 1
            actual.fecha_indexacion = None
            actual.actualizado_por = autor
            actual.save(
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
                entidad_id=actual.id,
                accion=AccionAuditoria.ACTUALIZAR,
                valores_anteriores={"version": version_anterior},
                valores_nuevos={"version": actual.version},
            )

    # Quien llamó sigue usando su objeto (cargar_demo_ia revisa después su
    # fecha de indexación): se deja igual a la fila guardada.
    for campo in ("contenido_fuente", "version", "fecha_indexacion"):
        setattr(documento, campo, getattr(actual, campo))
    return actual


def indexar_documento(*, documento_id: int) -> int:
    """Trocea el documento, pide los vectores y reemplaza sus fragmentos.

    Devuelve cuántos fragmentos quedaron. Recibe solo un id para que la tarea
    de Celery de la ingesta por cola (#25) la pueda llamar tal cual.

    Los vectores se piden ANTES de abrir la transacción: es una llamada de red
    que puede tardar segundos y no debe mantener filas bloqueadas. Si el
    proveedor falla, se lanza ProveedorIANoDisponible y los fragmentos
    anteriores quedan intactos (regla 7).

    Como los vectores se piden fuera de la transacción, el texto puede cambiar
    mientras llegan. Por eso se anota la versión leída y, ya con la fila
    bloqueada, se compara con la actual: si cambió, no se guarda nada y se
    lanza DocumentoModificadoDuranteIndexacion (revisión del PR #62).
    """
    documento = selectors.obtener_documento(documento_id=documento_id)
    version_leida = documento.version
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
        if documento.version != version_leida:
            raise DocumentoModificadoDuranteIndexacion(
                f"El documento {documento.titulo!r} pasó de la versión "
                f"{version_leida} a la {documento.version} mientras se indexaba."
            )
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
       citar [n], y devuelve como citas los fragmentos que el modelo citó.

    Cada consulta, correcta o fallida, queda en la bitácora del agente
    (spec 015) con el contrato acordado en el PR #61: por eso va en services y
    no en selectors. Si Gemini falla, la registra con exito=False y lanza
    AgenteNoDisponible.
    """
    inicio = time.monotonic()
    fragmentos: list[FragmentoRAG] = []
    try:
        proveedor = obtener_proveedor()
        vector = proveedor.generar_embedding(
            texto=pregunta, tarea=TareaEmbedding.CONSULTA
        )
        if len(vector) != DIMENSION_EMBEDDINGS:
            # Con otro tamaño la búsqueda en PostgreSQL fallaría con un 500.
            raise ProveedorIANoDisponible(
                f"El vector de la pregunta tiene {len(vector)} valores y no "
                f"{DIMENSION_EMBEDDINGS}. Revise IA_DIMENSION_EMBEDDINGS."
            )
        fragmentos = selectors.buscar_fragmentos_similares(
            embedding=vector,
            distancia_maxima=settings.IA_DISTANCIA_MAXIMA,
            limite=FRAGMENTOS_POR_CONSULTA,
        )
        if not fragmentos:
            # No se llamó al modelo: se sabe que el consumo fue cero.
            tokens_entrada, tokens_salida = 0, 0
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
            # None si el proveedor no los reportó (desconocido, no cero).
            tokens_entrada = respuesta_modelo.tokens_entrada
            tokens_salida = respuesta_modelo.tokens_salida
            texto = respuesta_modelo.texto.strip()
            if not texto:
                # El modelo no dijo nada: para el usuario es lo mismo que no
                # tener información, y no hay respuesta que citar.
                resultado = RespuestaAgente(
                    respuesta=MENSAJE_SIN_INFORMACION, sin_informacion=True, citas=[]
                )
            else:
                resultado = RespuestaAgente(
                    respuesta=texto,
                    sin_informacion=False,
                    citas=_citas_usadas(texto, fragmentos),
                )
    except ProveedorIANoDisponible as error:
        # Los mensajes de ProveedorIANoDisponible los arma el proveedor (código
        # HTTP, intentos): no llevan la llave ni el texto crudo de Gemini, así
        # que sirven como diagnóstico (spec 015). Los tokens quedan en None:
        # si el modelo falló, no se sabe cuánto consumió.
        _registrar_en_bitacora(
            pregunta=pregunta,
            respuesta="",
            fragmentos=fragmentos,
            tokens_entrada=None,
            tokens_salida=None,
            inicio=inicio,
            error=str(error),
        )
        raise AgenteNoDisponible() from error

    _registrar_en_bitacora(
        pregunta=pregunta,
        respuesta=resultado.respuesta,
        fragmentos=fragmentos,
        tokens_entrada=tokens_entrada,
        tokens_salida=tokens_salida,
        inicio=inicio,
    )
    return resultado


def _registrar_en_bitacora(
    *,
    pregunta: str,
    respuesta: str,
    fragmentos: list[FragmentoRAG],
    tokens_entrada: int | None,
    tokens_salida: int | None,
    inicio: float,
    error: str = "",
) -> None:
    """
    Escribe la consulta en la bitácora del agente (spec 015), con el contrato
    acordado en el PR #61.

    - modo PUBLICO y usuario None: el visitante no inicia sesión.
    - documentos_recuperados: cada fragmento que se le dio al modelo, con su
      documento y su distancia, aunque el modelo no lo citara. Así se puede
      revisar después por qué respondió lo que respondió.
    - herramientas_invocadas: vacía hasta que el agente tenga herramientas.
    - duracion_ms: desde el inicio de la consulta, con time.monotonic(), que no
      salta si cambia la hora del servidor.

    Es una sola inserción fuera de transacción: queda guardada aunque después
    se lance AgenteNoDisponible.
    """
    registrar_consulta_agente(
        usuario=None,
        modo=ModoAgente.PUBLICO,
        pregunta=pregunta,
        respuesta=respuesta,
        herramientas_invocadas=[],
        documentos_recuperados=[
            {
                "fragmento_id": fragmento.pk,
                "documento_id": fragmento.documento_id,
                "documento": fragmento.documento.titulo,
                "seccion": fragmento.seccion,
                # float y redondeada: el JSON no admite el tipo de pgvector.
                "distancia": round(float(fragmento.distancia), 4),
            }
            for fragmento in fragmentos
        ],
        tokens_entrada=tokens_entrada,
        tokens_salida=tokens_salida,
        duracion_ms=int((time.monotonic() - inicio) * 1000),
        exito=not error,
        error=error,
    )


def _citas_usadas(texto: str, fragmentos: list[FragmentoRAG]) -> list[Cita]:
    """Las fuentes que el modelo citó con [n], con su mismo número.

    Si no citó ninguna, se devuelven todas las que recibió: el usuario siempre
    ve de dónde pudo salir la respuesta (regla 2). Se decidió tras la prueba
    real del 2026-10-31, donde devolver siempre las cinco mostraba fuentes que
    nada tenían que ver con la respuesta.
    """
    citadas = {int(n) for n in _MARCADOR_CITA.findall(texto)}
    numerados = list(enumerate(fragmentos, start=1))
    usados = [(n, f) for n, f in numerados if n in citadas] or numerados
    return [_cita(numero, fragmento) for numero, fragmento in usados]


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
