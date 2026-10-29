"""Servicios de CRM: escrituras con reglas de negocio, transacciones y
auditoría (spec 004, §6 y §7).

No conocen request ni hablan HTTP. Cada escritura registra su auditoría dentro
de la misma transacción: si algo falla, se revierten las dos.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.forms.models import model_to_dict

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.exceptions import CiudadFueraDelPais
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_ciudades, listar_paises
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Usuario
from apps.usuarios.services import asegurar_usuario_demo

from . import datos_demo
from .enums import TipoCliente
from .exceptions import (
    AgenteConClientes,
    AgenteInactivo,
    ClienteDuplicado,
    SinPerfilDeAgente,
    UsuarioNoEsAgente,
    UsuarioYaEsAgente,
)
from .models import Agente, Cliente
from .selectors import (
    contar_clientes_activos,
    existe_cliente_con_documento,
    obtener_agente_de_usuario,
)

# Campos que se guardan en la bitácora y que se pueden editar. codigo y
# agente_asignado no se editan con actualizar_*: el código no cambia nunca
# (regla 10) y el agente se cambia solo con reasignar_cliente (regla 11).
CAMPOS_AGENTE_EDITABLES = ["porcentaje_comision", "fecha_ingreso"]
CAMPOS_CLIENTE_EDITABLES = [
    "tipo",
    "nombre",
    "apellidos",
    "documento_identidad",
    "razon_social",
    "nit",
    "email",
    "telefono",
    "pais",
    "ciudad",
    "direccion",
    "notas",
]
CAMPOS_AGENTE_AUDITADOS = ["codigo", "usuario", *CAMPOS_AGENTE_EDITABLES]
CAMPOS_CLIENTE_AUDITADOS = ["codigo", "agente_asignado", *CAMPOS_CLIENTE_EDITABLES]


# ---------- Agentes ----------


@transaction.atomic
def crear_agente(
    *,
    usuario_agente: Usuario,
    porcentaje_comision: Decimal,
    fecha_ingreso: date,
    autor: Usuario,
    ip: str | None,
) -> Agente:
    """
    Crea el perfil comercial de un usuario con rol AGENTE (regla 1) y le
    asigna su código AGT-NNN (regla 10).
    """
    if usuario_agente.rol.nombre != NombreRol.AGENTE:
        raise UsuarioNoEsAgente(
            email=usuario_agente.email, rol=usuario_agente.rol.nombre
        )
    if obtener_agente_de_usuario(usuario=usuario_agente) is not None:
        raise UsuarioYaEsAgente(email=usuario_agente.email)

    agente = Agente.objects.create(
        usuario=usuario_agente,
        porcentaje_comision=porcentaje_comision,
        fecha_ingreso=fecha_ingreso,
        creado_por=autor,
        actualizado_por=autor,
    )
    # El código sale del id que acaba de asignar PostgreSQL: dos agentes
    # creados a la vez nunca reciben el mismo (spec 004, §4).
    agente.codigo = f"AGT-{agente.pk:03d}"
    agente.save(update_fields=["codigo"])

    # Después de asignar el código, para que la bitácora guarde el definitivo.
    registrar_auditoria(
        usuario=autor,
        entidad=Agente._meta.db_table,
        entidad_id=agente.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=_foto(agente, CAMPOS_AGENTE_AUDITADOS),
        ip=ip,
    )
    return agente


@transaction.atomic
def actualizar_agente(
    *, agente: Agente, datos: dict, autor: Usuario, ip: str | None
) -> Agente:
    """
    Cambia la comisión o la fecha de ingreso. Solo audita los campos que de
    verdad cambiaron; si no cambió nada, no escribe ni audita.
    """
    return _actualizar(
        instancia=agente,
        datos=datos,
        editables=CAMPOS_AGENTE_EDITABLES,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def desactivar_agente(*, agente: Agente, autor: Usuario, ip: str | None) -> None:
    """
    Borrado lógico de un agente (CLAUDE.md §7).

    Regla 4: no se desactiva mientras tenga clientes activos. La fila del
    agente se bloquea antes de contar: si al mismo tiempo otra petición le
    asigna un cliente, esa petición espera a que esta termine y entonces ve
    al agente ya desactivado (regla 5). Sin el bloqueo, las dos podrían
    pasar sus comprobaciones y dejar un agente inactivo con cartera.
    """
    agente = _bloquear_agente(agente_id=agente.pk)
    if not agente.activo:
        return

    clientes = contar_clientes_activos(agente=agente)
    if clientes:
        raise AgenteConClientes(agente=agente.codigo, clientes_activos=clientes)

    _desactivar(instancia=agente, autor=autor, ip=ip)


# ---------- Clientes ----------


@transaction.atomic
def crear_cliente(*, datos: dict, autor: Usuario, ip: str | None) -> Cliente:
    """
    Registra un cliente y le asigna su código CLI-NNNNN (regla 10).

    - Si el autor es AGENTE, el cliente queda asignado a él, aunque haya
      enviado otro agente (regla 12). Sin perfil de agente no puede crear.
    - El agente asignado debe estar activo (regla 5); su fila se bloquea por
      la misma razón que en desactivar_agente.
    - La ciudad, si se indica, debe ser del país del cliente (regla 9).
    - Documento y NIT se guardan normalizados y no se repiten (regla 7).

    datos ya viene validado por el serializador: pais, ciudad y
    agente_asignado son objetos, no ids.
    """
    datos = dict(datos)
    if autor.rol.nombre == NombreRol.AGENTE:
        perfil = obtener_agente_de_usuario(usuario=autor)
        if perfil is None:
            raise SinPerfilDeAgente()
        datos["agente_asignado"] = perfil

    agente = _bloquear_agente(agente_id=datos["agente_asignado"].pk)
    if not agente.activo:
        raise AgenteInactivo(agente=agente.codigo)
    datos["agente_asignado"] = agente

    _normalizar_documentos(datos)
    _validar_ciudad(pais=datos["pais"], ciudad=datos.get("ciudad"))
    _validar_no_duplicado(datos)

    cliente = Cliente.objects.create(**datos, creado_por=autor, actualizado_por=autor)
    cliente.codigo = f"CLI-{cliente.pk:05d}"
    cliente.save(update_fields=["codigo"])

    registrar_auditoria(
        usuario=autor,
        entidad=Cliente._meta.db_table,
        entidad_id=cliente.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=_foto(cliente, CAMPOS_CLIENTE_AUDITADOS),
        ip=ip,
    )
    return cliente


@transaction.atomic
def actualizar_cliente(
    *, cliente: Cliente, datos: dict, autor: Usuario, ip: str | None
) -> Cliente:
    """
    Edita los datos del cliente, sin cambiar su agente (eso es
    reasignar_cliente) ni su código.

    Aplica las mismas reglas que al crear sobre el resultado final: si se
    cambia solo el país, la ciudad que ya tenía debe seguir siendo de ese
    país, y el documento no debe chocar con el de otro cliente.
    """
    datos = {
        campo: valor
        for campo, valor in datos.items()
        if campo in CAMPOS_CLIENTE_EDITABLES
    }
    _normalizar_documentos(datos)

    final = {campo: getattr(cliente, campo) for campo in CAMPOS_CLIENTE_EDITABLES}
    final.update(datos)
    _validar_ciudad(pais=final["pais"], ciudad=final["ciudad"])
    _validar_no_duplicado(final, excluir_id=cliente.pk)

    return _actualizar(
        instancia=cliente,
        datos=datos,
        editables=CAMPOS_CLIENTE_EDITABLES,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def desactivar_cliente(*, cliente: Cliente, autor: Usuario, ip: str | None) -> None:
    """Borrado lógico de un cliente. Nunca se borra físicamente (regla 10)."""
    if cliente.activo:
        _desactivar(instancia=cliente, autor=autor, ip=ip)


@transaction.atomic
def reasignar_cliente(
    *, cliente: Cliente, agente: Agente, autor: Usuario, ip: str | None
) -> Cliente:
    """
    Pasa el cliente a otro agente (reglas 5, 8 y 11).

    Si es el mismo agente, no hace nada y no audita: el resultado pedido ya
    se cumple (regla 8). El agente destino se bloquea y debe estar activo.
    """
    if agente.pk == cliente.agente_asignado_id:
        return cliente

    agente = _bloquear_agente(agente_id=agente.pk)
    if not agente.activo:
        raise AgenteInactivo(agente=agente.codigo)

    anterior = cliente.agente_asignado_id
    cliente.agente_asignado = agente
    cliente.actualizado_por = autor
    cliente.save(update_fields=["agente_asignado", "actualizado_por", "actualizado_en"])

    registrar_auditoria(
        usuario=autor,
        entidad=Cliente._meta.db_table,
        entidad_id=cliente.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={"agente_asignado": anterior},
        valores_nuevos={"agente_asignado": agente.pk},
        ip=ip,
    )
    return cliente


# ---------- Apoyo ----------


def _bloquear_agente(*, agente_id: int) -> Agente:
    """
    Lee el agente bloqueando su fila hasta que termine la transacción
    (SELECT ... FOR UPDATE). Otra transacción que quiera bloquearla espera.
    """
    return Agente.objects.select_for_update().get(pk=agente_id)


def _normalizar_documentos(datos: dict) -> None:
    for campo in ("documento_identidad", "nit"):
        if campo in datos:
            datos[campo] = normalizar_documento(datos[campo])


def _validar_ciudad(*, pais, ciudad) -> None:
    if ciudad is not None and ciudad.pais_id != pais.pk:
        raise CiudadFueraDelPais(ciudad=ciudad.nombre, pais=pais.nombre)


def _validar_no_duplicado(datos: dict, excluir_id: int | None = None) -> None:
    """
    Regla 7, comprobada antes de escribir para responder con un error claro.
    El constraint de la base sigue siendo la última barrera.
    """
    if datos["tipo"] == TipoCliente.EMPRESA:
        campo = "nit"
    else:
        campo = "documento_identidad"
    if existe_cliente_con_documento(
        pais_id=datos["pais"].pk,
        tipo=datos["tipo"],
        documento=datos[campo],
        excluir_id=excluir_id,
    ):
        raise ClienteDuplicado(campo=campo, valor=datos[campo])


def _foto(instancia, campos: list[str]) -> dict:
    """
    Valores de los campos para la bitácora. Las relaciones se guardan como su
    id; los Decimal y las fechas los escribe el DjangoJSONEncoder del modelo
    de auditoría.
    """
    return model_to_dict(instancia, fields=campos)


def _actualizar(*, instancia, datos: dict, editables: list[str], autor, ip):
    """
    Aplica los cambios y audita solo los campos que cambiaron, con su valor
    anterior y el nuevo. Si nada cambió, no escribe ni audita.
    """
    antes = _foto(instancia, editables)
    for campo, valor in datos.items():
        if campo in editables:
            setattr(instancia, campo, valor)
    despues = _foto(instancia, editables)

    cambiados = [campo for campo in editables if antes[campo] != despues[campo]]
    if not cambiados:
        return instancia

    instancia.actualizado_por = autor
    instancia.save(update_fields=[*cambiados, "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=instancia._meta.db_table,
        entidad_id=instancia.pk,
        accion=AccionAuditoria.ACTUALIZAR,
        valores_anteriores={campo: antes[campo] for campo in cambiados},
        valores_nuevos={campo: despues[campo] for campo in cambiados},
        ip=ip,
    )
    return instancia


def _desactivar(*, instancia, autor, ip) -> None:
    instancia.activo = False
    instancia.actualizado_por = autor
    instancia.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=instancia._meta.db_table,
        entidad_id=instancia.pk,
        accion=AccionAuditoria.ELIMINAR,
        valores_anteriores={"activo": True},
        valores_nuevos={"activo": False},
        ip=ip,
    )


# ---------- Datos de demostración ----------


@transaction.atomic
def cargar_demo_crm(*, password_agentes: str | None) -> dict[str, int]:
    """
    Carga los agentes y clientes ficticios de datos_demo.py y devuelve cuántos
    creó de cada uno (spec 004, incremento 8).

    Es idempotente: busca cada agente por el correo de su usuario y cada
    cliente por su país y su documento o NIT, y solo crea lo que falta. Nunca
    modifica lo que ya existe, así que correrlo en cada arranque (spec 002,
    §5.8) no duplica nada ni deshace cambios hechos desde la API.

    password_agentes viene de DEMO_AGENTES_PASSWORD. Sin ella, los usuarios de
    los agentes quedan sin contraseña utilizable: ninguna contraseña escrita en
    el repositorio da acceso al sistema desplegado (spec 004, §6).

    Necesita los países y ciudades de demostración de core; seed_demo los carga
    antes. No registra auditoría: es la foto inicial de la demostración, no una
    operación del negocio (spec 004, §7).
    """
    creados = {"agentes": 0, "clientes": 0}
    paises = {pais.codigo_iso: pais for pais in listar_paises()}

    agentes = {}
    for email, nombre, codigo_pais, comision, ingreso in datos_demo.AGENTES:
        usuario, _ = asegurar_usuario_demo(
            email=email,
            nombre_completo=nombre,
            rol=NombreRol.AGENTE,
            password=password_agentes,
        )
        if usuario.pais_id is None:
            usuario.pais = paises[codigo_pais]
            usuario.save(update_fields=["pais"])
        agente = obtener_agente_de_usuario(usuario=usuario)
        if agente is None:
            agente = Agente.objects.create(
                usuario=usuario,
                porcentaje_comision=comision,
                fecha_ingreso=ingreso,
            )
            # Mismo formato que crear_agente (regla 10).
            agente.codigo = f"AGT-{agente.pk:03d}"
            agente.save(update_fields=["codigo"])
            creados["agentes"] += 1
        agentes[email] = agente

    ciudades = {(c.pais.codigo_iso, c.nombre): c for c in listar_ciudades()}
    for datos in datos_demo.CLIENTES:
        datos = dict(datos)
        codigo_pais, nombre_ciudad = datos.pop("ciudad")
        agente = agentes[datos.pop("agente")]
        datos["pais"] = paises[codigo_pais]
        datos["ciudad"] = ciudades[(codigo_pais, nombre_ciudad)]
        _normalizar_documentos(datos)

        campo = "nit" if datos["tipo"] == TipoCliente.EMPRESA else "documento_identidad"
        if existe_cliente_con_documento(
            pais_id=datos["pais"].pk, tipo=datos["tipo"], documento=datos[campo]
        ):
            continue

        cliente = Cliente.objects.create(**datos, agente_asignado=agente)
        cliente.codigo = f"CLI-{cliente.pk:05d}"
        cliente.save(update_fields=["codigo"])
        creados["clientes"] += 1

    return creados
