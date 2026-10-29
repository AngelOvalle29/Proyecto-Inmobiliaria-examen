"""
Pruebas de la tarea de diagnóstico y del comando que la encola (spec 002, §5.5).

En las pruebas las tareas corren en el mismo proceso (CELERY_TASK_ALWAYS_EAGER
en test.py), así que no hace falta RabbitMQ ni un worker.
"""

import logging
from io import StringIO

from django.core.management import call_command

from apps.core.tasks import MENSAJE_DIAGNOSTICO, verificar_worker


def test_la_tarea_de_diagnostico_deja_constancia_en_el_registro(caplog):
    with caplog.at_level(logging.INFO, logger="apps.core.tasks"):
        resultado = verificar_worker.delay()

    assert resultado.get() == "ok"
    assert MENSAJE_DIAGNOSTICO in caplog.text


def test_el_comando_encola_el_diagnostico(caplog):
    salida = StringIO()

    with caplog.at_level(logging.INFO, logger="apps.core.tasks"):
        call_command("encolar_diagnostico", stdout=salida)

    assert "Tarea de diagnóstico encolada." in salida.getvalue()
    assert MENSAJE_DIAGNOSTICO in caplog.text


def test_si_rabbitmq_no_responde_el_comando_avisa_y_no_falla(monkeypatch):
    """El arranque no debe dejar la API caída solo porque falló el diagnóstico."""

    def encolar_sin_broker():
        raise ConnectionError("RabbitMQ no responde")

    monkeypatch.setattr(
        "apps.core.management.commands.encolar_diagnostico.verificar_worker.delay",
        encolar_sin_broker,
    )
    errores = StringIO()

    call_command("encolar_diagnostico", stderr=errores)

    assert "No se pudo encolar el diagnóstico" in errores.getvalue()
