"""Pruebas del proveedor de IA (spec 005, incremento 1).

Ninguna llama a la red: el cliente de Gemini se reemplaza por uno falso y las
esperas entre reintentos se anotan en lugar de dormir.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.ia.proveedores import gemini
from apps.ia.proveedores.base import (
    Herramienta,
    Mensaje,
    ProveedorIANoDisponible,
    RolMensaje,
    TareaEmbedding,
)
from apps.ia.proveedores.fabrica import obtener_proveedor
from apps.ia.proveedores.gemini import ProveedorGemini

DIMENSION = 768


class ModelosFalsos:
    """Imita client.models: devuelve o lanza las respuestas en orden."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def _siguiente(self, kwargs):
        self.llamadas.append(kwargs)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta(kwargs) if callable(respuesta) else respuesta

    def generate_content(self, **kwargs):
        return self._siguiente(kwargs)

    def embed_content(self, **kwargs):
        return self._siguiente(kwargs)


def crear_proveedor(respuestas):
    modelos = ModelosFalsos(respuestas)
    esperas = []
    proveedor = ProveedorGemini(
        api_key="clave-de-prueba",
        modelo="modelo-de-prueba",
        modelo_embeddings="embeddings-de-prueba",
        dimension_embeddings=DIMENSION,
        max_tokens_respuesta=256,
        cliente=SimpleNamespace(models=modelos),
        dormir=esperas.append,
    )
    return proveedor, modelos, esperas


def respuesta_texto(texto="Hola"):
    return SimpleNamespace(
        text=texto,
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=3),
    )


def respuesta_embeddings(kwargs):
    """Un vector por cada texto recibido, como hace Gemini."""
    return SimpleNamespace(
        embeddings=[
            SimpleNamespace(values=[0.1] * DIMENSION) for _ in kwargs["contents"]
        ]
    )


def error_gemini(codigo):
    # Se usa el módulo del proveedor para no importar el SDK fuera de
    # proveedores/, ni siquiera en las pruebas.
    return gemini.errors.APIError(
        codigo, {"error": {"code": codigo, "message": "de prueba", "status": "X"}}
    )


# ---------- Fábrica ----------


def test_la_fabrica_entrega_el_proveedor_de_gemini(settings):
    settings.IA_PROVEEDOR = "gemini"
    settings.IA_API_KEY = "clave-de-prueba"
    assert isinstance(obtener_proveedor(), ProveedorGemini)


def test_sin_llave_el_proveedor_no_esta_disponible(settings):
    settings.IA_API_KEY = ""
    with pytest.raises(ProveedorIANoDisponible):
        obtener_proveedor()


def test_un_proveedor_desconocido_es_un_error_de_configuracion(settings):
    settings.IA_PROVEEDOR = "otro"
    settings.IA_API_KEY = "clave-de-prueba"
    with pytest.raises(ImproperlyConfigured):
        obtener_proveedor()


# ---------- Respuestas ----------


def test_generar_respuesta_separa_las_instrucciones_y_devuelve_los_tokens():
    proveedor, modelos, _ = crear_proveedor([respuesta_texto("Hola")])

    resultado = proveedor.generar_respuesta(
        mensajes=[
            Mensaje(RolMensaje.SISTEMA, "Responde en español."),
            Mensaje(RolMensaje.USUARIO, "Saluda"),
        ]
    )

    assert resultado.texto == "Hola"
    assert resultado.modelo == "modelo-de-prueba"
    assert (resultado.tokens_entrada, resultado.tokens_salida) == (12, 3)
    llamada = modelos.llamadas[0]
    assert llamada["model"] == "modelo-de-prueba"
    assert llamada["config"].system_instruction == "Responde en español."
    assert llamada["config"].max_output_tokens == 256
    assert [c.role for c in llamada["contents"]] == ["user"]


def test_las_herramientas_todavia_no_estan_disponibles():
    proveedor, modelos, _ = crear_proveedor([])
    with pytest.raises(NotImplementedError):
        proveedor.generar_respuesta(
            mensajes=[Mensaje(RolMensaje.USUARIO, "Hola")],
            herramientas=[Herramienta("buscar", "Busca propiedades")],
        )
    assert modelos.llamadas == []


# ---------- Embeddings ----------


def test_un_embedding_pide_la_dimension_y_la_tarea():
    proveedor, modelos, _ = crear_proveedor([respuesta_embeddings])

    vector = proveedor.generar_embedding(
        texto="casa en venta", tarea=TareaEmbedding.CONSULTA
    )

    assert len(vector) == DIMENSION
    configuracion = modelos.llamadas[0]["config"]
    assert configuracion.output_dimensionality == DIMENSION
    assert configuracion.task_type == "RETRIEVAL_QUERY"


def test_los_embeddings_se_piden_en_lotes_de_cien():
    proveedor, modelos, _ = crear_proveedor([respuesta_embeddings] * 3)

    vectores = proveedor.generar_embeddings_lote(
        textos=[f"texto {i}" for i in range(250)], tarea=TareaEmbedding.DOCUMENTO
    )

    assert len(vectores) == 250
    assert [len(llamada["contents"]) for llamada in modelos.llamadas] == [100, 100, 50]
    assert modelos.llamadas[0]["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_sin_textos_no_llama_a_gemini():
    proveedor, modelos, _ = crear_proveedor([])
    assert (
        proveedor.generar_embeddings_lote(textos=[], tarea=TareaEmbedding.DOCUMENTO)
        == []
    )
    assert modelos.llamadas == []


# ---------- Reintentos (regla 9) ----------


@pytest.mark.parametrize("codigo", [429, 500, 503, 504])
def test_un_error_pasajero_se_reintenta_con_espera_creciente(codigo):
    proveedor, modelos, esperas = crear_proveedor(
        [error_gemini(codigo), error_gemini(codigo), respuesta_texto("Ya")]
    )

    resultado = proveedor.generar_respuesta(
        mensajes=[Mensaje(RolMensaje.USUARIO, "Hola")]
    )

    assert resultado.texto == "Ya"
    assert len(modelos.llamadas) == 3
    assert esperas == [1, 2]


def test_un_tiempo_agotado_tambien_se_reintenta():
    proveedor, _, esperas = crear_proveedor(
        [httpx.ReadTimeout("sin respuesta"), respuesta_texto("Ya")]
    )
    resultado = proveedor.generar_respuesta(
        mensajes=[Mensaje(RolMensaje.USUARIO, "Hola")]
    )
    assert resultado.texto == "Ya"
    assert esperas == [1]


def test_despues_de_tres_fallos_el_proveedor_no_esta_disponible():
    proveedor, modelos, esperas = crear_proveedor([error_gemini(503)] * 3)

    with pytest.raises(ProveedorIANoDisponible):
        proveedor.generar_respuesta(mensajes=[Mensaje(RolMensaje.USUARIO, "Hola")])

    assert len(modelos.llamadas) == 3
    assert esperas == [1, 2]


def test_un_error_que_no_es_pasajero_no_se_reintenta():
    proveedor, modelos, esperas = crear_proveedor([error_gemini(400)])

    with pytest.raises(ProveedorIANoDisponible):
        proveedor.generar_respuesta(mensajes=[Mensaje(RolMensaje.USUARIO, "Hola")])

    assert len(modelos.llamadas) == 1
    assert esperas == []


# ---------- Regla de CLAUDE.md ----------


def test_el_sdk_de_gemini_solo_se_importa_en_proveedores():
    carpeta_apps = Path(__file__).resolve().parents[2]
    importa_google = re.compile(r"^\s*(from|import)\s+google\b", re.MULTILINE)

    infractores = [
        str(ruta.relative_to(carpeta_apps))
        for ruta in carpeta_apps.rglob("*.py")
        if "proveedores" not in ruta.parts
        and importa_google.search(ruta.read_text(encoding="utf-8"))
    ]

    assert infractores == []
