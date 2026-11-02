"""Modelos de construcción: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.db import models
from django.db.models import F, Q

from apps.core.models import ModeloBase

from .enums import ESTADOS_ACTIVOS, EstadoPago, EstadoProyecto, TipoPagoConstructora


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


class ProyectoConstruccion(ModeloBase):
    """
    Obra que una constructora hace sobre una propiedad de la agencia (spec 017,
    reglas 9 a 18).

    Iniciar, finalizar y cancelar cambian el estado de la propiedad; eso lo
    hacen los servicios con cambiar_estado_propiedad del catálogo, nunca el
    modelo.
    """

    # Nulo solo durante la creación, como en Constructora.
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)  # noqa: DJ001
    nombre = models.CharField(max_length=200)
    propiedad = models.ForeignKey(
        "catalogo.Propiedad",
        on_delete=models.PROTECT,
        related_name="proyectos_construccion",
    )
    constructora = models.ForeignKey(
        Constructora, on_delete=models.PROTECT, related_name="proyectos"
    )
    fecha_inicio = models.DateField()
    fecha_fin_estimada = models.DateField()
    # Nula hasta finalizar; la pone el servicio con la fecha de hoy (regla 15).
    fecha_fin_real = models.DateField(null=True, blank=True)
    presupuesto_total = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="proyectos_construccion"
    )
    # Regla 11: tasa al dólar de la fecha de inicio. Si el presupuesto cambia,
    # se convierte con esta misma tasa, para que un presupuesto subido no cambie
    # el costo en dólares de lo ya planificado.
    tasa_a_usd = models.DecimalField(max_digits=18, decimal_places=6)
    presupuesto_total_usd = models.DecimalField(max_digits=18, decimal_places=2)
    estado = models.CharField(
        max_length=15,
        choices=EstadoProyecto.choices,
        default=EstadoProyecto.PLANIFICADO,
    )
    porcentaje_avance = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-fecha_inicio", "-id"]
        verbose_name = "proyecto de construcción"
        verbose_name_plural = "proyectos de construcción"
        indexes = [
            models.Index(fields=["estado"], name="construccion_proy_estado_idx"),
            models.Index(fields=["fecha_inicio"], name="construccion_proy_inicio_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(presupuesto_total__gt=0),
                name="construccion_proyecto_presupuesto_positivo",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin_estimada__gte=F("fecha_inicio")),
                name="construccion_proyecto_fin_no_antes_del_inicio",
            ),
            models.CheckConstraint(
                condition=Q(porcentaje_avance__gte=0) & Q(porcentaje_avance__lte=100),
                name="construccion_proyecto_avance_0_a_100",
            ),
            models.CheckConstraint(
                condition=Q(tasa_a_usd__gt=0),
                name="construccion_proyecto_tasa_positiva",
            ),
            # Regla 10: un solo proyecto activo por propiedad. Los finalizados y
            # cancelados no cuentan. Es la garantía final aunque dos peticiones
            # lleguen al mismo tiempo, como el contrato de compra.
            models.UniqueConstraint(
                fields=["propiedad"],
                condition=Q(estado__in=ESTADOS_ACTIVOS),
                name="construccion_proyecto_unico_activo_por_propiedad",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre}"


class PagoConstructora(ModeloBase):
    """
    Pago a la constructora por una obra (spec 017, reglas 19 a 21).

    No guarda la constructora: sale del proyecto. Guardarla dos veces
    permitiría un pago a una constructora distinta de la de su obra (§10).
    """

    # Nulo solo durante la creación, como el código del proyecto.
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)  # noqa: DJ001
    proyecto = models.ForeignKey(
        ProyectoConstruccion, on_delete=models.PROTECT, related_name="pagos"
    )
    tipo = models.CharField(max_length=10, choices=TipoPagoConstructora.choices)
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    # La del proyecto: la asigna el servicio, no la elige el usuario (regla 20).
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="pagos_constructora"
    )
    fecha_programada = models.DateField()
    estado = models.CharField(
        max_length=10, choices=EstadoPago.choices, default=EstadoPago.PROGRAMADO
    )
    # Vacíos hasta pagar (regla 21).
    fecha_pago = models.DateField(null=True, blank=True)
    referencia_pago = models.CharField(max_length=100, blank=True)
    # La tasa es la de la fecha de pago, no la de la programación: lo que
    # importa a los reportes es cuánto costó en dólares el día que salió el
    # dinero.
    tasa_a_usd = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    monto_usd = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    documento = models.ForeignKey(
        "catalogo.DocumentoOficial",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos_constructora",
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["fecha_programada", "id"]
        verbose_name = "pago a constructora"
        verbose_name_plural = "pagos a constructoras"
        indexes = [
            models.Index(fields=["estado"], name="construccion_pago_estado_idx"),
            models.Index(
                fields=["fecha_programada"], name="construccion_pago_fecha_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__gt=0), name="construccion_pago_monto_positivo"
            ),
            # Un pago PAGADO tiene sus datos de pago. isnull=False hace falta:
            # en SQL un CHECK acepta las filas donde la condición da
            # desconocido, y una comparación con NULL da desconocido.
            models.CheckConstraint(
                condition=~Q(estado=EstadoPago.PAGADO)
                | (
                    Q(fecha_pago__isnull=False)
                    & ~Q(referencia_pago="")
                    & Q(tasa_a_usd__isnull=False)
                    & Q(tasa_a_usd__gt=0)
                    & Q(monto_usd__isnull=False)
                ),
                name="construccion_pago_pagado_completo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.proyecto_id}"
