"""Serializadores de CRM: validan el formato de entrada y arman la salida.

Sin reglas de negocio. Los campos que reciben un id (pais, agente_asignado…)
validan que ese id exista con una consulta que viene de un selector, nunca
escrita aquí.
"""

from rest_framework import serializers

from apps.core.selectors import listar_ciudades, listar_paises
from apps.core.serializers import PaisResumenSerializer
from apps.usuarios.selectors import listar_usuarios_activos

from .enums import TipoCliente
from .models import Agente, Cliente
from .selectors import consultar_agentes_asignables

# Regla 6: qué datos exige cada tipo de cliente.
OBLIGATORIOS_POR_TIPO = {
    TipoCliente.PERSONA: ["nombre", "apellidos", "documento_identidad"],
    TipoCliente.EMPRESA: ["razon_social", "nit"],
}


# ---------- Resúmenes (relaciones dentro de otra respuesta) ----------


class UsuarioResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    nombre_completo = serializers.CharField()


class AgenteResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre_completo = serializers.CharField(source="usuario.nombre_completo")


class CiudadResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


# ---------- Agentes ----------


class AgenteSerializer(serializers.ModelSerializer):
    """Salida de un agente. Teléfono y país son los de su usuario (regla 2)."""

    usuario = UsuarioResumenSerializer()
    telefono = serializers.CharField(source="usuario.telefono")
    pais = PaisResumenSerializer(source="usuario.pais", allow_null=True)
    # Lo calcula el selector (listar_agentes) en la misma consulta.
    clientes_activos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Agente
        fields = [
            "id",
            "codigo",
            "usuario",
            "telefono",
            "pais",
            "porcentaje_comision",
            "fecha_ingreso",
            "clientes_activos",
        ]


class AgenteCrearSerializer(serializers.Serializer):
    usuario = serializers.PrimaryKeyRelatedField(queryset=listar_usuarios_activos())
    # El rango 0 a 100 también lo garantiza la base (regla 3); aquí se valida
    # para responder 400 indicando el campo.
    porcentaje_comision = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )
    fecha_ingreso = serializers.DateField()


class AgenteEditarSerializer(serializers.Serializer):
    porcentaje_comision = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False
    )
    fecha_ingreso = serializers.DateField(required=False)


# ---------- Clientes ----------


class ClienteSerializer(serializers.ModelSerializer):
    """Salida de un cliente (spec 004, §5)."""

    pais = PaisResumenSerializer()
    ciudad = CiudadResumenSerializer(allow_null=True)
    agente_asignado = AgenteResumenSerializer()

    class Meta:
        model = Cliente
        fields = [
            "id",
            "codigo",
            "tipo",
            "nombre",
            "apellidos",
            "razon_social",
            "documento_identidad",
            "nit",
            "email",
            "telefono",
            "pais",
            "ciudad",
            "direccion",
            "agente_asignado",
            "notas",
            "creado_en",
        ]


class ClienteEntradaSerializer(serializers.Serializer):
    """
    Entrada para crear (todos los obligatorios) o editar (PATCH, solo lo que
    cambia) un cliente.

    Valida el formato: tipos, longitudes, que los ids existan y que estén los
    datos que exige el tipo (regla 6), combinando lo que llega con lo que el
    cliente ya tenía al editar. Las reglas que comparan con otros registros
    (duplicados, ciudad del país, cartera) son del servicio.
    """

    tipo = serializers.ChoiceField(choices=TipoCliente.choices)
    nombre = serializers.CharField(max_length=100, required=False, allow_blank=True)
    apellidos = serializers.CharField(max_length=100, required=False, allow_blank=True)
    documento_identidad = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    razon_social = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    nit = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    pais = serializers.PrimaryKeyRelatedField(queryset=listar_paises())
    ciudad = serializers.PrimaryKeyRelatedField(
        queryset=listar_ciudades(), required=False, allow_null=True
    )
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notas = serializers.CharField(required=False, allow_blank=True)
    # Obligatorio solo para administrador y gerente; a un agente se le ignora
    # (regla 12). Ver validate().
    agente_asignado = serializers.PrimaryKeyRelatedField(
        queryset=consultar_agentes_asignables(), required=False
    )

    def validate(self, datos: dict) -> dict:
        def valor(campo):
            if campo in datos:
                return datos[campo]
            return getattr(self.instance, campo, "")

        errores = {}
        tipo = valor("tipo")
        for campo in OBLIGATORIOS_POR_TIPO.get(tipo, []):
            if not str(valor(campo)).strip():
                errores[campo] = [
                    f"Obligatorio para un cliente de tipo {TipoCliente(tipo).label}."
                ]

        es_alta = self.instance is None
        if (
            es_alta
            and not self.context.get("autor_es_agente")
            and "agente_asignado" not in datos
        ):
            errores["agente_asignado"] = ["Indique el agente que atenderá al cliente."]

        if errores:
            raise serializers.ValidationError(errores)
        return datos


class ReasignarClienteSerializer(serializers.Serializer):
    agente = serializers.PrimaryKeyRelatedField(queryset=consultar_agentes_asignables())
