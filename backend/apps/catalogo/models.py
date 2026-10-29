"""Modelos de catálogo: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import Q

from apps.core.models import ModeloBase

from .enums import EstadoPropiedad


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
