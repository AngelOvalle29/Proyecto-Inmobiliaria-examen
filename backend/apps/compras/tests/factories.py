"""Fábricas de datos de prueba de compras. Datos ficticios y numerados."""

import factory

from apps.compras.enums import TipoProveedor
from apps.compras.models import Proveedor
from apps.core.tests.factories import PaisFactory


class ProveedorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Proveedor

    codigo = factory.Sequence(lambda n: f"PRV-T{n:03d}")
    tipo = TipoProveedor.BANCO
    nombre = factory.Sequence(lambda n: f"Proveedor de prueba {n}")
    nit = factory.Sequence(lambda n: f"{9100000 + n}")
    pais = factory.SubFactory(PaisFactory)
