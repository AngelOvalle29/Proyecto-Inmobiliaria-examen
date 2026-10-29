"""Excepciones de dominio de CRM (spec 004, §5).

El manejador global de errores las traduce al formato uniforme.
"""

from apps.core.exceptions import ErrorDominio


class ClienteDuplicado(ErrorDominio):
    """Regla 7: ya existe ese documento (persona) o NIT (empresa) en el país."""

    codigo = "CLIENTE_DUPLICADO"
    estado_http = 409

    def __init__(self, *, campo: str, valor: str) -> None:
        super().__init__(
            "Ya existe un cliente con ese documento en el mismo país.",
            detalles={"campo": campo, "valor": valor},
        )


class CiudadFueraDelPais(ErrorDominio):
    """Regla 9: la ciudad indicada pertenece a otro país."""

    codigo = "CIUDAD_FUERA_DEL_PAIS"
    estado_http = 400

    def __init__(self, *, ciudad: str, pais: str) -> None:
        super().__init__(
            f"La ciudad {ciudad} no pertenece a {pais}.",
            detalles={"ciudad": ciudad, "pais": pais},
        )


class AgenteInactivo(ErrorDominio):
    """Regla 5: a un agente desactivado no se le asignan clientes."""

    codigo = "AGENTE_INACTIVO"
    estado_http = 409

    def __init__(self, *, agente: str) -> None:
        super().__init__(
            f"El agente {agente} está desactivado y no puede recibir clientes.",
            detalles={"agente": agente},
        )


class AgenteConClientes(ErrorDominio):
    """Regla 4: primero se reasigna la cartera, después se desactiva."""

    codigo = "AGENTE_CON_CLIENTES"
    estado_http = 409

    def __init__(self, *, agente: str, clientes_activos: int) -> None:
        super().__init__(
            f"El agente {agente} tiene {clientes_activos} clientes activos: "
            "reasígnelos antes de desactivarlo.",
            detalles={"agente": agente, "clientes_activos": clientes_activos},
        )


class UsuarioNoEsAgente(ErrorDominio):
    """Regla 1: solo un usuario con rol AGENTE tiene perfil de agente."""

    codigo = "USUARIO_NO_ES_AGENTE"
    estado_http = 400

    def __init__(self, *, email: str, rol: str) -> None:
        super().__init__(
            f"El usuario {email} tiene el rol {rol}, no AGENTE.",
            detalles={"usuario": email, "rol": rol},
        )


class UsuarioYaEsAgente(ErrorDominio):
    """Regla 1: un usuario tiene como máximo un perfil de agente."""

    codigo = "USUARIO_YA_ES_AGENTE"
    estado_http = 409

    def __init__(self, *, email: str) -> None:
        super().__init__(
            f"El usuario {email} ya tiene perfil de agente.",
            detalles={"usuario": email},
        )


class SinPerfilDeAgente(ErrorDominio):
    """Regla 12: un usuario AGENTE sin perfil todavía no puede crear clientes."""

    codigo = "SIN_PERFIL_DE_AGENTE"
    estado_http = 403

    def __init__(self) -> None:
        super().__init__(
            "Su usuario tiene el rol AGENTE pero todavía no tiene perfil de "
            "agente. Pida a un gerente que lo cree."
        )
