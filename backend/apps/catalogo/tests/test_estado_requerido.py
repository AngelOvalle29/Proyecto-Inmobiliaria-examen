"""
Pruebas de estado_requerido en cambiar_estado_propiedad y cambiar_estado_unidad.

Lo agregó la spec 007 (cotizaciones y ventas): comprobar el estado actual y
cambiarlo bajo el mismo bloqueo de fila, para que dos operaciones simultáneas
sobre la misma propiedad no pasen las dos.
"""

import pytest

from apps.auditoria.models import LogAuditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.services import cambiar_estado_propiedad, cambiar_estado_unidad
from apps.catalogo.tests.factories import PropiedadFactory, UnidadFactory

pytestmark = pytest.mark.django_db


def test_con_el_estado_requerido_cambia_y_audita():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.DISPONIBLE)

    cambiar_estado_propiedad(
        propiedad=propiedad,
        estado=EstadoPropiedad.RESERVADA,
        autor=None,
        ip=None,
        motivo="prueba",
        estado_requerido=EstadoPropiedad.DISPONIBLE,
    )

    propiedad.refresh_from_db()
    assert propiedad.estado == EstadoPropiedad.RESERVADA
    assert LogAuditoria.objects.count() == 1


def test_sin_el_estado_requerido_rechaza_y_no_cambia_nada():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.RESERVADA)

    with pytest.raises(PropiedadNoDisponible) as error:
        cambiar_estado_propiedad(
            propiedad=propiedad,
            estado=EstadoPropiedad.RESERVADA,
            autor=None,
            ip=None,
            motivo="prueba",
            estado_requerido=EstadoPropiedad.DISPONIBLE,
        )

    assert error.value.detalles["estado_actual"] == EstadoPropiedad.RESERVADA
    assert not LogAuditoria.objects.exists()


def test_la_unidad_tambien_respeta_el_estado_requerido():
    unidad = UnidadFactory(estado=EstadoPropiedad.VENDIDA)

    with pytest.raises(PropiedadNoDisponible):
        cambiar_estado_unidad(
            unidad=unidad,
            estado=EstadoPropiedad.RESERVADA,
            autor=None,
            ip=None,
            motivo="prueba",
            estado_requerido=EstadoPropiedad.DISPONIBLE,
        )
