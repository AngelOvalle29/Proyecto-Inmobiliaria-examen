"""Tareas Celery de IA.

Cáscaras delgadas: reciben identificadores, llaman a un servicio y
manejan reintentos. Sin reglas de negocio.
"""

import logging

from celery import shared_task

from . import selectors, services
from .exceptions import (
    DocumentoModificadoDuranteIndexacion,
    EmbeddingConDimensionIncorrecta,
)
from .models import DocumentoRAG
from .proveedores.base import ProveedorIANoDisponible

logger = logging.getLogger(__name__)

# Spec 020, regla 6: tres reintentos, a 1, 2 y 4 minutos.
REINTENTOS = 3
ESPERA_BASE_SEGUNDOS = 60


@shared_task(
    name="ia.indexar_documento",
    bind=True,
    # Regla 10: el mensaje se confirma al terminar, no al recibirlo. Si Render
    # reinicia el worker a mitad de la tarea, RabbitMQ lo vuelve a entregar.
    # Repetir es seguro: indexar reemplaza los fragmentos (spec 005, regla 7).
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=REINTENTOS,
)
def indexar_documento_tarea(self, documento_id: int) -> None:
    """
    Indexa un documento del agente desde la cola documentos (spec 020).

    Es una cáscara: llama a indexar_documento de la spec 005 y decide qué hacer
    con cada error. Recibe solo el id, nunca el objeto (arquitectura §6).
    """
    try:
        documento = selectors.obtener_documento(documento_id=documento_id)
    except DocumentoRAG.DoesNotExist:
        logger.info("Indexación omitida: el documento %s ya no existe.", documento_id)
        return
    if not documento.activo:
        # Regla 9: un documento desactivado no se responde, no hace falta indexarlo.
        logger.info(
            "Indexación omitida: el documento %s está desactivado.", documento_id
        )
        return

    logger.info(
        "Indexando el documento %s (intento %s).",
        documento_id,
        self.request.retries + 1,
    )
    try:
        fragmentos = services.indexar_documento(documento_id=documento_id)
    except DocumentoModificadoDuranteIndexacion as error:
        # Regla 8: el cambio encoló su propia indexación, que es la que vale.
        logger.info("Indexación descartada: %s", error)
        return
    except EmbeddingConDimensionIncorrecta as error:
        # Error de configuración: reintentar daría lo mismo.
        services.marcar_error_indexacion(documento_id=documento_id, motivo=str(error))
        logger.error("Indexación fallida sin reintentar: %s", error)
        return
    except ProveedorIANoDisponible as error:
        if self.request.retries >= REINTENTOS:
            # Regla 7: queda en ERROR y conserva sus fragmentos anteriores.
            services.marcar_error_indexacion(
                documento_id=documento_id, motivo=str(error)
            )
            logger.error("Indexación fallida tras %s reintentos: %s", REINTENTOS, error)
            return
        espera = ESPERA_BASE_SEGUNDOS * 2**self.request.retries
        logger.warning("Gemini no disponible; se reintenta en %s s: %s", espera, error)
        raise self.retry(exc=error, countdown=espera) from error

    logger.info("Documento %s indexado: %s fragmentos.", documento_id, fragmentos)
