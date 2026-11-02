"""Serializadores de IA: validan el formato de entrada y arman la salida.

Sin reglas de negocio ni acceso a la base de datos.
"""

from rest_framework import serializers


class ConsultaAgenteSerializer(serializers.Serializer):
    # Regla 8: entre 3 y 500 caracteres. Los espacios de los extremos no
    # cuentan, así "   " no pasa como pregunta.
    pregunta = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


class CitaSerializer(serializers.Serializer):
    numero = serializers.IntegerField()
    documento = serializers.CharField()
    seccion = serializers.CharField()
    tipo = serializers.CharField()
    extracto = serializers.CharField()


class RespuestaAgenteSerializer(serializers.Serializer):
    respuesta = serializers.CharField()
    sin_informacion = serializers.BooleanField()
    citas = CitaSerializer(many=True)
