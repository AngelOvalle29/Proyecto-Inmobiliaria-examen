"""Modelos de compras: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import F, Q

from apps.core.models import ModeloBase

from .enums import EstadoContratoCompra, TipoProveedor


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


class ContratoCompra(ModeloBase):
    """
    Compra de una propiedad a un proveedor (spec 017, reglas 1 a 8).

    Completarlo pasa la propiedad de EN_NEGOCIACION a ADQUIRIDA; eso lo hace el
    servicio con cambiar_estado_propiedad del catálogo, nunca el modelo.
    """

    # Nulo solo durante la creación, como el código del proveedor.
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)  # noqa: DJ001
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name="contratos"
    )
    propiedad = models.ForeignKey(
        "catalogo.Propiedad", on_delete=models.PROTECT, related_name="contratos_compra"
    )
    fecha_compra = models.DateField()
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    gastos_legales = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    impuestos = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    # Regla 3: lo calcula el servicio. Se guarda (y no se calcula al leer) para
    # que los reportes de rentabilidad de D lo usen sin repetir la suma.
    costo_total = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="contratos_compra"
    )
    # Regla 5: tasa al dólar de la fecha de compra y el costo ya convertido,
    # como en ventas (spec 007, regla 14), para no recalcular el pasado.
    tasa_a_usd = models.DecimalField(max_digits=18, decimal_places=6)
    costo_total_usd = models.DecimalField(max_digits=18, decimal_places=2)
    estado = models.CharField(
        max_length=10,
        choices=EstadoContratoCompra.choices,
        default=EstadoContratoCompra.EN_PROCESO,
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_compra", "-id"]
        verbose_name = "contrato de compra"
        verbose_name_plural = "contratos de compra"
        indexes = [
            models.Index(fields=["estado"], name="compras_contrato_estado_idx"),
            models.Index(fields=["fecha_compra"], name="compras_contrato_fecha_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__gt=0), name="compras_contrato_monto_positivo"
            ),
            models.CheckConstraint(
                condition=Q(gastos_legales__gte=0) & Q(impuestos__gte=0),
                name="compras_contrato_cargos_no_negativos",
            ),
            models.CheckConstraint(
                condition=Q(
                    costo_total=F("monto") + F("gastos_legales") + F("impuestos")
                ),
                name="compras_contrato_costo_total_es_la_suma",
            ),
            models.CheckConstraint(
                condition=Q(tasa_a_usd__gt=0), name="compras_contrato_tasa_positiva"
            ),
            # Regla 2: un solo contrato no anulado por propiedad. La condición
            # deja tener varios anulados. Es la garantía final aunque dos
            # peticiones lleguen al mismo tiempo; el servicio revisa antes para
            # responder 409 con un mensaje claro.
            models.UniqueConstraint(
                fields=["propiedad"],
                condition=~Q(estado=EstadoContratoCompra.ANULADO),
                name="compras_contrato_unico_no_anulado_por_propiedad",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.propiedad_id}"
