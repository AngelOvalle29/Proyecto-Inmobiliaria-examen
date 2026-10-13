"""Serializadores de core: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.
"""

from rest_framework import serializers

# Valores posibles del servicio y de la base de datos. Tiene nombre propio en
# SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"] para que la documentación los
# muestre como un solo tipo y no como dos con las mismas opciones.
ESTADOS_SALUD = ["ok", "error"]


class EstadoServicioSerializer(serializers.Serializer):
    """Respuesta de /health/. También documenta su forma en /api/docs/."""

    estado = serializers.ChoiceField(choices=ESTADOS_SALUD)
    base_datos = serializers.ChoiceField(choices=ESTADOS_SALUD)
