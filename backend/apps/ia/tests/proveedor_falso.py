"""Proveedor de IA falso para las pruebas: nunca llama a la red.

Devuelve vectores fijos que la prueba controla, y anota cada llamada para
poder comprobar qué se le pidió.
"""

from apps.ia.models import DIMENSION_EMBEDDINGS
from apps.ia.proveedores.base import (
    ProveedorIA,
    ProveedorIANoDisponible,
    RespuestaIA,
)


def vector_eje(eje: int) -> list[float]:
    """Vector unitario en un solo eje. Dos ejes distintos tienen distancia de
    coseno 1 (nada en común) y el mismo eje, distancia 0 (idénticos)."""
    vector = [0.0] * DIMENSION_EMBEDDINGS
    vector[eje] = 1.0
    return vector


def vector_mezcla(eje_a: int, eje_b: int, peso_a: float) -> list[float]:
    """Vector entre dos ejes. Respecto de vector_eje(eje_a), su distancia de
    coseno es 1 - peso_a / sqrt(peso_a² + (1 - peso_a)²)."""
    vector = [0.0] * DIMENSION_EMBEDDINGS
    vector[eje_a] = peso_a
    vector[eje_b] = 1 - peso_a
    return vector


class ProveedorFalso(ProveedorIA):
    def __init__(self) -> None:
        self.llamadas_embeddings: list[dict] = []
        self.llamadas_respuesta: list[dict] = []
        self.falla = False
        self.dimension = DIMENSION_EMBEDDINGS
        self.texto_respuesta = "Respuesta de prueba [1]."
        # Vector que se devuelve para un texto dado; los demás reciben uno fijo.
        self.vectores: dict[str, list[float]] = {}

    def generar_respuesta(self, *, mensajes, herramientas=None) -> RespuestaIA:
        self.llamadas_respuesta.append({"mensajes": mensajes})
        if self.falla:
            raise ProveedorIANoDisponible("falla simulada")
        return RespuestaIA(
            texto=self.texto_respuesta,
            modelo="modelo-falso",
            tokens_entrada=10,
            tokens_salida=5,
        )

    def generar_embedding(self, *, texto, tarea) -> list[float]:
        return self.generar_embeddings_lote(textos=[texto], tarea=tarea)[0]

    def generar_embeddings_lote(self, *, textos, tarea) -> list[list[float]]:
        self.llamadas_embeddings.append({"textos": list(textos), "tarea": tarea})
        if self.falla:
            raise ProveedorIANoDisponible("falla simulada")
        return [self.vectores.get(t, [0.1] * self.dimension) for t in textos]
