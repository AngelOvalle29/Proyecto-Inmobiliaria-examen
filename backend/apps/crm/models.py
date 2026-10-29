"""Modelos de CRM: campos, relaciones, constraints y validación propia.

No llaman a servicios ni envían correos.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import ModeloBase

from .enums import EstadoCotizacion, TipoCliente


class Agente(ModeloBase):
    """
    Perfil comercial de un usuario con rol AGENTE (spec 004, reglas 1 a 3).

    Solo guarda lo propio del agente. Nombre, teléfono, correo y país se leen
    de su usuario: duplicarlos aquí haría que tarde o temprano no coincidan
    (regla 2). activo y los campos de rastro vienen de ModeloBase.
    """

    # PROTECT: un usuario con perfil de agente no se puede borrar. Los usuarios
    # se desactivan con is_active, nunca se borran (spec 001).
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="agente"
    )
    # Lo asigna el servicio a partir del id (AGT-001) en la misma transacción
    # que crea el registro. Es nulo solo en ese instante: dos nulos no chocan
    # con unique en PostgreSQL, dos cadenas vacías sí (spec 004, §4).
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_ingreso = models.DateField()

    class Meta:
        ordering = ["codigo"]
        verbose_name = "agente"
        verbose_name_plural = "agentes"
        constraints = [
            # Regla 3. En la base y no solo en Python, para que se cumpla
            # aunque el dato entre por un script.
            models.CheckConstraint(
                condition=Q(porcentaje_comision__gte=0)
                & Q(porcentaje_comision__lte=100),
                name="crm_agente_comision_entre_0_y_100",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.usuario.nombre_completo}"


class Cliente(ModeloBase):
    """
    Persona o empresa que la agencia atiende (spec 004, reglas 6 a 10).

    Los campos de texto opcionales usan cadena vacía y no nulo, como
    Ciudad.region en la spec 001: "sin dato" tiene una sola representación.
    """

    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=TipoCliente.choices)

    # Persona
    nombre = models.CharField(max_length=100, blank=True)
    apellidos = models.CharField(max_length=100, blank=True)
    documento_identidad = models.CharField(max_length=30, blank=True)

    # Empresa (el NIT también es opcional para una persona)
    razon_social = models.CharField(max_length=200, blank=True)
    nit = models.CharField(max_length=30, blank=True)

    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    pais = models.ForeignKey(
        "core.Pais", on_delete=models.PROTECT, related_name="clientes"
    )
    # Opcional: el catálogo solo tiene algunas ciudades por país. Que la ciudad
    # sea del país del cliente (regla 9) lo valida el servicio, porque compara
    # con otra tabla.
    ciudad = models.ForeignKey(
        "core.Ciudad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clientes",
    )
    direccion = models.CharField(max_length=255, blank=True)
    # PROTECT: un agente con clientes no se puede borrar (y tampoco
    # desactivar, regla 4, pero eso lo valida el servicio).
    agente_asignado = models.ForeignKey(
        Agente, on_delete=models.PROTECT, related_name="clientes"
    )
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [
            # Regla 6. Se leen así: "o no es persona, o tiene los tres datos".
            models.CheckConstraint(
                condition=~Q(tipo=TipoCliente.PERSONA)
                | (~Q(nombre="") & ~Q(apellidos="") & ~Q(documento_identidad="")),
                name="crm_cliente_persona_completa",
            ),
            models.CheckConstraint(
                condition=~Q(tipo=TipoCliente.EMPRESA)
                | (~Q(razon_social="") & ~Q(nit="")),
                name="crm_cliente_empresa_completa",
            ),
            # Regla 7. Únicos por país y solo dentro de su tipo: el DPI de
            # Guatemala y la cédula de Costa Rica son sistemas distintos, y el
            # NIT opcional de una persona no compite con el de una empresa.
            # Incluye a los clientes desactivados: un cliente dado de baja no
            # se vuelve a registrar como nuevo.
            models.UniqueConstraint(
                fields=["pais", "documento_identidad"],
                condition=Q(tipo=TipoCliente.PERSONA),
                name="crm_cliente_documento_unico_por_pais",
            ),
            models.UniqueConstraint(
                fields=["pais", "nit"],
                condition=Q(tipo=TipoCliente.EMPRESA),
                name="crm_cliente_nit_unico_por_pais",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.nombre_mostrado}"

    @property
    def nombre_mostrado(self) -> str:
        """Cómo se nombra al cliente en pantallas y reportes."""
        if self.tipo == TipoCliente.EMPRESA:
            return self.razon_social
        return f"{self.nombre} {self.apellidos}"


class Cotizacion(ModeloBase):
    """
    Propuesta de precio a un cliente por una propiedad o una unidad (spec 007,
    reglas 1 a 6). El detalle va en la propia cotización: no hay
    CotizacionDetalle (plan de una semana, #28).
    """

    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="cotizaciones"
    )
    # Regla 3: es el agente asignado al cliente al crear la cotización. Se
    # guarda para que una reasignación posterior no cambie quién la emitió.
    agente = models.ForeignKey(
        Agente, on_delete=models.PROTECT, related_name="cotizaciones"
    )
    # Regla 1: exactamente una de las dos (constraint abajo).
    propiedad = models.ForeignKey(
        "catalogo.Propiedad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )
    unidad = models.ForeignKey(
        "catalogo.Unidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(
        max_length=10,
        choices=EstadoCotizacion.choices,
        default=EstadoCotizacion.BORRADOR,
    )
    # Regla 2: el total lo calcula el servicio; los constraints garantizan que
    # cuadre aunque el dato entre por otro lado.
    precio = models.DecimalField(max_digits=18, decimal_places=2)
    descuento = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2)
    moneda = models.ForeignKey(
        "core.Moneda", on_delete=models.PROTECT, related_name="cotizaciones"
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_emision", "-id"]
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        indexes = [models.Index(fields=["estado"], name="crm_cotizacion_estado_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(Q(propiedad__isnull=False) & Q(unidad__isnull=True))
                | (Q(propiedad__isnull=True) & Q(unidad__isnull=False)),
                name="crm_cotizacion_propiedad_o_unidad",
            ),
            models.CheckConstraint(
                condition=Q(precio__gt=0), name="crm_cotizacion_precio_positivo"
            ),
            models.CheckConstraint(
                condition=Q(descuento__gte=0) & Q(descuento__lte=F("precio")),
                name="crm_cotizacion_descuento_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(total=F("precio") - F("descuento")),
                name="crm_cotizacion_total_cuadra",
            ),
            models.CheckConstraint(
                condition=Q(fecha_vencimiento__gte=F("fecha_emision")),
                name="crm_cotizacion_vence_despues_de_emitirse",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.cliente.nombre_mostrado}"

    @property
    def bien(self):
        """La propiedad o la unidad cotizada, la que no sea nula."""
        return self.propiedad or self.unidad

    def esta_vencida(self, hoy=None) -> bool:
        """
        Regla 4: una cotización todavía sin decidir (borrador o enviada) está
        vencida si su fecha de vencimiento ya pasó. No se guarda: se calcula,
        como la mora (regla 17), así nunca queda desactualizada.
        """
        hoy = hoy or timezone.localdate()
        abierta = self.estado in (EstadoCotizacion.BORRADOR, EstadoCotizacion.ENVIADA)
        return abierta and self.fecha_vencimiento < hoy
