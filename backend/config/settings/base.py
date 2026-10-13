"""
Configuración común a todos los entornos.

dev.py, test.py y prod.py importan este archivo y solo cambian lo que es
distinto en su entorno. Todo valor que dependa del entorno o sea secreto se
lee de variables de entorno; nunca se escribe aquí.
"""

from pathlib import Path

import environ

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# En desarrollo las variables vienen del .env en la raíz del repositorio.
# En la integración continua y en producción no hay .env: las variables las
# define el entorno, y read_env no sobrescribe las que ya existen.
environ.Env.read_env(BASE_DIR.parent / ".env")


# ---------- Seguridad ----------

# Sin valor por defecto a propósito: si falta, Django no arranca. Es preferible
# a arrancar con una clave falsa (spec 001, §8).
SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])


# ---------- Aplicaciones ----------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Primero las transversales, que cualquier app puede importar, y luego los
# dominios del negocio (docs/arquitectura.md §3).
LOCAL_APPS = [
    "apps.core",
    "apps.usuarios",
    "apps.auditoria",
    "apps.catalogo",
    "apps.crm",
    "apps.ventas",
    "apps.arrendamientos",
    "apps.compras",
    "apps.construccion",
    "apps.reportes",
    "apps.ia",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------- Base de datos ----------

# Solo PostgreSQL, en todos los entornos (CLAUDE.md prohíbe SQLite).
# Sin valor por defecto, por la misma razón que SECRET_KEY.
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------- Contraseñas ----------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        # Mínimo de 10 caracteres (docs/arquitectura.md §9).
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ---------- Idioma y zona horaria ----------

LANGUAGE_CODE = "es"

# Zona en que se muestran las fechas en el panel. Las fechas se guardan
# siempre en UTC gracias a USE_TZ.
TIME_ZONE = "America/Guatemala"

USE_I18N = True

USE_TZ = True


# ---------- Archivos estáticos ----------

STATIC_URL = "static/"

# Destino de collectstatic. Cómo se sirven en producción lo decide la spec 002.
STATIC_ROOT = BASE_DIR / "staticfiles"
