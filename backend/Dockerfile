# Imagen de producción del backend. La usan tanto el servicio `api` como el
# servicio `worker` en Railway: cambia únicamente el comando de arranque.

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
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las dependencias se copian primero para aprovechar la cache de capas:
# si no cambian, Docker no vuelve a instalarlas.
COPY requirements/ requirements/
RUN pip install --upgrade pip && pip install -r requirements/prod.txt

COPY . .

RUN python manage.py collectstatic --noinput --settings=config.settings.prod

# Usuario sin privilegios: nada corre como root en producción.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/api/v1/health/ || exit 1

# Railway sobrescribe este comando en el servicio `worker`.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120"]
