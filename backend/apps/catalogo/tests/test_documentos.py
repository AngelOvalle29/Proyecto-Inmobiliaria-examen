"""Pruebas de documentos oficiales: archivos, reglas y auditoría (spec 011)."""

from datetime import date

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import TipoDocumento
from apps.catalogo.exceptions import ArchivoNoPermitido, DocumentoEnUso
from apps.catalogo.models import TAMANO_MAXIMO_DOCUMENTO, DocumentoOficial
from apps.catalogo.services import (
    actualizar_documento,
    desactivar_avaluo,
    desactivar_documento,
    generar_url_descarga,
    subir_documento,
)

from .factories import AvaluoFactory, DocumentoOficialFactory, PropiedadFactory

pytestmark = pytest.mark.django_db


def archivo_pdf(
    nombre: str = "escritura.pdf", contenido: bytes = b"%PDF-1.4 demo"
) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


def datos_documento(**cambios) -> dict:
    datos = {
        "tipo": TipoDocumento.ESCRITURA,
        "nombre": "Escritura de la propiedad",
        "fecha_emision": date(2025, 1, 10),
        "emisor": "Registro ficticio",
    }
    datos.update(cambios)
    return datos


def test_subir_guarda_el_archivo_con_nombre_generado_y_audita():
    propiedad = PropiedadFactory()

    documento = subir_documento(
        propiedad=propiedad,
        archivo=archivo_pdf(),
        datos=datos_documento(),
        autor=None,
        ip="127.0.0.1",
    )

    assert documento.tipo_contenido == "application/pdf"
    assert documento.nombre_original == "escritura.pdf"
    assert documento.tamano_bytes == len(b"%PDF-1.4 demo")
    assert documento.archivo.name.startswith(f"documentos/{propiedad.codigo}/")
    assert documento.archivo.name.endswith(".pdf")
    assert default_storage.exists(documento.archivo.name)

    registro = LogAuditoria.objects.get(accion=AccionAuditoria.CREAR)
    assert registro.entidad == "catalogo_documentooficial"
    assert registro.valores_nuevos["archivo"] == documento.archivo.name
    assert registro.valores_nuevos["nombre_original"] == "escritura.pdf"
    assert "contenido" not in registro.valores_nuevos


def test_dos_archivos_con_el_mismo_nombre_no_se_pisan():
    propiedad = PropiedadFactory()

    primero = subir_documento(
        propiedad=propiedad,
        archivo=archivo_pdf(),
        datos=datos_documento(),
        autor=None,
        ip=None,
    )
    segundo = subir_documento(
        propiedad=propiedad,
        archivo=archivo_pdf(),
        datos=datos_documento(),
        autor=None,
        ip=None,
    )

    assert primero.archivo.name != segundo.archivo.name
    assert primero.nombre_original == segundo.nombre_original == "escritura.pdf"


@pytest.mark.parametrize(
    ("contenido", "tipo_contenido", "extension"),
    [
        (b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg", ".jpg"),
        (b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png", ".png"),
    ],
)
def test_reconoce_el_tipo_por_el_contenido_y_no_por_la_extension(
    contenido, tipo_contenido, extension
):
    """Regla 6: un JPG o PNG con otro nombre se acepta y se guarda bien."""
    documento = subir_documento(
        propiedad=PropiedadFactory(),
        archivo=SimpleUploadedFile("foto.txt", contenido),
        datos=datos_documento(),
        autor=None,
        ip=None,
    )

    assert documento.tipo_contenido == tipo_contenido
    assert documento.archivo.name.endswith(extension)


def test_rechaza_un_ejecutable_renombrado_a_pdf():
    with pytest.raises(ArchivoNoPermitido):
        subir_documento(
            propiedad=PropiedadFactory(),
            archivo=archivo_pdf(contenido=b"MZ\x90\x00"),
            datos=datos_documento(),
            autor=None,
            ip=None,
        )

    assert not DocumentoOficial.objects.exists()
    assert not LogAuditoria.objects.exists()


def test_rechaza_un_archivo_de_mas_de_diez_megas():
    grande = SimpleUploadedFile("grande.pdf", b"x" * (TAMANO_MAXIMO_DOCUMENTO + 1))

    with pytest.raises(ArchivoNoPermitido):
        subir_documento(
            propiedad=PropiedadFactory(),
            archivo=grande,
            datos=datos_documento(),
            autor=None,
            ip=None,
        )

    assert not DocumentoOficial.objects.exists()


def test_si_falla_el_registro_se_borra_el_archivo_subido(monkeypatch):
    rutas: list[str] = []

    def fallar(*args, **kwargs):
        rutas.append(kwargs["datos"]["archivo"])
        raise RuntimeError("fallo simulado de la base")

    monkeypatch.setattr("apps.catalogo.services._crear", fallar)

    with pytest.raises(RuntimeError):
        subir_documento(
            propiedad=PropiedadFactory(),
            archivo=archivo_pdf(),
            datos=datos_documento(),
            autor=None,
            ip=None,
        )

    assert len(rutas) == 1
    assert not default_storage.exists(rutas[0])


def test_actualizar_solo_cambia_los_campos_editables_y_audita():
    documento = DocumentoOficialFactory()

    actualizado = actualizar_documento(
        documento=documento,
        datos={
            "nombre": "Escritura corregida",
            "fecha_vencimiento": date(2030, 1, 10),
            "tipo": TipoDocumento.PLANO,
            "archivo": "otro/archivo.pdf",
        },
        autor=None,
        ip="127.0.0.1",
    )

    assert actualizado.nombre == "Escritura corregida"
    assert actualizado.tipo == TipoDocumento.ESCRITURA
    assert actualizado.archivo.name == documento.archivo.name
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ACTUALIZAR)
    assert set(registro.valores_anteriores) == {"nombre", "fecha_vencimiento"}
    assert registro.valores_nuevos["nombre"] == "Escritura corregida"


def test_no_se_desactiva_un_documento_que_respalda_un_avaluo_activo():
    documento = DocumentoOficialFactory()
    AvaluoFactory(propiedad=documento.propiedad, documento=documento)

    with pytest.raises(DocumentoEnUso):
        desactivar_documento(documento=documento, autor=None, ip=None)

    documento.refresh_from_db()
    assert documento.activo is True
    assert not LogAuditoria.objects.exists()


def test_se_desactiva_cuando_el_avaluo_ya_no_esta_activo_y_no_borra_el_archivo():
    documento = subir_documento(
        propiedad=PropiedadFactory(),
        archivo=archivo_pdf(),
        datos=datos_documento(),
        autor=None,
        ip=None,
    )
    avaluo = AvaluoFactory(propiedad=documento.propiedad, documento=documento)
    desactivar_avaluo(avaluo=avaluo, autor=None, ip=None)
    ruta = documento.archivo.name

    desactivar_documento(documento=documento, autor=None, ip=None)

    documento.refresh_from_db()
    assert documento.activo is False
    assert default_storage.exists(ruta)
    registro = LogAuditoria.objects.get(
        accion=AccionAuditoria.ELIMINAR, entidad="catalogo_documentooficial"
    )
    assert registro.valores_nuevos == {"activo": False}


def test_generar_url_descarga_apunta_al_archivo():
    documento = DocumentoOficialFactory()

    url = generar_url_descarga(documento=documento)

    assert documento.archivo.name in url
