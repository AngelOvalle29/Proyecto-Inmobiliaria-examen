"""
Fábricas de datos de prueba del catálogo. Las pueden usar las pruebas de las
apps que dependen de Propiedad: cotizaciones, ventas, arrendamientos, compras y
construcción.
"""

from decimal import Decimal

import factory

from apps.catalogo.models import Propiedad, TipoPropiedad, Unidad
from apps.core.tests.factories import CiudadFactory, MonedaFactory


def tipo(nombre: str) -> TipoPropiedad:
    """Uno de los siete tipos que crea la migración 0002 (no se crean de nuevo)."""
    return TipoPropiedad.objects.get(nombre=nombre)


class PropiedadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Propiedad
        # asignar_codigo ya guarda lo que cambia; no hace falta otro save.
        skip_postgeneration_save = True

    # Igual que el servicio: el código se deriva del id después de insertar.
    codigo = factory.LazyAttribute(lambda _: None)
    nombre = factory.Sequence(lambda n: f"Propiedad demo {n}")
    tipo = factory.LazyFunction(lambda: tipo("Casa"))
    ciudad = factory.SubFactory(CiudadFactory)
    direccion = factory.Sequence(lambda n: f"Calle demo {n}")
    area_m2 = Decimal("250.00")
    precio_lista = Decimal("150000.00")
    moneda = factory.SubFactory(MonedaFactory, codigo="USD")

    @factory.post_generation
    def asignar_codigo(propiedad, create, extracted, **kwargs):
        if create and propiedad.codigo is None:
            propiedad.codigo = f"PROP-{propiedad.pk:05d}"
            propiedad.save(update_fields=["codigo"])


class UnidadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Unidad

    propiedad = factory.SubFactory(
        PropiedadFactory, tipo=factory.LazyFunction(lambda: tipo("Apartamentos"))
    )
    codigo = factory.Sequence(lambda n: f"A-{100 + n}")
    nivel = 1
    area_m2 = Decimal("80.00")
    habitaciones = 2
    banos = 1
    precio_lista = Decimal("95000.00")
    moneda = factory.SubFactory(MonedaFactory, codigo="USD")
