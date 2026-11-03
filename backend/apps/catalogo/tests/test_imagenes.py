"""Pruebas de las imágenes de las propiedades: reglas y auditoría (spec 019)."""

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.exceptions import ArchivoNoPermitido, LimiteImagenes
from apps.catalogo.models import TAMANO_MAXIMO_IMAGEN, ImagenPropiedad
from apps.catalogo.selectors import listar_imagenes
from apps.catalogo.services import (
    MAXIMO_IMAGENES,
    actualizar_imagen,
    desactivar_imagen,
    marcar_portada,
    subir_imagen,
)

from .factories import ImagenPropiedadFactory, PropiedadFactory

pytestmark = pytest.mark.django_db

JPG = b"\xff\xd8\xff\xe0 foto de prueba"
PNG = b"\x89PNG\r\n\x1a\n plano de prueba"


def foto(nombre: str = "fachada.jpg", contenido: bytes = JPG) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


def subir(propiedad, archivo=None, descripcion: str = "") -> ImagenPropiedad:
    return subir_imagen(
        propiedad=propiedad,
        archivo=archivo or foto(),
        descripcion=descripcion,
        autor=None,
        ip="127.0.0.1",
    )


def test_la_primera_imagen_es_portada_y_las_siguientes_van_al_final():
    propiedad = PropiedadFactory()

    primera = subir(propiedad, descripcion="Fachada")
    segunda = subir(propiedad, foto("plano.png", PNG))

    assert primera.es_portada is True
    assert segunda.es_portada is False
    assert (primera.orden, segunda.orden) == (1, 2)
    assert segunda.tipo_contenido == "image/png"
    assert primera.archivo.name.startswith(f"imagenes/{propiedad.codigo}/")
    assert segunda.archivo.name.endswith(".png")
    assert default_storage.exists(primera.archivo.name)


def test_subir_audita_la_ruta_y_no_el_contenido():
    imagen = subir(PropiedadFactory(), descripcion="Fachada")

    registro = LogAuditoria.objects.get(accion=AccionAuditoria.CREAR)
    assert registro.entidad == "catalogo_imagenpropiedad"
    assert registro.valores_nuevos["archivo"] == imagen.archivo.name
    assert registro.valores_nuevos["es_portada"] is True
    assert registro.valores_nuevos["descripcion"] == "Fachada"


@pytest.mark.parametrize(
    "contenido",
    [b"%PDF-1.4 documento", b"MZ\x90\x00 ejecutable"],
    ids=["pdf", "ejecutable"],
)
def test_rechaza_lo_que_no_es_jpg_ni_png(contenido):
    with pytest.raises(ArchivoNoPermitido) as error:
        subir(PropiedadFactory(), foto("foto.jpg", contenido))

    assert "JPG o PNG" in error.value.mensaje
    assert not ImagenPropiedad.objects.exists()


def test_rechaza_una_imagen_de_mas_de_cinco_megas():
    pesada = foto(contenido=JPG + b"0" * TAMANO_MAXIMO_IMAGEN)

    with pytest.raises(ArchivoNoPermitido) as error:
        subir(PropiedadFactory(), pesada)

    assert "5 MB" in error.value.mensaje


def test_la_undecima_imagen_lanza_limite_y_desactivar_libera_lugar():
    propiedad = PropiedadFactory()
    imagenes = [subir(propiedad) for _ in range(MAXIMO_IMAGENES)]

    with pytest.raises(LimiteImagenes):
        subir(propiedad)

    desactivar_imagen(imagen=imagenes[3], autor=None, ip=None)
    subir(propiedad)
    assert listar_imagenes(propiedad=propiedad).count() == MAXIMO_IMAGENES


def test_marcar_portada_deja_una_sola_y_audita_las_dos():
    propiedad = PropiedadFactory()
    primera = subir(propiedad)
    segunda = subir(propiedad)
    LogAuditoria.objects.all().delete()

    marcar_portada(imagen=segunda, autor=None, ip=None)

    primera.refresh_from_db()
    segunda.refresh_from_db()
    assert (primera.es_portada, segunda.es_portada) == (False, True)
    cambios = {
        registro.entidad_id: registro.valores_nuevos
        for registro in LogAuditoria.objects.filter(accion=AccionAuditoria.ACTUALIZAR)
    }
    assert cambios == {
        primera.pk: {"es_portada": False},
        segunda.pk: {"es_portada": True},
    }


def test_marcar_la_portada_actual_no_cambia_nada():
    imagen = subir(PropiedadFactory())
    LogAuditoria.objects.all().delete()

    marcar_portada(imagen=imagen, autor=None, ip=None)

    assert not LogAuditoria.objects.exists()


def test_desactivar_la_portada_pasa_la_marca_a_la_siguiente_por_orden():
    propiedad = PropiedadFactory()
    portada = subir(propiedad)
    segunda = subir(propiedad)
    tercera = subir(propiedad)
    # La tercera pasa adelante de la segunda en la galería.
    actualizar_imagen(imagen=tercera, datos={"orden": 1}, autor=None, ip=None)

    desactivar_imagen(imagen=portada, autor=None, ip=None)

    tercera.refresh_from_db()
    segunda.refresh_from_db()
    assert tercera.es_portada is True
    assert segunda.es_portada is False
    assert default_storage.exists(portada.archivo.name)


def test_desactivar_la_ultima_deja_la_propiedad_sin_portada():
    propiedad = PropiedadFactory()
    imagen = subir(propiedad)

    desactivar_imagen(imagen=imagen, autor=None, ip=None)

    assert not listar_imagenes(propiedad=propiedad).exists()


def test_actualizar_solo_cambia_descripcion_y_orden():
    imagen = subir(PropiedadFactory())

    actualizar_imagen(
        imagen=imagen,
        datos={"descripcion": "Vista lateral", "orden": 4, "es_portada": False},
        autor=None,
        ip=None,
    )

    imagen.refresh_from_db()
    assert (imagen.descripcion, imagen.orden, imagen.es_portada) == (
        "Vista lateral",
        4,
        True,
    )


def test_el_constraint_rechaza_dos_portadas_activas():
    portada = ImagenPropiedadFactory(es_portada=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        ImagenPropiedadFactory(propiedad=portada.propiedad, es_portada=True)

    # Una portada desactivada no cuenta.
    portada.activo = False
    portada.save()
    ImagenPropiedadFactory(propiedad=portada.propiedad, es_portada=True)
