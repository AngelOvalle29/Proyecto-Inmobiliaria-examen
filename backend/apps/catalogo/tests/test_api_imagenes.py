"""Pruebas de los endpoints de imágenes de las propiedades (spec 019)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.services import MAXIMO_IMAGENES
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ImagenPropiedadFactory, PropiedadFactory

pytestmark = pytest.mark.django_db

PROPIEDADES = "/api/v1/propiedades/"
IMAGENES = "/api/v1/imagenes/"
JPG = b"\xff\xd8\xff\xe0 foto de prueba"


def cliente_con_rol(rol: str) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return cliente


@pytest.fixture
def gerente():
    return cliente_con_rol(NombreRol.GERENTE)


def subir(cliente: APIClient, propiedad, contenido: bytes = JPG, **datos):
    archivo = SimpleUploadedFile("fachada.jpg", contenido, content_type="image/jpeg")
    return cliente.post(
        f"{PROPIEDADES}{propiedad.pk}/imagenes/",
        {"archivo": archivo, **datos},
        format="multipart",
    )


def test_subir_responde_201_con_la_url_y_la_primera_es_portada(gerente):
    propiedad = PropiedadFactory()

    respuesta = subir(gerente, propiedad, descripcion="Fachada principal")

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["es_portada"] is True
    assert datos["orden"] == 1
    assert datos["descripcion"] == "Fachada principal"
    assert datos["url"].startswith("http://testserver/media/imagenes/")
    assert datos["vence_en_segundos"] == 300


def test_un_ejecutable_renombrado_a_jpg_responde_400(gerente):
    respuesta = subir(gerente, PropiedadFactory(), contenido=b"MZ\x90\x00 programa")

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "ARCHIVO_NO_PERMITIDO"


def test_la_undecima_imagen_responde_409(gerente):
    propiedad = PropiedadFactory()
    ImagenPropiedadFactory.create_batch(MAXIMO_IMAGENES, propiedad=propiedad)

    respuesta = subir(gerente, propiedad)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "LIMITE_IMAGENES"


def test_consulta_ve_la_galeria_pero_no_escribe():
    consulta = cliente_con_rol(NombreRol.CONSULTA)
    imagen = ImagenPropiedadFactory(es_portada=True)

    lista = consulta.get(f"{PROPIEDADES}{imagen.propiedad.pk}/imagenes/")
    assert lista.status_code == 200
    assert lista.json()["count"] == 1

    assert subir(consulta, imagen.propiedad).status_code == 403
    assert consulta.patch(f"{IMAGENES}{imagen.pk}/", {"orden": 3}).status_code == 403
    assert consulta.delete(f"{IMAGENES}{imagen.pk}/").status_code == 403
    marcar = consulta.post(f"{IMAGENES}{imagen.pk}/marcar-portada/")
    assert marcar.status_code == 403


def test_patch_cambia_orden_y_descripcion_pero_no_la_portada(gerente):
    imagen = ImagenPropiedadFactory(es_portada=False, orden=1)

    respuesta = gerente.patch(
        f"{IMAGENES}{imagen.pk}/",
        {"orden": 5, "descripcion": "Jardín", "es_portada": True},
        format="json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["orden"] == 5
    assert respuesta.json()["descripcion"] == "Jardín"
    assert respuesta.json()["es_portada"] is False
    assert LogAuditoria.objects.filter(accion=AccionAuditoria.ACTUALIZAR).exists()


def test_marcar_portada_y_desactivar_por_la_api(gerente):
    propiedad = PropiedadFactory()
    portada = ImagenPropiedadFactory(propiedad=propiedad, es_portada=True, orden=1)
    otra = ImagenPropiedadFactory(propiedad=propiedad, orden=2)

    respuesta = gerente.post(f"{IMAGENES}{otra.pk}/marcar-portada/")
    assert respuesta.status_code == 200
    assert respuesta.json()["es_portada"] is True

    assert gerente.delete(f"{IMAGENES}{otra.pk}/").status_code == 204
    portada.refresh_from_db()
    assert portada.es_portada is True
    assert gerente.get(f"{IMAGENES}{otra.pk}/").status_code == 404


def test_la_lista_de_propiedades_trae_portada_url(gerente):
    con_foto = PropiedadFactory()
    ImagenPropiedadFactory(propiedad=con_foto, es_portada=True)
    sin_foto = PropiedadFactory()

    filas = {fila["id"]: fila for fila in gerente.get(PROPIEDADES).json()["results"]}

    assert filas[con_foto.pk]["portada_url"].startswith("http://testserver/media/")
    assert filas[sin_foto.pk]["portada_url"] is None
    detalle = gerente.get(f"{PROPIEDADES}{con_foto.pk}/").json()
    assert detalle["portada_url"] == filas[con_foto.pk]["portada_url"]


def test_la_lista_de_propiedades_no_hace_una_consulta_por_fila(
    gerente, django_assert_max_num_queries
):
    """El número de consultas no crece con las filas (spec 019, §6)."""
    for _ in range(3):
        ImagenPropiedadFactory(es_portada=True)
    with django_assert_max_num_queries(20) as pocas:
        gerente.get(PROPIEDADES)

    for _ in range(10):
        ImagenPropiedadFactory(es_portada=True)
    with django_assert_max_num_queries(len(pocas.captured_queries)):
        gerente.get(PROPIEDADES)
