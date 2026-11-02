"""Pruebas de los endpoints de proyectos de construcción (spec 017, §9, nivel API).

Las reglas ya están probadas en los servicios (test_proyectos.py). Aquí se
prueba lo que solo existe en la capa HTTP: la matriz de permisos, un caso feliz
por acción, la validación de entrada y el formato de los errores.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.tests.factories import PropiedadFactory
from apps.construccion.enums import EstadoProyecto
from apps.core.tests.factories import MonedaFactory
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory

from .factories import ConstructoraFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/proyectos-construccion/"
HOY = timezone.localdate()
ESCRIBEN = [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]
NO_ESCRIBEN = [NombreRol.AGENTE, NombreRol.CONTABILIDAD, NombreRol.CONSULTA]


def cliente_http(rol=NombreRol.GERENTE):
    http = APIClient()
    http.force_authenticate(UsuarioFactory(rol=Rol.objects.get(nombre=rol)))
    return http


def datos(**cambios):
    base = {
        "nombre": "Remodelación demo",
        "propiedad": PropiedadFactory(estado=EstadoPropiedad.ADQUIRIDA).pk,
        "constructora": ConstructoraFactory().pk,
        "fecha_inicio": HOY.isoformat(),
        "fecha_fin_estimada": (HOY + timedelta(days=180)).isoformat(),
        "presupuesto_total": "500000.00",
        "moneda": MonedaFactory(codigo="USD").pk,
    }
    base.update(cambios)
    return base


def registrar(http=None, **cambios):
    return (http or cliente_http()).post(URL, datos(**cambios), format="json")


def accion(http, proyecto, nombre, cuerpo=None):
    return http.post(f"{URL}{proyecto['id']}/{nombre}/", cuerpo or {}, format="json")


def test_sin_token_responde_401():
    assert APIClient().get(URL).status_code == 401


@pytest.mark.parametrize("rol", ESCRIBEN)
def test_administracion_y_gerencia_registran(rol):
    respuesta = registrar(cliente_http(rol))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["codigo"].startswith("PC-")
    assert cuerpo["estado"] == EstadoProyecto.PLANIFICADO
    assert cuerpo["porcentaje_avance"] == 0
    assert cuerpo["constructora"]["codigo"]


@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_leen_pero_no_registran(rol):
    http = cliente_http(rol)
    assert http.get(URL).status_code == 200
    assert registrar(http).status_code == 403


def test_una_constructora_desactivada_responde_400():
    """Regla 9: solo se contrata a una constructora activa."""
    constructora = ConstructoraFactory(activo=False)
    assert registrar(constructora=constructora.pk).status_code == 400


def test_una_propiedad_que_no_esta_adquirida_responde_409():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.EN_NEGOCIACION)

    respuesta = registrar(propiedad=propiedad.pk)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROPIEDAD_NO_DISPONIBLE"


def test_un_segundo_proyecto_activo_responde_409():
    propiedad = PropiedadFactory(estado=EstadoPropiedad.ADQUIRIDA)
    registrar(propiedad=propiedad.pk)

    respuesta = registrar(propiedad=propiedad.pk)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "PROPIEDAD_CON_PROYECTO"


def test_fin_estimado_antes_del_inicio_responde_400_junto_al_campo():
    respuesta = registrar(fecha_fin_estimada=(HOY - timedelta(days=1)).isoformat())

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "FECHA_INVALIDA"
    assert "fecha_fin_estimada" in respuesta.json()["error"]["detalles"]


def test_el_ciclo_completo_por_la_api():
    """Iniciar, avanzar, suspender, reanudar y finalizar (reglas 12 a 15)."""
    http = cliente_http()
    proyecto = registrar(http).json()

    assert accion(http, proyecto, "iniciar").json()["estado"] == "EN_EJECUCION"
    avance = accion(http, proyecto, "avance", {"porcentaje": 100, "descripcion": "Fin"})
    assert avance.json()["porcentaje_avance"] == 100
    assert (
        accion(http, proyecto, "suspender", {"motivo": "Lluvias"}).json()["estado"]
        == "SUSPENDIDO"
    )
    assert accion(http, proyecto, "reanudar").json()["estado"] == "EN_EJECUCION"
    finalizado = accion(http, proyecto, "finalizar").json()

    assert finalizado["estado"] == EstadoProyecto.FINALIZADO
    assert finalizado["fecha_fin_real"] == HOY.isoformat()


def test_cancelar_con_motivo_responde_el_proyecto_cancelado():
    http = cliente_http()
    proyecto = registrar(http).json()

    respuesta = accion(http, proyecto, "cancelar", {"motivo": "Sin fondos"})

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoProyecto.CANCELADO


@pytest.mark.parametrize("nombre", ["suspender", "cancelar"])
def test_las_acciones_con_motivo_sin_motivo_responden_400(nombre):
    http = cliente_http()
    proyecto = registrar(http).json()
    accion(http, proyecto, "iniciar")

    respuesta = accion(http, proyecto, nombre)

    assert respuesta.status_code == 400
    assert "motivo" in respuesta.json()["error"]["detalles"]


def test_un_avance_que_baja_responde_400():
    http = cliente_http()
    proyecto = registrar(http).json()
    accion(http, proyecto, "iniciar")
    accion(http, proyecto, "avance", {"porcentaje": 50, "descripcion": "a"})

    respuesta = accion(http, proyecto, "avance", {"porcentaje": 40, "descripcion": "b"})

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "AVANCE_INVALIDO"


def test_un_avance_mayor_que_100_responde_400_por_validacion():
    http = cliente_http()
    proyecto = registrar(http).json()
    accion(http, proyecto, "iniciar")

    respuesta = accion(
        http, proyecto, "avance", {"porcentaje": 101, "descripcion": "x"}
    )

    assert respuesta.status_code == 400
    assert "porcentaje" in respuesta.json()["error"]["detalles"]


def test_una_accion_en_un_estado_que_no_corresponde_responde_409():
    http = cliente_http()
    proyecto = registrar(http).json()

    respuesta = accion(http, proyecto, "reanudar")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TRANSICION_INVALIDA"


@pytest.mark.parametrize(
    "nombre", ["iniciar", "avance", "suspender", "reanudar", "finalizar", "cancelar"]
)
@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_no_ejecutan_acciones(rol, nombre):
    proyecto = registrar().json()

    respuesta = accion(
        cliente_http(rol), proyecto, nombre, {"motivo": "x", "porcentaje": 1}
    )

    assert respuesta.status_code == 403


def test_patch_edita_el_presupuesto():
    http = cliente_http()
    proyecto = registrar(http).json()

    respuesta = http.patch(
        f"{URL}{proyecto['id']}/", {"presupuesto_total": "650000.00"}, format="json"
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["presupuesto_total"] == "650000.00"


@pytest.mark.parametrize("rol", NO_ESCRIBEN)
def test_los_demas_roles_no_editan(rol):
    proyecto = registrar().json()
    respuesta = cliente_http(rol).patch(
        f"{URL}{proyecto['id']}/", {"nombre": "x"}, format="json"
    )
    assert respuesta.status_code == 403


def test_detalle_y_filtro_por_estado():
    http = cliente_http()
    planificado = registrar(http).json()
    en_ejecucion = registrar(http).json()
    accion(http, en_ejecucion, "iniciar")

    assert (
        http.get(f"{URL}{planificado['id']}/").json()["codigo"] == planificado["codigo"]
    )
    ids = [p["id"] for p in http.get(URL, {"estado": "EN_EJECUCION"}).json()["results"]]
    assert ids == [en_ejecucion["id"]]


def test_desactivar_una_constructora_con_un_proyecto_activo_responde_409():
    """Regla 23, por la API de constructoras de la spec 006."""
    http = cliente_http()
    proyecto = registrar(http).json()

    respuesta = http.delete(f"/api/v1/constructoras/{proyecto['constructora']['id']}/")

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "CONSTRUCTORA_CON_PROYECTOS"
