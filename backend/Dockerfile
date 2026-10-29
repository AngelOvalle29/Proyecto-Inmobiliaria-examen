# Imagen de producción del backend, para el servicio web de Render
# (spec 002, §5.4). Arranca con scripts/iniciar.sh, que levanta la API y
# el worker de Celery en este mismo contenedor.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias del sistema.
# Las de libpango y libcairo las necesita WeasyPrint para generar los PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las dependencias se copian primero para aprovechar la cache de capas:
# si no cambian, Docker no vuelve a instalarlas.
COPY requirements/ requirements/
RUN pip install --upgrade pip && pip install -r requirements/prod.txt

# .dockerignore deja fuera el entorno virtual local, los cachés y .env.
COPY . .

# prod.py exige secretos que no existen al construir la imagen. Estos valores
# ficticios existen solo durante este comando: no quedan en la imagen ni llegan
# al contenedor, que recibe los reales desde Render. collectstatic no se
# conecta a la base, así que nunca se usan.
RUN SECRET_KEY=valor-ficticio-solo-para-collectstatic-con-al-menos-50-caracteres \
    DATABASE_URL=postgresql://construccion:construccion@localhost:5432/construccion \
    ALLOWED_HOSTS=construccion \
    RABBITMQ_URL=amqp://construccion@localhost// \
    python manage.py collectstatic --noinput --settings=config.settings.prod

# Usuario sin privilegios: nada corre como root en producción.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Sin HEALTHCHECK de Docker: Render usa su propia ruta de salud,
# /api/v1/health/ (spec 002, §5.1 y §5.4).

# Migraciones, worker de Celery con reinicio, diagnóstico y gunicorn. Se llama
# con sh para no depender del permiso de ejecución del archivo, que se pierde
# al editarlo en Windows.
CMD ["sh", "scripts/iniciar.sh"]
