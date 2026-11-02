"""Pruebas de avalúos: reglas, auditoría y selectores (spec 011)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.models import LogAuditoria
from apps.catalogo.exceptions import DocumentoDeOtraPropiedad, FechaAvaluoFutura
from apps.catalogo.models import Avaluo
from apps.catalogo.selectors import listar_avaluos
from apps.catalogo.services import desactivar_avaluo, registrar_avaluo
from apps.core.tests.factories import MonedaFactory

from .factories import AvaluoFactory, DocumentoOficialFactory, PropiedadFactory

pytestmark = pytest.mark.django_db


def datos_de_avaluo(**cambios) -> dict:
    datos = {
        "fecha": date(2025, 5, 1),
        "valor": Decimal("250000.00"),
        "moneda": MonedaFactory(codigo="USD"),
        "perito": "Perito de prueba",
        "metodologia": "Comparativo de mercado",
        "observaciones": "Avalúo de prueba.",
    }
    datos.update(cambios)
    return datos


def test_registrar_avaluo_guarda_y_audita_todos_los_campos():
    propiedad = PropiedadFactory()

    avaluo = registrar_avaluo(
        propiedad=propiedad, datos=datos_de_avaluo(), autor=None, ip="127.0.0.1"
    )

    assert avaluo.propiedad == propiedad
    registro = LogAuditoria.objects.get()
    assert registro.accion == AccionAuditoria.CREAR
    assert registro.entidad == "catalogo_avaluo"
    assert registro.entidad_id == avaluo.pk
    assert registro.valores_nuevos["propiedad"] == propiedad.pk
    assert registro.valores_nuevos["fecha"] == "2025-05-01"
    assert registro.valores_nuevos["valor"] == "250000.00"
    assert registro.valores_nuevos["perito"] == "Perito de prueba"
    assert registro.valores_nuevos["documento"] is None


def test_una_fecha_futura_se_rechaza_sin_escribir_ni_auditar():
    """Regla 2: la fecha no puede ser futura."""
    futura = timezone.localdate() + timedelta(days=1)

    with pytest.raises(FechaAvaluoFutura) as error:
        registrar_avaluo(
            propiedad=PropiedadFactory(),
            datos=datos_de_avaluo(fecha=futura),
            autor=None,
            ip=None,
        )

    assert error.value.codigo == "VALIDACION"
    assert not Avaluo.objects.exists()
    assert not LogAuditoria.objects.exists()


def test_un_documento_de_otra_propiedad_se_rechaza():
    """Regla 4: el documento debe ser de la misma propiedad."""
    propiedad = PropiedadFactory()
    documento = DocumentoOficialFactory(propiedad=PropiedadFactory())

    with pytest.raises(DocumentoDeOtraPropiedad) as error:
        registrar_avaluo(
            propiedad=propiedad,
            datos=datos_de_avaluo(documento=documento),
            autor=None,
            ip=None,
        )

    assert error.value.detalles["propiedad_documento"] == documento.propiedad.codigo
    assert not Avaluo.objects.exists()
    assert not LogAuditoria.objects.exists()


def test_un_documento_de_la_misma_propiedad_se_acepta():
    propiedad = PropiedadFactory()
    documento = DocumentoOficialFactory(propiedad=propiedad)

    avaluo = registrar_avaluo(
        propiedad=propiedad,
        datos=datos_de_avaluo(documento=documento),
        autor=None,
        ip=None,
    )

    assert avaluo.documento == documento
    assert LogAuditoria.objects.filter(accion=AccionAuditoria.CREAR).count() == 1


def test_desactivar_avaluo_es_logico_y_auditado():
    """Regla 3: no se edita; si hay un error se desactiva."""
    avaluo = AvaluoFactory()

    desactivar_avaluo(avaluo=avaluo, autor=None, ip="127.0.0.1")

    avaluo.refresh_from_db()
    assert avaluo.activo is False
    registro = LogAuditoria.objects.get(accion=AccionAuditoria.ELIMINAR)
    assert registro.valores_anteriores == {"activo": True}
    assert registro.valores_nuevos == {"activo": False}


def test_listar_avaluos_va_del_mas_reciente_al_mas_antiguo_y_omite_desactivados():
    propiedad = PropiedadFactory()
    viejo = AvaluoFactory(propiedad=propiedad, fecha=date(2025, 1, 10))
    nuevo = AvaluoFactory(propiedad=propiedad, fecha=date(2026, 1, 10))
    AvaluoFactory(propiedad=PropiedadFactory(), fecha=date(2026, 6, 1))

    assert list(listar_avaluos(propiedad=propiedad)) == [nuevo, viejo]

    desactivar_avaluo(avaluo=nuevo, autor=None, ip=None)
    assert list(listar_avaluos(propiedad=propiedad)) == [viejo]
