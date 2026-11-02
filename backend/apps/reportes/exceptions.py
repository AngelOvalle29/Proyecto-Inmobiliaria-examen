"""Excepciones de dominio de reportes.

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class ReporteDemasiadoGrande(ErrorDominio):
    """La exportación síncrona exige acotar el conjunto de resultados."""

    codigo = "REPORTE_DEMASIADO_GRANDE"
