"""Modelos de compras: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import Q

from apps.core.models import ModeloBase

from .enums import TipoProveedor


class Proveedor(ModeloBase):
    """A quién le compra propiedades la agencia (spec 006, §4)."""

    # Nulo solo durante la creación: el servicio lo asigna a partir del id en la
    # misma transacción. En PostgreSQL dos nulos no chocan con unique, dos
    # cadenas vacías sí (mismo criterio que la spec 004).
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)  # noqa: DJ001
    tipo = models.CharField(max_length=30, choices=TipoProveedor.choices)
    nombre = models.CharField(max_length=200)
    # Normalizado: sin espacios ni guiones y en mayúsculas (regla 3).
    nit = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    pais = models.ForeignKey(
        "core.Pais", on_delete=models.PROTECT, related_name="proveedores"
    )
    ciudad = models.ForeignKey(
        "core.Ciudad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="proveedores",
    )
    direccion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"
        constraints = [
            # Regla 2: el NIT solo puede faltar en un propietario particular.
            models.CheckConstraint(
                condition=Q(tipo=TipoProveedor.PROPIETARIO_PARTICULAR) | ~Q(nit=""),
                name="compras_proveedor_nit_obligatorio",
            ),
            # Regla 3: un NIT por país, aunque el proveedor esté desactivado.
            # La condición permite varios particulares sin NIT en el mismo país.
            models.UniqueConstraint(
                fields=["pais", "nit"],
                condition=~Q(nit=""),
                name="compras_proveedor_nit_unico_por_pais",
            ),
        ]
        indexes = [models.Index(fields=["tipo"], name="compras_proveedor_tipo_idx")]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"
