"""Modelos de construcción: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import Q

from apps.core.models import ModeloBase


class Constructora(ModeloBase):
    """Empresa que la agencia contrata para construir o remodelar (spec 006, §4).

    Sin ciudad: una constructora suele trabajar en varias ciudades de su país
    (spec 006, §10).
    """

    # Nulo solo durante la creación, igual que en compras y crm.
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)  # noqa: DJ001
    nombre = models.CharField(max_length=200)
    # Normalizado: sin espacios ni guiones y en mayúsculas (regla 5).
    nit = models.CharField(max_length=30)
    contacto = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    pais = models.ForeignKey(
        "core.Pais", on_delete=models.PROTECT, related_name="constructoras"
    )
    # Nula hasta que tenga trabajos que calificar (regla 6).
    calificacion = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "constructora"
        verbose_name_plural = "constructoras"
        constraints = [
            models.CheckConstraint(
                condition=~Q(nit=""), name="construccion_constructora_nit_obligatorio"
            ),
            # Un NIT por país, aunque la constructora esté desactivada.
            models.UniqueConstraint(
                fields=["pais", "nit"],
                name="construccion_constructora_nit_unico_por_pais",
            ),
            models.CheckConstraint(
                condition=Q(calificacion__isnull=True)
                | Q(calificacion__gte=1, calificacion__lte=5),
                name="construccion_constructora_calificacion_1_a_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"
