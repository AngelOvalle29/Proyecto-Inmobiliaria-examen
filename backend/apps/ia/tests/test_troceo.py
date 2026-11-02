"""Pruebas del troceo de documentos (spec 005, reglas 5 y 6). Sin base de datos."""

from apps.ia.troceo import (
    LIMITE_CARACTERES,
    SECCION_INICIAL,
    estimar_tokens,
    trocear_markdown,
)


def parrafo(letra: str, largo: int) -> str:
    return (letra * 9 + " ") * (largo // 10)


def test_tres_secciones_cortas_dan_tres_fragmentos_con_su_seccion():
    texto = "## Uno\nTexto uno.\n\n## Dos\nTexto dos.\n\n## Tres\nTexto tres."

    trozos = trocear_markdown(texto)

    assert [t.seccion for t in trozos] == ["Uno", "Dos", "Tres"]
    assert [t.contenido for t in trozos] == ["Texto uno.", "Texto dos.", "Texto tres."]


def test_el_texto_antes_del_primer_encabezado_es_la_introduccion():
    texto = "# Título del documento\nBienvenida.\n\n## Requisitos\nDPI vigente."

    trozos = trocear_markdown(texto)

    assert trozos[0].seccion == SECCION_INICIAL
    # El título # no se repite: ya es el título del documento.
    assert trozos[0].contenido == "Bienvenida."
    assert trozos[1].seccion == "Requisitos"


def test_una_seccion_sin_texto_no_da_fragmentos():
    trozos = trocear_markdown("# Título\n\n## Vacía\n\n## Llena\nAlgo.")
    assert [t.seccion for t in trozos] == ["Llena"]


def test_los_subtitulos_se_quedan_dentro_de_su_seccion():
    trozos = trocear_markdown("## Proceso\nPaso 1.\n### Detalle\nPaso 2.")
    assert len(trozos) == 1
    assert "### Detalle" in trozos[0].contenido


def test_una_seccion_larga_se_divide_con_solapamiento():
    parrafos = [parrafo(letra, 600) for letra in "abcde"]
    texto = "## Larga\n" + "\n\n".join(parrafos)

    trozos = trocear_markdown(texto)

    assert len(trozos) > 1
    assert all(t.seccion == "Larga" for t in trozos)
    assert all(len(t.contenido) <= LIMITE_CARACTERES for t in trozos)
    # Cada fragmento empieza con el último párrafo del anterior.
    for anterior, siguiente in zip(trozos, trozos[1:], strict=False):
        ultimo_parrafo = anterior.contenido.split("\n\n")[-1]
        assert siguiente.contenido.startswith(ultimo_parrafo)


def test_un_parrafo_gigante_se_corta_sin_pasar_el_limite():
    texto = "## Enorme\n" + parrafo("x", 4000)

    trozos = trocear_markdown(texto)

    assert len(trozos) >= 3
    assert all(len(t.contenido) <= LIMITE_CARACTERES for t in trozos)


def test_un_texto_vacio_no_da_fragmentos():
    assert trocear_markdown("") == []
    assert trocear_markdown("# Solo el título") == []


def test_estimar_tokens():
    assert estimar_tokens("a" * 400) == 100
    assert estimar_tokens("ab") == 1
