"""Desarrollo local: depuración activa y acceso solo desde la propia máquina."""

from .base import *

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
