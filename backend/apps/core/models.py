"""Modelos de core: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

# Códigos ISO: tres letras mayúsculas (GTQ, USD para monedas; GTM, MEX para
# países). Lo valida el formulario del panel antes de llegar a la base.
validar_codigo_iso = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="Debe tener exactamente tres letras mayúsculas.",
)


class ModeloBase(models.Model):
    """
    Campos de rastro que heredan las entidades de negocio desde la fase 2.

    Ningún modelo de core lo hereda: si lo hiciera, core dependería de
    usuarios en las migraciones y, como Usuario apunta a Pais, se formaría un
    ciclo (spec 001, §4).

    creado_por y actualizado_por los llena el servicio que escribe, no el
    modelo. related_name="+" evita que Usuario acumule una relación inversa
    por cada modelo que herede de aquí.
    """

    creado_en = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Moneda(models.Model):
    codigo = models.CharField(
        max_length=3, unique=True, validators=[validar_codigo_iso]
    )
    nombre = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=5)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "moneda"
        verbose_name_plural = "monedas"

    def __str__(self) -> str:
        return self.codigo


class Pais(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo_iso = models.CharField(
        max_length=3, unique=True, validators=[validar_codigo_iso]
    )
    # PROTECT: no se puede borrar una moneda que un país usa.
    moneda_principal = models.ForeignKey(
        Moneda, on_delete=models.PROTECT, related_name="paises"
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "país"
        verbose_name_plural = "países"

    def __str__(self) -> str:
        return self.nombre


class Ciudad(models.Model):
    nombre = models.CharField(max_length=100)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="ciudades")
    # Opcional. Django recomienda texto vacío y no nulo en los campos de texto,
    # para que "sin región" tenga una sola representación.
    region = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["pais__nombre", "nombre"]
        verbose_name = "ciudad"
        verbose_name_plural = "ciudades"
        constraints = [
            # Puede haber dos "San José" en países distintos, no en el mismo.
            models.UniqueConstraint(
                fields=["nombre", "pais"], name="core_ciudad_unica_por_pais"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nombre}, {self.pais}"


class TipoCambio(models.Model):
    """
    Cuántas unidades de moneda_destino vale una unidad de moneda_origen en una
    fecha. No lleva activo: una tasa equivocada se corrige editándola.
    """

    moneda_origen = models.ForeignKey(
        Moneda, on_delete=models.PROTECT, related_name="tipos_cambio_origen"
    )
    moneda_destino = models.ForeignKey(
        Moneda, on_delete=models.PROTECT, related_name="tipos_cambio_destino"
    )
    tasa = models.DecimalField(max_digits=18, decimal_places=6)
    fecha = models.DateField()

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "tipo de cambio"
        verbose_name_plural = "tipos de cambio"
        # Las tres reglas viven en la base de datos y no solo en Python: así
        # se cumplen aunque el dato entre por el panel, un script o el seed.
        constraints = [
            # Regla 4. El índice que crea también acelera la búsqueda de la
            # tasa vigente, que filtra por estas mismas columnas.
            models.UniqueConstraint(
                fields=["moneda_origen", "moneda_destino", "fecha"],
                name="core_tipo_cambio_unico_por_fecha",
            ),
            # Regla 5.
            models.CheckConstraint(
                condition=Q(tasa__gt=0), name="core_tipo_cambio_tasa_positiva"
            ),
            models.CheckConstraint(
                condition=~Q(moneda_origen=F("moneda_destino")),
                name="core_tipo_cambio_monedas_distintas",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.moneda_origen}→{self.moneda_destino} {self.fecha}: {self.tasa}"
