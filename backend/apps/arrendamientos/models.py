"""Modelos de arrendamientos: campos, relaciones, constraints y validación
propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import ModeloBase

from .enums import EstadoArrendamiento, EstadoPagoRenta


class ContratoArrendamiento(ModeloBase):
    """
    Renta de una propiedad o una unidad a un cliente (spec 008, reglas 1 a 5 y
    9 a 12). Al firmarse se generan todos sus pagos de renta.
    """

    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    cliente = models.ForeignKey(
        "crm.Cliente", on_delete=models.PROTECT, related_name="arrendamientos"
    )
    agente = models.ForeignKey(
        "crm.Agente", on_delete=models.PROTECT, related_name="arrendamientos"
    )
    propiedad = models.ForeignKey(
        "catalogo.Propiedad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="arrendamientos",
    )
    unidad = models.ForeignKey(
        "catalogo.Unidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="arrendamientos",
    )
    fecha_inicio = models.DateField()
    # Regla 3: la duración se da en meses y la fecha de fin la calcula el
    # servicio, así el número de pagos es exacto.
    duracion_meses = models.PositiveSmallIntegerField()
    fecha_fin = models.DateField()
    renta_mensual = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="arrendamientos"
    )
    # Regla 5: tasa de la moneda al dólar en la fecha de firma.
    tasa_a_usd = models.DecimalField(max_digits=18, decimal_places=6)
    deposito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    dia_cobro = models.PositiveSmallIntegerField()
    dias_gracia = models.PositiveSmallIntegerField()
    porcentaje_mora = models.DecimalField(max_digits=5, decimal_places=2)
    estado = models.CharField(
        max_length=10,
        choices=EstadoArrendamiento.choices,
        default=EstadoArrendamiento.VIGENTE,
    )
    fecha_rescision = models.DateField(null=True, blank=True)
    # Regla 9: el contrato que este renueva. OneToOne: cada contrato se
    # renueva una sola vez.
    contrato_anterior = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="renovacion",
    )

    class Meta:
        ordering = ["-fecha_inicio", "-id"]
        verbose_name = "contrato de arrendamiento"
        verbose_name_plural = "contratos de arrendamiento"
        indexes = [
            models.Index(fields=["estado"], name="arrend_contrato_estado_idx"),
            models.Index(fields=["fecha_fin"], name="arrend_contrato_fin_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(propiedad__isnull=False) & Q(unidad__isnull=True))
                | (Q(propiedad__isnull=True) & Q(unidad__isnull=False)),
                name="arrend_contrato_propiedad_o_unidad",
            ),
            # Regla 3. Ningún campo de estos admite nulo, así que no hace falta
            # el isnull=False de la spec 007.
            models.CheckConstraint(
                condition=Q(duracion_meses__gte=1) & Q(duracion_meses__lte=120),
                name="arrend_contrato_duracion_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(dia_cobro__gte=1) & Q(dia_cobro__lte=28),
                name="arrend_contrato_dia_cobro_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(dias_gracia__lte=31),
                name="arrend_contrato_gracia_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(porcentaje_mora__gte=0) & Q(porcentaje_mora__lte=100),
                name="arrend_contrato_mora_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(renta_mensual__gt=0), name="arrend_contrato_renta_positiva"
            ),
            models.CheckConstraint(
                condition=Q(deposito__gte=0), name="arrend_contrato_deposito_positivo"
            ),
            models.CheckConstraint(
                condition=Q(tasa_a_usd__gt=0), name="arrend_contrato_tasa_positiva"
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__gt=F("fecha_inicio")),
                name="arrend_contrato_fin_despues_de_inicio",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.cliente}"

    @property
    def bien(self):
        """La propiedad o la unidad arrendada, la que no sea nula."""
        return self.propiedad or self.unidad


class PagoRenta(ModeloBase):
    """
    Un mes de renta de un contrato (spec 008, reglas 4 y 6 a 8). Se paga
    completo y una sola vez; el recargo por mora queda en mora_aplicada.
    """

    contrato = models.ForeignKey(
        ContratoArrendamiento, on_delete=models.PROTECT, related_name="pagos"
    )
    periodo_anio = models.PositiveSmallIntegerField()
    periodo_mes = models.PositiveSmallIntegerField()
    fecha_vencimiento = models.DateField()
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    estado = models.CharField(
        max_length=10,
        choices=EstadoPagoRenta.choices,
        default=EstadoPagoRenta.PENDIENTE,
    )
    fecha_pago = models.DateField(null=True, blank=True)
    monto_pagado = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    mora_aplicada = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    referencia_pago = models.CharField(max_length=100, blank=True)
    tasa_a_usd = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )

    class Meta:
        ordering = ["contrato_id", "fecha_vencimiento"]
        verbose_name = "pago de renta"
        verbose_name_plural = "pagos de renta"
        indexes = [
            models.Index(fields=["estado"], name="arrend_pago_estado_idx"),
            models.Index(
                fields=["fecha_vencimiento"], name="arrend_pago_vencimiento_idx"
            ),
        ]
        constraints = [
            # Regla 4 (docs/modelo-datos.md): un pago por contrato y mes.
            models.UniqueConstraint(
                fields=["contrato", "periodo_anio", "periodo_mes"],
                name="arrend_pago_unico_por_periodo",
            ),
            models.CheckConstraint(
                condition=Q(periodo_mes__gte=1) & Q(periodo_mes__lte=12),
                name="arrend_pago_mes_valido",
            ),
            models.CheckConstraint(
                condition=Q(monto__gt=0), name="arrend_pago_monto_positivo"
            ),
            models.CheckConstraint(
                condition=Q(mora_aplicada__gte=0), name="arrend_pago_mora_positiva"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contrato.codigo} {self.periodo_mes:02d}/{self.periodo_anio}"

    def en_mora(self, hoy=None) -> bool:
        """
        Regla 8: un pago pendiente con fecha de vencimiento pasada está en
        mora. No se guarda: se calcula con la fecha de hoy. El recargo, en
        cambio, solo se cobra después de los días de gracia (regla 6).
        """
        hoy = hoy or timezone.localdate()
        return self.estado == EstadoPagoRenta.PENDIENTE and self.fecha_vencimiento < hoy
