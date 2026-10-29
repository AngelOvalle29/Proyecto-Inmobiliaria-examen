"""Selectores de CRM: consultas, filtros y agregaciones.

Nunca escriben en la base de datos.
"""

from django.db.models import Count, Q, QuerySet

from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Usuario

from .enums import TipoCliente
from .models import Agente, Cliente

# ---------- Agentes ----------


def listar_agentes() -> QuerySet[Agente]:
    """
    Agentes activos, con su usuario y la cantidad de clientes activos.

    clientes_activos se calcula en la misma consulta (annotate): el detalle
    del agente lo muestra, y la regla 4 se explica sola al ver el número.
    El orden termina en id para que la paginación sea estable.
    """
    return (
        Agente.objects.filter(activo=True)
        .select_related("usuario__pais")
        .annotate(clientes_activos=Count("clientes", filter=Q(clientes__activo=True)))
        .order_by("codigo", "id")
    )


def obtener_agente(*, agente_id: int) -> Agente | None:
    """Un agente activo con sus datos de listado, o None si no existe."""
    return listar_agentes().filter(pk=agente_id).first()


def obtener_agente_de_usuario(*, usuario: Usuario) -> Agente | None:
    """
    Perfil de agente del usuario, o None si no lo tiene.

    Devuelve el perfil aunque esté desactivado: quien decide qué hacer con un
    agente inactivo es el servicio (regla 5), no la consulta.
    """
    return Agente.objects.filter(usuario=usuario).first()


def contar_clientes_activos(*, agente: Agente) -> int:
    """Clientes activos asignados al agente (regla 4)."""
    return Cliente.objects.filter(agente_asignado=agente, activo=True).count()


# ---------- Clientes ----------


def listar_clientes_visibles(*, usuario: Usuario) -> QuerySet[Cliente]:
    """
    Clientes activos que el usuario puede ver (reglas 11 a 14).

    - ADMINISTRADOR, GERENTE, CONTABILIDAD y CONSULTA: todos.
    - AGENTE: solo su cartera. Sin perfil de agente, ninguno (regla 12).

    Es la única regla de cartera del sistema: la vista de detalle busca dentro
    de esta misma consulta, así que un cliente ajeno simplemente no se
    encuentra y la API responde 404 (regla 14). El agente de IA en modo
    interno debe usar este mismo selector.
    """
    clientes = (
        Cliente.objects.filter(activo=True)
        .select_related("pais", "ciudad", "agente_asignado__usuario")
        .order_by("codigo", "id")
    )
    if usuario.rol.nombre != NombreRol.AGENTE:
        return clientes

    agente = obtener_agente_de_usuario(usuario=usuario)
    if agente is None:
        return clientes.none()
    return clientes.filter(agente_asignado=agente)


def existe_cliente_con_documento(
    *,
    pais_id: int,
    tipo: str,
    documento: str,
    excluir_id: int | None = None,
) -> bool:
    """
    True si ya hay otro cliente del mismo tipo con ese documento en el país
    (regla 7), activo o no. Para una persona compara el documento de
    identidad; para una empresa, el NIT. El documento llega ya normalizado.

    excluir_id deja fuera al propio cliente al editarlo.
    """
    campo = "nit" if tipo == TipoCliente.EMPRESA else "documento_identidad"
    clientes = Cliente.objects.filter(pais_id=pais_id, tipo=tipo, **{campo: documento})
    if excluir_id is not None:
        clientes = clientes.exclude(pk=excluir_id)
    return clientes.exists()


def consultar_agentes_asignables() -> QuerySet[Agente]:
    """
    Todos los agentes, activos o no, para validar el id que llega en la API al
    asignar o reasignar un cliente.

    Incluye a los desactivados a propósito: así el servicio responde
    AGENTE_INACTIVO (regla 5), que explica el problema, en lugar de un "no
    existe" que confundiría.
    """
    return Agente.objects.select_related("usuario")
