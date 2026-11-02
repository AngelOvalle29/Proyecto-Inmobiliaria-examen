"""Troceo de un documento Markdown en fragmentos (spec 005, reglas 5 y 6).

Funciones puras: no tocan la base ni la red, así que se prueban sin nada más.
"""

import re
from dataclasses import dataclass

# Tamaño máximo de un fragmento, en caracteres (regla 6). Unos 375 tokens:
# cabe holgado junto a otros cuatro fragmentos en la instrucción al modelo.
LIMITE_CARACTERES = 1500

# Sección del texto que va antes del primer encabezado ## (regla 5).
SECCION_INICIAL = "Introducción"

_SEPARADOR_PARRAFOS = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Trozo:
    seccion: str
    contenido: str


def trocear_markdown(texto: str) -> list[Trozo]:
    """Divide el Markdown por sus encabezados ## y parte las secciones largas.

    El título # se omite porque ya es el título del documento. Los
    encabezados ### se quedan dentro de su sección ##.
    """
    return [
        Trozo(seccion=seccion, contenido=contenido)
        for seccion, cuerpo in _secciones(texto)
        for contenido in _dividir(cuerpo)
    ]


def estimar_tokens(texto: str) -> int:
    """Estimación simple: en español, un token son unos 4 caracteres."""
    return max(1, len(texto) // 4)


def _secciones(texto: str) -> list[tuple[str, str]]:
    secciones = []
    seccion = SECCION_INICIAL
    lineas: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith("## "):
            secciones.append((seccion, "\n".join(lineas).strip()))
            seccion = linea[3:].strip()
            lineas = []
        elif not linea.startswith("# "):
            lineas.append(linea)
    secciones.append((seccion, "\n".join(lineas).strip()))
    # Una sección sin texto (por ejemplo, sin introducción) no da fragmentos.
    return [(seccion, cuerpo) for seccion, cuerpo in secciones if cuerpo]


def _dividir(cuerpo: str) -> list[str]:
    """Junta párrafos hasta el límite; cada fragmento nuevo repite el último
    párrafo del anterior para no cortar una idea a la mitad (regla 6)."""
    if len(cuerpo) <= LIMITE_CARACTERES:
        return [cuerpo]

    parrafos = []
    for parrafo in _SEPARADOR_PARRAFOS.split(cuerpo):
        parrafo = parrafo.strip()
        if parrafo:
            parrafos.extend(_partir_parrafo_largo(parrafo))

    fragmentos = []
    actual: list[str] = []
    for parrafo in parrafos:
        if actual and _largo([*actual, parrafo]) > LIMITE_CARACTERES:
            fragmentos.append("\n\n".join(actual))
            ultimo = actual[-1]
            # El solapamiento solo se agrega si cabe junto al párrafo nuevo.
            actual = [ultimo] if _largo([ultimo, parrafo]) <= LIMITE_CARACTERES else []
        actual.append(parrafo)
    fragmentos.append("\n\n".join(actual))
    return fragmentos


def _partir_parrafo_largo(parrafo: str) -> list[str]:
    """Un solo párrafo más largo que el límite se corta por palabras."""
    partes = []
    while len(parrafo) > LIMITE_CARACTERES:
        corte = parrafo.rfind(" ", 0, LIMITE_CARACTERES)
        if corte <= 0:
            corte = LIMITE_CARACTERES
        partes.append(parrafo[:corte].strip())
        parrafo = parrafo[corte:].strip()
    partes.append(parrafo)
    return partes


def _largo(parrafos: list[str]) -> int:
    """Largo del texto que resulta de unir los párrafos con una línea en blanco."""
    return sum(len(p) for p in parrafos) + 2 * (len(parrafos) - 1)
