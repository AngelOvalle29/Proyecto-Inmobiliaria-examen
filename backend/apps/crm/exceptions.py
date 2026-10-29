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


# ---------- Cotizaciones (spec 007) ----------


class CotizacionNoEditable(ErrorDominio):
    """Regla 4: solo se edita una cotización en borrador."""

    codigo = "COTIZACION_NO_EDITABLE"
    estado_http = 409

    def __init__(self, *, cotizacion: str, estado: str) -> None:
        super().__init__(
            f"La cotización {cotizacion} está {estado}: solo se edita en borrador.",
            detalles={"cotizacion": cotizacion, "estado": estado},
        )


class TransicionInvalida(ErrorDominio):
    """Regla 4: la acción no se permite desde el estado actual."""

    codigo = "TRANSICION_INVALIDA"
    estado_http = 409

    def __init__(self, *, cotizacion: str, estado: str, accion: str) -> None:
        super().__init__(
            f"No se puede {accion} la cotización {cotizacion}: está {estado}.",
            detalles={"cotizacion": cotizacion, "estado": estado, "accion": accion},
        )


class CotizacionVencida(ErrorDominio):
    """Regla 4: una cotización vencida no se envía ni se aprueba."""

    codigo = "COTIZACION_VENCIDA"
    estado_http = 409

    def __init__(self, *, cotizacion: str, fecha_vencimiento) -> None:
        super().__init__(
            f"La cotización {cotizacion} venció el {fecha_vencimiento:%d/%m/%Y}.",
            detalles={
                "cotizacion": cotizacion,
                "fecha_vencimiento": fecha_vencimiento.isoformat(),
            },
        )


class CotizacionYaContratada(ErrorDominio):
    """Reglas 6 y 7: con contrato, no se rechaza ni da otro contrato."""

    codigo = "COTIZACION_YA_CONTRATADA"
    estado_http = 409

    def __init__(self, *, cotizacion: str) -> None:
        super().__init__(
            f"La cotización {cotizacion} ya tiene un contrato de venta.",
            detalles={"cotizacion": cotizacion},
        )


class SeVendePorUnidades(ErrorDominio):
    """
    Reglas 1 y 9: una propiedad de un tipo con unidades (un edificio) no se
    cotiza ni se vende completa, sino por unidades. Usa el código de la spec.
    """

    codigo = "PROPIEDAD_CON_UNIDADES"
    estado_http = 409

    def __init__(self, *, propiedad: str) -> None:
        super().__init__(
            f"{propiedad} se vende por unidades: cotice o venda una de ellas.",
            detalles={"propiedad": propiedad},
        )


class DescuentoFueraDeRango(ErrorDominio):
    """
    Regla 2: el descuento va de 0 al precio. Se responde como un error de
    validación del campo, igual que los del serializador.
    """

    codigo = "VALIDACION"
    estado_http = 400

    def __init__(self) -> None:
        super().__init__(
            "Los datos enviados no son válidos.",
            detalles={"descuento": ["Debe estar entre 0 y el precio."]},
        )
