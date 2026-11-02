"""Fábricas de datos de prueba de construcción. Datos ficticios y numerados."""

import factory

from apps.construccion.models import Constructora
from apps.core.tests.factories import PaisFactory


class ConstructoraFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Constructora

    codigo = factory.Sequence(lambda n: f"CST-T{n:03d}")
    nombre = factory.Sequence(lambda n: f"Constructora de prueba {n}")
    nit = factory.Sequence(lambda n: f"{8100000 + n}")
    pais = factory.SubFactory(PaisFactory)
