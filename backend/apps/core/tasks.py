"""Tareas Celery de core.

Cáscaras delgadas: reciben identificadores, llaman a un servicio y
manejan reintentos. Sin reglas de negocio.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

MENSAJE_DIAGNOSTICO = "Worker de Celery operativo: tarea de diagnóstico recibida."


@shared_task(name="core.verificar_worker")
def verificar_worker() -> str:
    """
    Tarea de diagnóstico (spec 002, §5.5): solo deja constancia en el registro
    de que el worker la recibió.

    El script de arranque la encola en cada despliegue. Si ese mensaje aparece
    en los registros de Render, la cadena completa funciona: la API publica en
    RabbitMQ y el worker consume. No tiene lógica de negocio.
    """
    logger.info(MENSAJE_DIAGNOSTICO)
    return "ok"
