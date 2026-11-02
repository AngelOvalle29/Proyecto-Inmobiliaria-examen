"""Serializadores de construcción: validan el formato de entrada y arman la
salida.

Sin reglas de negocio ni acceso a la base de datos: los ids se resuelven con
los selectores de core, catalogo y construcción, como en crm y ventas.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.catalogo.selectors import listar_documentos, listar_propiedades
from apps.catalogo.serializers import (
    DocumentoOficialResumenSerializer,
    PropiedadResumenSerializer,
)
from apps.core.selectors import listar_monedas, listar_paises
from apps.core.serializers import MonedaResumenSerializer, PaisResumenSerializer

from .enums import TipoPagoConstructora
from .models import Constructora, PagoConstructora, ProyectoConstruccion
from .selectors import listar_constructoras


class ConstructoraSerializer(serializers.ModelSerializer):
    """Salida de una constructora, con su país resumido."""

    pais = PaisResumenSerializer()

    class Meta:
        model = Constructora
        fields = [
            "id",
            "codigo",
            "nombre",
            "nit",
            "contacto",
            "email",
            "telefono",
            "pais",
            "calificacion",
            "activo",
        ]


class ConstructoraEntradaSerializer(serializers.Serializer):
    """Entrada para crear (POST) o editar (PATCH, parcial) una constructora."""

    nombre = serializers.CharField(max_length=200)
    # Obligatorio (regla 4). Si queda vacío al normalizarlo, lo rechaza el servicio.
    nit = serializers.CharField(max_length=30)
    contacto = serializers.CharField(max_length=150, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    telefono = serializers.CharField(max_length=30, allow_blank=True, default="")
    pais = serializers.PrimaryKeyRelatedField(queryset=listar_paises())
    # Regla 6: de 1 a 5, u omitida mientras no haya trabajos que calificar.
    calificacion = serializers.IntegerField(
        min_value=1, max_value=5, allow_null=True, default=None
    )


# ---------- Proyectos de construcción (spec 017) ----------


class ConstructoraResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()


class ProyectoSerializer(serializers.ModelSerializer):
    """Salida de un proyecto, con su propiedad, constructora y moneda."""

    propiedad = PropiedadResumenSerializer()
    constructora = ConstructoraResumenSerializer()
    moneda = MonedaResumenSerializer()

    class Meta:
        model = ProyectoConstruccion
        fields = [
            "id",
            "codigo",
            "nombre",
            "propiedad",
            "constructora",
            "fecha_inicio",
            "fecha_fin_estimada",
            "fecha_fin_real",
            "presupuesto_total",
            "moneda",
            "tasa_a_usd",
            "presupuesto_total_usd",
            "estado",
            "porcentaje_avance",
        ]


class ProyectoDetalleSerializer(ProyectoSerializer):
    """
    Detalle de un proyecto: lo de la lista más total_comprometido y disponible,
    que calcula el selector listar_proyectos_con_totales (spec 017, §5). Así la
    pantalla (spec 018) no suma los pagos por su cuenta.
    """

    total_comprometido = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )
    disponible = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta(ProyectoSerializer.Meta):
        fields = [*ProyectoSerializer.Meta.fields, "total_comprometido", "disponible"]


class ProyectoEntradaSerializer(serializers.Serializer):
    """
    Entrada para registrar un proyecto (POST). Solo valida el formato: que la
    propiedad esté adquirida y sin otra obra activa, las fechas y la tasa los
    revisa el servicio (spec 017, reglas 9 a 11).

    La constructora se busca entre las activas: una desactivada responde 400
    como si no existiera (regla 9).
    """

    nombre = serializers.CharField(max_length=200)
    propiedad = serializers.PrimaryKeyRelatedField(queryset=listar_propiedades())
    constructora = serializers.PrimaryKeyRelatedField(queryset=listar_constructoras())
    fecha_inicio = serializers.DateField()
    fecha_fin_estimada = serializers.DateField()
    presupuesto_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    moneda = serializers.PrimaryKeyRelatedField(queryset=listar_monedas())


class ProyectoEdicionSerializer(serializers.Serializer):
    """
    Entrada de PATCH: solo los tres campos que la regla 17 deja editar. Qué se
    puede cambiar según el estado del proyecto lo decide el servicio.
    """

    nombre = serializers.CharField(max_length=200, required=False)
    fecha_fin_estimada = serializers.DateField(required=False)
    presupuesto_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01"), required=False
    )


class AvanceSerializer(serializers.Serializer):
    """Entrada de /avance/ (regla 13). Que no baje lo revisa el servicio."""

    porcentaje = serializers.IntegerField(min_value=0, max_value=100)
    descripcion = serializers.CharField(max_length=500)


class MotivoConstruccionSerializer(serializers.Serializer):
    """
    Entrada de las acciones que solo piden un motivo: suspender o cancelar un
    proyecto y anular un pago. El motivo es obligatorio y queda en la bitácora.
    """

    motivo = serializers.CharField(max_length=255)


# ---------- Pagos a constructoras (spec 017) ----------


class ProyectoDePagoSerializer(serializers.Serializer):
    """El proyecto de un pago, con su constructora: el pago no la repite (§10)."""

    id = serializers.IntegerField()
    codigo = serializers.CharField()
    constructora = ConstructoraResumenSerializer()


class PagoSerializer(serializers.ModelSerializer):
    """Salida de un pago a constructora."""

    proyecto = ProyectoDePagoSerializer()
    moneda = MonedaResumenSerializer()
    documento = DocumentoOficialResumenSerializer(allow_null=True)

    class Meta:
        model = PagoConstructora
        fields = [
            "id",
            "codigo",
            "proyecto",
            "tipo",
            "monto",
            "moneda",
            "fecha_programada",
            "estado",
            "fecha_pago",
            "referencia_pago",
            "tasa_a_usd",
            "monto_usd",
            "documento",
            "observaciones",
        ]


class ProgramarPagoSerializer(serializers.Serializer):
    """
    Entrada de POST /proyectos-construccion/{id}/pagos/. La moneda no se
    recibe: es la del proyecto (regla 20). El presupuesto, el finiquito y que
    el documento sea de la misma propiedad los revisa el servicio.
    """

    tipo = serializers.ChoiceField(choices=TipoPagoConstructora.choices)
    monto = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0.01")
    )
    fecha_programada = serializers.DateField()
    documento = serializers.PrimaryKeyRelatedField(
        queryset=listar_documentos(), allow_null=True, default=None
    )
    observaciones = serializers.CharField(allow_blank=True, default="")


class PagarSerializer(serializers.Serializer):
    """Entrada de /pagar/ (regla 21). Las reglas de la fecha, en el servicio."""

    fecha_pago = serializers.DateField()
    referencia_pago = serializers.CharField(max_length=100)
