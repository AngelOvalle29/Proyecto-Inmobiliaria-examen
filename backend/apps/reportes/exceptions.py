"""Excepciones de dominio de reportes.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class ReporteDemasiadoGrande(ErrorDominio):
    """La exportación síncrona exige acotar el conjunto de resultados."""

    codigo = "REPORTE_DEMASIADO_GRANDE"


class DatosCobrosIncompletos(ErrorDominio):
    """Los abonos no concilian con las cuotas o carecen de fecha/tasa válida."""

    codigo = "DATOS_INCOMPLETOS"
    estado_http = 409
