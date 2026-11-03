"""Modelos de catálogo: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

import uuid
from pathlib import Path

from django.db import models
from django.db.models import F, Q

from apps.core.models import ModeloBase

from .enums import EstadoPropiedad, TipoDocumento

# Regla 6: ningún documento oficial supera los 10 MB. El servicio lo valida
# antes de leer el archivo y la base lo vuelve a garantizar con un constraint.
TAMANO_MAXIMO_DOCUMENTO = 10 * 1024 * 1024


def ruta_documento(instancia: "DocumentoOficial", nombre_original: str) -> str:
    """
    Regla 8: documentos/<código de propiedad>/<uuid>.<extensión>.

    El uuid evita que dos archivos llamados igual se pisen y que alguien
    adivine la ruta de otro. La extensión se conserva para que el archivo se
    abra bien al descargarlo; el tipo real se valida por el contenido.
    """
    extension = Path(nombre_original).suffix.lower()
    return f"documentos/{instancia.propiedad.codigo}/{uuid.uuid4().hex}{extension}"


# Spec 019, regla 1: las fotos pesan menos que un documento, porque una
# propiedad tiene varias y el plan gratuito de Supabase tiene 1 GB.
TAMANO_MAXIMO_IMAGEN = 5 * 1024 * 1024


def ruta_imagen(instancia: "ImagenPropiedad", nombre_original: str) -> str:
    """Spec 019, regla 3: imagenes/<código de propiedad>/<uuid>.<extensión>."""
    extension = Path(nombre_original).suffix.lower()
    return f"imagenes/{instancia.propiedad.codigo}/{uuid.uuid4().hex}{extension}"


class TipoPropiedad(ModeloBase):
    """Terreno, casa, edificio de apartamentos, hotel… (spec 003, §4)."""

    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)
    # Regla 2: solo los tipos que la tienen en True admiten unidades.
    requiere_unidades = models.BooleanField(default=False)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "tipo de propiedad"
        verbose_name_plural = "tipos de propiedad"

    def __str__(self) -> str:
        return self.nombre


class Propiedad(ModeloBase):
    # Lo genera el servicio a partir del id (regla 3). Es nulo solo entre la
    # inserción y la asignación: dos nulos no chocan con unique, dos cadenas
    # vacías sí (mismo criterio que la spec 004). Por eso se ignora aquí la
    # regla DJ001 del linter, que en general desaconseja null en texto.
    codigo = models.CharField(  # noqa: DJ001
        max_length=12, unique=True, null=True, editable=False
    )
    nombre = models.CharField(max_length=150)
    tipo = models.ForeignKey(
        TipoPropiedad, on_delete=models.PROTECT, related_name="propiedades"
    )
    # El país es el de la ciudad (regla 1): no se guarda dos veces.
    ciudad = models.ForeignKey(
        "core.Ciudad", on_delete=models.PROTECT, related_name="propiedades"
    )
    direccion = models.CharField(max_length=255)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    area_m2 = models.DecimalField(max_digits=12, decimal_places=2)
    area_construida_m2 = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoPropiedad.choices,
        default=EstadoPropiedad.EN_NEGOCIACION,
        db_index=True,
    )
    precio_lista = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="propiedades"
    )
    # Regla 5: lo que el agente de IA puede mostrar en modo público.
    es_publica = models.BooleanField(default=False)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "propiedad"
        verbose_name_plural = "propiedades"
        # Regla 4, en la base para que se cumpla aunque el dato no pase por la
        # API (mismo criterio que los tipos de cambio de la spec 001).
        constraints = [
            models.CheckConstraint(
                condition=Q(precio_lista__gt=0),
                name="catalogo_propiedad_precio_positivo",
            ),
            models.CheckConstraint(
                condition=Q(area_m2__gt=0), name="catalogo_propiedad_area_positiva"
            ),
            models.CheckConstraint(
                condition=Q(area_construida_m2__isnull=True)
                | Q(area_construida_m2__gt=0),
                name="catalogo_propiedad_area_construida_positiva",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"


class Unidad(ModeloBase):
    """Apartamento o local dentro de una propiedad que admite unidades."""

    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.PROTECT, related_name="unidades"
    )
    # Lo pone el usuario ("A-101"); único dentro de su propiedad (regla 3).
    codigo = models.CharField(max_length=20)
    # Negativo para sótanos.
    nivel = models.SmallIntegerField()
    area_m2 = models.DecimalField(max_digits=12, decimal_places=2)
    habitaciones = models.PositiveSmallIntegerField(default=0)
    banos = models.PositiveSmallIntegerField(default=0)
    estado = models.CharField(
        max_length=20,
        choices=EstadoPropiedad.choices,
        default=EstadoPropiedad.EN_NEGOCIACION,
        db_index=True,
    )
    precio_lista = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="unidades"
    )

    class Meta:
        ordering = ["propiedad_id", "codigo"]
        verbose_name = "unidad"
        verbose_name_plural = "unidades"
        constraints = [
            models.UniqueConstraint(
                fields=["propiedad", "codigo"],
                name="catalogo_unidad_unica_por_propiedad",
            ),
            models.CheckConstraint(
                condition=Q(precio_lista__gt=0), name="catalogo_unidad_precio_positivo"
            ),
            models.CheckConstraint(
                condition=Q(area_m2__gt=0), name="catalogo_unidad_area_positiva"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.propiedad.codigo} · {self.codigo}"


class DocumentoOficial(ModeloBase):
    """
    Escritura, licencia, plano o certificación de una propiedad (spec 011).

    El archivo no se reemplaza: una versión nueva es otro documento y el
    anterior se desactiva. Desactivarlo tampoco borra el archivo.
    """

    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.PROTECT, related_name="documentos"
    )
    tipo = models.CharField(max_length=20, choices=TipoDocumento.choices)
    nombre = models.CharField(max_length=200)
    archivo = models.FileField(upload_to=ruta_documento, max_length=255)
    nombre_original = models.CharField(max_length=255)
    # application/pdf, image/jpeg o image/png. El servicio lo deduce del
    # contenido, no de la extensión (regla 6).
    tipo_contenido = models.CharField(max_length=50)
    tamano_bytes = models.PositiveIntegerField()
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    emisor = models.CharField(max_length=150)

    class Meta:
        ordering = ["-fecha_emision", "-id"]
        verbose_name = "documento oficial"
        verbose_name_plural = "documentos oficiales"
        indexes = [
            models.Index(
                fields=["propiedad", "tipo"],
                name="catalogo_doc_prop_tipo_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_vencimiento__isnull=True)
                | Q(fecha_vencimiento__gte=F("fecha_emision")),
                name="catalogo_documento_vencimiento_valido",
            ),
            models.CheckConstraint(
                condition=Q(tamano_bytes__gt=0)
                & Q(tamano_bytes__lte=TAMANO_MAXIMO_DOCUMENTO),
                name="catalogo_documento_tamano_valido",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.nombre}"


class ImagenPropiedad(ModeloBase):
    """
    Una foto de la galería de una propiedad (spec 019).

    Es un modelo aparte de DocumentoOficial porque una foto no tiene emisor ni
    vencimiento, y sí portada y orden (§10). El archivo no se reemplaza: una
    foto distinta es otra imagen (regla 4).
    """

    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.PROTECT, related_name="imagenes"
    )
    archivo = models.FileField(upload_to=ruta_imagen, max_length=255)
    nombre_original = models.CharField(max_length=255)
    # image/jpeg o image/png, deducido del contenido (regla 1).
    tipo_contenido = models.CharField(max_length=50)
    tamano_bytes = models.PositiveIntegerField()
    # También es el texto alternativo de la imagen en la pantalla.
    descripcion = models.CharField(max_length=200, blank=True)
    orden = models.PositiveSmallIntegerField(default=1)
    es_portada = models.BooleanField(default=False)

    class Meta:
        # Regla 7: por orden y, a igual orden, por fecha de subida.
        ordering = ["orden", "creado_en", "id"]
        verbose_name = "imagen de propiedad"
        verbose_name_plural = "imágenes de propiedad"
        constraints = [
            models.CheckConstraint(
                condition=Q(tamano_bytes__gt=0)
                & Q(tamano_bytes__lte=TAMANO_MAXIMO_IMAGEN),
                name="catalogo_imagen_tamano_valido",
            ),
            # Regla 6: una sola portada activa por propiedad. La base lo
            # garantiza aunque dos personas marquen portada a la vez.
            models.UniqueConstraint(
                fields=["propiedad"],
                condition=Q(es_portada=True, activo=True),
                name="catalogo_imagen_una_portada",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.propiedad.codigo} · {self.descripcion or self.nombre_original}"


class Avaluo(ModeloBase):
    """
    Valoración de una propiedad en una fecha (spec 011).

    No se edita: el historial es la plusvalía. Si un avalúo tiene un error se
    desactiva y se registra el correcto.
    """

    propiedad = models.ForeignKey(
        Propiedad, on_delete=models.PROTECT, related_name="avaluos"
    )
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="avaluos"
    )
    perito = models.CharField(max_length=150)
    metodologia = models.CharField(max_length=150)
    documento = models.ForeignKey(
        DocumentoOficial,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="avaluos",
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "avalúo"
        verbose_name_plural = "avalúos"
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0), name="catalogo_avaluo_valor_positivo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.propiedad.codigo} · {self.fecha}: {self.valor} {self.moneda}"
