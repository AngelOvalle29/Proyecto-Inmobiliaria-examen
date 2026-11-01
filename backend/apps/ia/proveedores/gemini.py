"""Implementación de ProveedorIA con la API de Gemini (spec 005, §6).

Es el único archivo del proyecto que importa el SDK de Google (CLAUDE.md).
"""

import time
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors, types

from .base import (
    Herramienta,
    Mensaje,
    ProveedorIA,
    ProveedorIANoDisponible,
    RespuestaIA,
    RolMensaje,
    TareaEmbedding,
)

# Errores que suelen pasar solos: cuota por minuto (429), saturación (503) y
# fallas internas de Google (500, 504). Un 400 o un 401 no se arreglan
# reintentando, así que no se reintentan.
CODIGOS_REINTENTABLES = frozenset({429, 500, 503, 504})

# Espera antes del segundo y del tercer intento (regla 9 de la spec 005):
# tres intentos en total y, en el peor caso, tres segundos de espera.
ESPERAS_ENTRE_INTENTOS = (1, 2)

# Sin límite, una petición colgada dejaría la vista esperando para siempre:
# en la prueba del 2026-10-28, gemini-3.8-flash no respondió en 60 segundos.
TIEMPO_LIMITE_MS = 30_000

# Máximo de textos por petición de embeddings.
TAMANO_LOTE_EMBEDDINGS = 100

_ROLES_GEMINI = {RolMensaje.USUARIO: "user", RolMensaje.MODELO: "model"}

_TAREAS_GEMINI = {
    TareaEmbedding.DOCUMENTO: "RETRIEVAL_DOCUMENT",
    TareaEmbedding.CONSULTA: "RETRIEVAL_QUERY",
}


class ProveedorGemini(ProveedorIA):
    def __init__(
        self,
        *,
        api_key: str,
        modelo: str,
        modelo_embeddings: str,
        dimension_embeddings: int,
        max_tokens_respuesta: int,
        cliente=None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        # cliente y dormir se reciben para que las pruebas usen un cliente
        # falso y no esperen de verdad. En el sistema siempre van por defecto.
        self._cliente = cliente or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=TIEMPO_LIMITE_MS),
        )
        self._modelo = modelo
        self._modelo_embeddings = modelo_embeddings
        self._dimension_embeddings = dimension_embeddings
        self._max_tokens_respuesta = max_tokens_respuesta
        self._dormir = dormir

    def generar_respuesta(
        self,
        *,
        mensajes: list[Mensaje],
        herramientas: list[Herramienta] | None = None,
    ) -> RespuestaIA:
        if herramientas:
            raise NotImplementedError(
                "Las herramientas del agente llegan con su propia spec."
            )

        # Gemini recibe las instrucciones aparte de la conversación.
        instrucciones = "\n\n".join(
            m.contenido for m in mensajes if m.rol == RolMensaje.SISTEMA
        )
        contenidos = [
            types.Content(
                role=_ROLES_GEMINI[m.rol], parts=[types.Part(text=m.contenido)]
            )
            for m in mensajes
            if m.rol != RolMensaje.SISTEMA
        ]
        configuracion = types.GenerateContentConfig(
            system_instruction=instrucciones or None,
            max_output_tokens=self._max_tokens_respuesta,
        )

        respuesta = self._con_reintentos(
            lambda: self._cliente.models.generate_content(
                model=self._modelo, contents=contenidos, config=configuracion
            )
        )

        uso = respuesta.usage_metadata
        return RespuestaIA(
            texto=respuesta.text or "",
            modelo=self._modelo,
            tokens_entrada=(uso.prompt_token_count or 0) if uso else 0,
            tokens_salida=(uso.candidates_token_count or 0) if uso else 0,
        )

    def generar_embedding(self, *, texto: str, tarea: TareaEmbedding) -> list[float]:
        return self.generar_embeddings_lote(textos=[texto], tarea=tarea)[0]

    def generar_embeddings_lote(
        self, *, textos: list[str], tarea: TareaEmbedding
    ) -> list[list[float]]:
        # output_dimensionality siempre: sin él Gemini devuelve 3072 valores y
        # no caben en el campo vector(768) (spec 005, §10).
        configuracion = types.EmbedContentConfig(
            task_type=_TAREAS_GEMINI[tarea],
            output_dimensionality=self._dimension_embeddings,
        )
        vectores: list[list[float]] = []
        for inicio in range(0, len(textos), TAMANO_LOTE_EMBEDDINGS):
            lote = textos[inicio : inicio + TAMANO_LOTE_EMBEDDINGS]
            # lote=lote fija el valor de esta vuelta: sin eso, la función
            # usaría el lote de la última vuelta del ciclo.
            respuesta = self._con_reintentos(
                lambda lote=lote: self._cliente.models.embed_content(
                    model=self._modelo_embeddings,
                    contents=lote,
                    config=configuracion,
                )
            )
            vectores.extend(list(e.values) for e in respuesta.embeddings)
        return vectores

    def _con_reintentos[T](self, operacion: Callable[[], T]) -> T:
        """Ejecuta la llamada y la repite si Gemini falla con un error pasajero."""
        ultimo_error: Exception | None = None
        for intento in range(len(ESPERAS_ENTRE_INTENTOS) + 1):
            if intento > 0:
                self._dormir(ESPERAS_ENTRE_INTENTOS[intento - 1])
            try:
                return operacion()
            except errors.APIError as error:
                if error.code not in CODIGOS_REINTENTABLES:
                    raise ProveedorIANoDisponible(
                        f"Gemini rechazó la petición (código {error.code})."
                    ) from error
                ultimo_error = error
            except httpx.TimeoutException as error:
                ultimo_error = error

        raise ProveedorIANoDisponible(
            "Gemini no respondió después de "
            f"{len(ESPERAS_ENTRE_INTENTOS) + 1} intentos."
        ) from ultimo_error
