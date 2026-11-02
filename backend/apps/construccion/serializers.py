"""Serializadores de construcción: validan el formato de entrada y arman la
salida.

Sin reglas de negocio ni acceso a la base de datos: los ids se resuelven con
los selectores de core, catalogo y construcción, como en crm y ventas.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.catalogo.selectors import listar_propiedades
from apps.catalogo.serializers import PropiedadResumenSerializer
from apps.core.selectors import listar_monedas, listar_paises
from apps.core.serializers import MonedaResumenSerializer, PaisResumenSerializer

from .models import Constructora, ProyectoConstruccion
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


class MotivoProyectoSerializer(serializers.Serializer):
    """Entrada de /suspender/ y /cancelar/: el motivo es obligatorio."""

    motivo = serializers.CharField(max_length=255)
