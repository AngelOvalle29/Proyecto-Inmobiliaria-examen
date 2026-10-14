"""Fábricas de datos de prueba para los modelos de usuarios."""

import factory

from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol, Usuario

# Contraseña de todos los usuarios de prueba. Cumple el mínimo de 10 caracteres.
CONTRASENA_DE_PRUEBA = "contrasena-de-prueba-123"


class UsuarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Usuario
        django_get_or_create = ["email"]
        skip_postgeneration_save = True

    # Correos y nombres ficticios y numerados: nunca nombres de personas reales.
    email = factory.Sequence(lambda n: f"usuario{n}@demo.test")
    nombre_completo = factory.Sequence(lambda n: f"Usuario Demo {n}")
    # Los roles ya existen (los crea la migración 0002): se buscan, no se crean.
    # CONSULTA es el de menos privilegios; cada prueba pide otro si lo necesita.
    rol = factory.LazyFunction(lambda: Rol.objects.get(nombre=NombreRol.CONSULTA))
    # Guarda la contraseña cifrada, igual que set_password.
    password = factory.django.Password(CONTRASENA_DE_PRUEBA)
