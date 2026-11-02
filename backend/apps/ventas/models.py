"""Modelos de ventas: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import ModeloBase

from .enums import EstadoContrato, EstadoCuota, ModalidadVenta

FINANCIADO = Q(modalidad=ModalidadVenta.FINANCIADO)
CONTADO = Q(modalidad=ModalidadVenta.CONTADO)


class ContratoVenta(ModeloBase):
    """
    Venta de una propiedad o una unidad a un cliente (spec 007, reglas 7 a 15).

    Lleva los datos que antes eran de PlanPago (número de cuotas, tasa y
    primera cuota): el plan de una semana (#28) lo dejó dentro del contrato.
    """

    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    # Regla 7: cada cotización da lugar a un contrato como máximo. crm consulta
    # esta relación por su nombre inverso (cotizacion_tiene_contrato).
    cotizacion = models.OneToOneField(
        "crm.Cotizacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contrato_venta",
    )
    cliente = models.ForeignKey(
        "crm.Cliente", on_delete=models.PROTECT, related_name="contratos_venta"
    )
    # La comisión es de este agente (regla 13), aunque después se reasigne
    # el cliente.
    agente = models.ForeignKey(
        "crm.Agente", on_delete=models.PROTECT, related_name="contratos_venta"
    )
    propiedad = models.ForeignKey(
        "catalogo.Propiedad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contratos_venta",
    )
    unidad = models.ForeignKey(
        "catalogo.Unidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contratos_venta",
    )
    fecha_firma = models.DateField()
    monto_total = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="contratos_venta"
    )
    # Regla 14: tasa de la moneda del contrato al dólar en la fecha de firma,
    # y el monto ya convertido, para que los reportes no recalculen el pasado.
    tasa_a_usd = models.DecimalField(max_digits=18, decimal_places=6)
    monto_total_usd = models.DecimalField(max_digits=18, decimal_places=2)
    modalidad = models.CharField(max_length=10, choices=ModalidadVenta.choices)
    enganche = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    # Solo para FINANCIADO (regla 11); nulos en un contrato de contado.
    numero_cuotas = models.PositiveSmallIntegerField(null=True, blank=True)
    tasa_interes_anual = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    fecha_primera_cuota = models.DateField(null=True, blank=True)
    comision_agente = models.DecimalField(max_digits=18, decimal_places=2)
    estado = models.CharField(
        max_length=10, choices=EstadoContrato.choices, default=EstadoContrato.VIGENTE
    )
    observaciones = models.TextField(blank=True)
    # El contrato firmado, escaneado, entre los documentos de la propiedad. Lo
    # apunta el contrato y no al revés: catalogo no depende de ventas (spec 011,
    # §10). Opcional: suele subirse después de firmar.
    documento = models.ForeignKey(
        "catalogo.DocumentoOficial",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contratos_venta",
    )

    class Meta:
        ordering = ["-fecha_firma", "-id"]
        verbose_name = "contrato de venta"
        verbose_name_plural = "contratos de venta"
        indexes = [
            models.Index(fields=["estado"], name="ventas_contrato_estado_idx"),
            models.Index(fields=["fecha_firma"], name="ventas_contrato_firma_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(propiedad__isnull=False) & Q(unidad__isnull=True))
                | (Q(propiedad__isnull=True) & Q(unidad__isnull=False)),
                name="ventas_contrato_propiedad_o_unidad",
            ),
            models.CheckConstraint(
                condition=Q(monto_total__gt=0), name="ventas_contrato_monto_positivo"
            ),
            models.CheckConstraint(
                condition=Q(tasa_a_usd__gt=0), name="ventas_contrato_tasa_positiva"
            ),
            models.CheckConstraint(
                condition=Q(enganche__gte=0) & Q(enganche__lt=F("monto_total")),
                name="ventas_contrato_enganche_en_rango",
            ),
            # Regla 11: un financiado tiene sus datos de plan, en rango...
            # isnull=False es necesario: en SQL, NULL >= 1 no es falso sino
            # desconocido, y un CHECK acepta las filas donde da desconocido.
            # Sin él, un financiado sin número de cuotas pasaría.
            models.CheckConstraint(
                condition=CONTADO
                | (
                    Q(numero_cuotas__isnull=False)
                    & Q(tasa_interes_anual__isnull=False)
                    & Q(numero_cuotas__gte=1)
                    & Q(numero_cuotas__lte=360)
                    & Q(tasa_interes_anual__gte=0)
                    & Q(tasa_interes_anual__lte=100)
                    & Q(fecha_primera_cuota__isnull=False)
                ),
                name="ventas_contrato_financiado_completo",
            ),
            # ...y uno de contado no los tiene.
            models.CheckConstraint(
                condition=FINANCIADO
                | (
                    Q(numero_cuotas__isnull=True)
                    & Q(tasa_interes_anual__isnull=True)
                    & Q(fecha_primera_cuota__isnull=True)
                    & Q(enganche=0)
                ),
                name="ventas_contrato_contado_sin_plan",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.cliente}"

    @property
    def bien(self):
        """La propiedad o la unidad vendida, la que no sea nula."""
        return self.propiedad or self.unidad


class CuotaPago(ModeloBase):
    """
    Una cuota mensual de un contrato financiado (spec 007, reglas 12 y 16 a
    18). Los pagos parciales se acumulan en monto_pagado; la historia de cada
    pago queda en la bitácora de auditoría.
    """

    contrato = models.ForeignKey(
        ContratoVenta, on_delete=models.PROTECT, related_name="cuotas"
    )
    numero = models.PositiveSmallIntegerField()
    fecha_vencimiento = models.DateField()
    monto_capital = models.DecimalField(max_digits=18, decimal_places=2)
    monto_interes = models.DecimalField(max_digits=18, decimal_places=2)
    monto_total = models.DecimalField(max_digits=18, decimal_places=2)
    estado = models.CharField(
        max_length=10, choices=EstadoCuota.choices, default=EstadoCuota.PENDIENTE
    )
    monto_pagado = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fecha_ultimo_pago = models.DateField(null=True, blank=True)
    referencia_ultimo_pago = models.CharField(max_length=100, blank=True)
    tasa_a_usd_ultimo_pago = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )

    class Meta:
        ordering = ["contrato_id", "numero"]
        verbose_name = "cuota de pago"
        verbose_name_plural = "cuotas de pago"
        indexes = [
            models.Index(fields=["estado"], name="ventas_cuota_estado_idx"),
            models.Index(
                fields=["fecha_vencimiento"], name="ventas_cuota_vencimiento_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["contrato", "numero"], name="ventas_cuota_unica_por_numero"
            ),
            models.CheckConstraint(
                condition=Q(monto_total=F("monto_capital") + F("monto_interes")),
                name="ventas_cuota_total_cuadra",
            ),
            # Regla 16: no se paga de más.
            models.CheckConstraint(
                condition=Q(monto_pagado__gte=0)
                & Q(monto_pagado__lte=F("monto_total")),
                name="ventas_cuota_pagado_en_rango",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contrato.codigo} cuota {self.numero}"

    @property
    def saldo(self):
        """Lo que falta pagar de la cuota."""
        return self.monto_total - self.monto_pagado

    def en_mora(self, hoy=None) -> bool:
        """
        Regla 17: una cuota no pagada del todo y con fecha vencida de un
        contrato vigente está en mora. Un contrato anulado ya no se cobra, así
        que sus cuotas no están en mora. No se guarda: se calcula con la fecha
        de hoy, así nunca queda desactualizada.
        """
        hoy = hoy or timezone.localdate()
        return (
            self.contrato.estado == EstadoContrato.VIGENTE
            and self.estado != EstadoCuota.PAGADA
            and self.fecha_vencimiento < hoy
        )
