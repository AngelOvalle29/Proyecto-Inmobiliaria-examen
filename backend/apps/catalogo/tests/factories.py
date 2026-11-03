"""
Fábricas de datos de prueba del catálogo. Las pueden usar las pruebas de las
apps que dependen de Propiedad: cotizaciones, ventas, arrendamientos, compras y
construcción.
"""

from datetime import date
from decimal import Decimal

import factory

from apps.catalogo.enums import TipoDocumento
from apps.catalogo.models import (
    Avaluo,
    DocumentoOficial,
    ImagenPropiedad,
    Propiedad,
    TipoPropiedad,
    Unidad,
)
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


class DocumentoOficialFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentoOficial

    propiedad = factory.SubFactory(PropiedadFactory)
    tipo = TipoDocumento.ESCRITURA
    nombre = factory.Sequence(lambda n: f"Documento demo {n}")
    # Basta el nombre: las pruebas no necesitan el archivo real salvo que
    # prueben la subida (incremento 3).
    archivo = factory.Sequence(lambda n: f"documentos/demo/{n}.pdf")
    nombre_original = "documento.pdf"
    tipo_contenido = "application/pdf"
    tamano_bytes = 1024
    fecha_emision = date(2025, 1, 1)
    emisor = "Registro ficticio"


class AvaluoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Avaluo

    propiedad = factory.SubFactory(PropiedadFactory)
    fecha = date(2025, 1, 15)
    valor = Decimal("150000.00")
    moneda = factory.SubFactory(MonedaFactory, codigo="USD")
    perito = factory.Sequence(lambda n: f"Perito demo {n}")
    metodologia = "Comparativo de mercado"


class ImagenPropiedadFactory(factory.django.DjangoModelFactory):
    """Una imagen ya registrada; la subida real la prueban test_imagenes.py."""

    class Meta:
        model = ImagenPropiedad

    propiedad = factory.SubFactory(PropiedadFactory)
    archivo = factory.Sequence(lambda n: f"imagenes/demo/{n}.jpg")
    nombre_original = "foto.jpg"
    tipo_contenido = "image/jpeg"
    tamano_bytes = 2048
    orden = factory.Sequence(lambda n: n + 1)
