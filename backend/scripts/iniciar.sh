#!/bin/sh
# Arranque del contenedor en Render (spec 002, §5.4).
#
# El plan gratuito de Render no tiene workers, así que la API (gunicorn) y el
# worker de Celery comparten este contenedor. Este script los levanta a los dos.

# Si una migración falla, el contenedor no debe arrancar con una base a medias.
set -e

python manage.py migrate --noinput

# Worker de Celery en segundo plano, dentro de un ciclo que lo vuelve a
# levantar si se cae (observación de la revisión de la spec 002): sin el ciclo,
# un worker caído quedaría así hasta el siguiente despliegue y nadie lo notaría.
#   --pool=solo   un solo proceso que ejecuta una tarea a la vez; cabe en 512 MB.
#   --without-*   sin mensajes de coordinación entre workers: hay uno solo, y
#                 cada mensaje cuenta contra la cuota de CloudAMQP.
(
    # Dentro del ciclo se desactiva set -e: si celery termina con error, hay
    # que reiniciarlo, no salir del ciclo.
    set +e
    while true; do
        celery -A config worker --pool=solo --loglevel=info \
            --without-gossip --without-mingle --without-heartbeat
        echo "El worker de Celery se detuvo (código $?). Se reinicia en 5 segundos." >&2
        sleep 5
    done
) &

# Diagnóstico: si el registro muestra "tarea de diagnóstico recibida", la API
# publica en RabbitMQ y el worker consume. Si RabbitMQ no responde, el comando
# avisa y sigue, para no dejar la API caída por eso.
python manage.py encolar_diagnostico

# exec reemplaza este script por gunicorn, que pasa a recibir las señales de
# apagado de Render. Un solo proceso, por los 512 MB del plan gratuito.
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" --workers 1 --timeout 120
