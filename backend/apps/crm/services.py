"""Servicios de CRM: escrituras con reglas de negocio, transacciones y
auditoría (spec 004, §6 y §7).

No conocen request ni hablan HTTP. Cada escritura registra su auditoría dentro
de la misma transacción: si algo falla, se revierten las dos.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.catalogo.enums import EstadoPropiedad
from apps.catalogo.exceptions import PropiedadNoDisponible
from apps.catalogo.services import cambiar_estado_propiedad, cambiar_estado_unidad
from apps.core.exceptions import CiudadFueraDelPais
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_ciudades, listar_paises
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Usuario
from apps.usuarios.services import asegurar_usuario_demo

from . import datos_demo
from .enums import EstadoCotizacion, TipoCliente
from .exceptions import (
    AgenteConClientes,
    AgenteInactivo,
    ClienteDuplicado,
    CotizacionNoEditable,
    CotizacionVencida,
    CotizacionYaContratada,
    DescuentoFueraDeRango,
    SeVendePorUnidades,
    SinPerfilDeAgente,
    TransicionInvalida,
    UsuarioNoEsAgente,
    UsuarioYaEsAgente,
)
from .models import Agente, Cliente, Cotizacion
from .selectors import (
    contar_clientes_activos,
    cotizacion_tiene_contrato,
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


# ---------- Cotizaciones (spec 007) ----------

CAMPOS_COTIZACION_EDITABLES = [
    "precio",
    "descuento",
    "fecha_vencimiento",
    "observaciones",
]
CAMPOS_COTIZACION_AUDITADOS = [
    "codigo",
    "cliente",
    "agente",
    "propiedad",
    "unidad",
    "fecha_emision",
    "estado",
    "total",
    "moneda",
    *CAMPOS_COTIZACION_EDITABLES,
]


@transaction.atomic
def crear_cotizacion(*, datos: dict, autor: Usuario, ip: str | None) -> Cotizacion:
    """
    Emite una cotización en borrador (spec 007, reglas 1 a 5).

    - Es por una propiedad o una unidad, y un edificio no se cotiza completo
      (regla 1): se cotizan sus unidades.
    - El precio inicial y la moneda son los de lista del bien (regla 2).
    - El agente es el asignado al cliente (regla 3).
    - Solo se cotiza un bien DISPONIBLE (regla 5). No se reserva todavía:
      eso pasa al aprobar.

    datos ya viene validado: el cliente es visible para el autor (cartera) y
    trae exactamente uno de propiedad o unidad.
    """
    bien = datos.get("propiedad") or datos.get("unidad")
    _validar_bien_cotizable(bien, es_propiedad=datos.get("propiedad") is not None)

    precio = bien.precio_lista
    descuento = datos.get("descuento", Decimal("0"))
    _validar_descuento(precio=precio, descuento=descuento)

    cotizacion = Cotizacion.objects.create(
        cliente=datos["cliente"],
        agente=datos["cliente"].agente_asignado,
        propiedad=datos.get("propiedad"),
        unidad=datos.get("unidad"),
        fecha_emision=timezone.localdate(),
        fecha_vencimiento=datos["fecha_vencimiento"],
        precio=precio,
        descuento=descuento,
        total=precio - descuento,
        moneda=bien.moneda,
        observaciones=datos.get("observaciones", ""),
        creado_por=autor,
        actualizado_por=autor,
    )
    cotizacion.codigo = f"COT-{cotizacion.pk:05d}"
    cotizacion.save(update_fields=["codigo"])

    registrar_auditoria(
        usuario=autor,
        entidad=Cotizacion._meta.db_table,
        entidad_id=cotizacion.pk,
        accion=AccionAuditoria.CREAR,
        valores_nuevos=_foto(cotizacion, CAMPOS_COTIZACION_AUDITADOS),
        ip=ip,
    )
    return cotizacion


@transaction.atomic
def actualizar_cotizacion(
    *, cotizacion: Cotizacion, datos: dict, autor: Usuario, ip: str | None
) -> Cotizacion:
    """
    Edita precio, descuento, vencimiento u observaciones de un borrador
    (regla 4). El total se recalcula siempre: nunca se edita directamente
    (regla 2).
    """
    if cotizacion.estado != EstadoCotizacion.BORRADOR:
        raise CotizacionNoEditable(
            cotizacion=cotizacion.codigo, estado=cotizacion.estado
        )

    precio = datos.get("precio", cotizacion.precio)
    descuento = datos.get("descuento", cotizacion.descuento)
    _validar_descuento(precio=precio, descuento=descuento)

    datos = {c: v for c, v in datos.items() if c in CAMPOS_COTIZACION_EDITABLES}
    datos["total"] = precio - descuento
    return _actualizar(
        instancia=cotizacion,
        datos=datos,
        editables=[*CAMPOS_COTIZACION_EDITABLES, "total"],
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def enviar_cotizacion(
    *, cotizacion: Cotizacion, autor: Usuario, ip: str | None
) -> Cotizacion:
    """Regla 4: un borrador vigente pasa a ENVIADA."""
    _exigir_estado(cotizacion, EstadoCotizacion.BORRADOR, accion="enviar")
    _exigir_no_vencida(cotizacion)
    return _cambiar_estado_cotizacion(
        cotizacion,
        EstadoCotizacion.ENVIADA,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def aprobar_cotizacion(
    *, cotizacion: Cotizacion, autor: Usuario, ip: str | None
) -> Cotizacion:
    """
    Regla 6: el cliente aceptó. La cotización enviada y vigente pasa a
    APROBADA y su propiedad o unidad, de DISPONIBLE a RESERVADA.

    El catálogo comprueba que el bien siga DISPONIBLE bajo el bloqueo de su
    fila (estado_requerido), así dos aprobaciones simultáneas sobre el mismo
    bien no pasan las dos: la segunda recibe PROPIEDAD_NO_DISPONIBLE (regla 5).
    """
    _exigir_estado(cotizacion, EstadoCotizacion.ENVIADA, accion="aprobar")
    _exigir_no_vencida(cotizacion)
    _cambiar_estado_bien(
        cotizacion,
        estado=EstadoPropiedad.RESERVADA,
        requerido=EstadoPropiedad.DISPONIBLE,
        motivo=f"Cotización {cotizacion.codigo} aprobada",
        autor=autor,
        ip=ip,
    )
    return _cambiar_estado_cotizacion(
        cotizacion,
        EstadoCotizacion.APROBADA,
        accion=AccionAuditoria.APROBAR,
        autor=autor,
        ip=ip,
    )


@transaction.atomic
def rechazar_cotizacion(
    *, cotizacion: Cotizacion, autor: Usuario, ip: str | None
) -> Cotizacion:
    """
    El cliente no aceptó, o desistió después de aprobar (regla 6).

    - Desde ENVIADA: solo cambia la cotización.
    - Desde APROBADA: además libera el bien, de RESERVADA a DISPONIBLE. Pero si
      ya tiene contrato, no se rechaza: su bien está VENDIDO y rechazarla lo
      volvería a ofrecer.
    """
    if cotizacion.estado == EstadoCotizacion.APROBADA:
        if cotizacion_tiene_contrato(cotizacion=cotizacion):
            raise CotizacionYaContratada(cotizacion=cotizacion.codigo)
        _cambiar_estado_bien(
            cotizacion,
            estado=EstadoPropiedad.DISPONIBLE,
            requerido=EstadoPropiedad.RESERVADA,
            motivo=f"Cotización {cotizacion.codigo} rechazada",
            autor=autor,
            ip=ip,
        )
    else:
        _exigir_estado(cotizacion, EstadoCotizacion.ENVIADA, accion="rechazar")
    return _cambiar_estado_cotizacion(
        cotizacion,
        EstadoCotizacion.RECHAZADA,
        accion=AccionAuditoria.ACTUALIZAR,
        autor=autor,
        ip=ip,
    )


def _validar_bien_cotizable(bien, *, es_propiedad: bool) -> None:
    """Reglas 1 y 5: ni un edificio completo ni un bien que no esté disponible."""
    if es_propiedad and bien.tipo.requiere_unidades:
        raise SeVendePorUnidades(propiedad=bien.codigo)
    if bien.estado != EstadoPropiedad.DISPONIBLE:
        raise PropiedadNoDisponible(
            codigo=str(bien.codigo),
            estado_actual=bien.estado,
            estado_requerido=EstadoPropiedad.DISPONIBLE,
        )


def _validar_descuento(*, precio: Decimal, descuento: Decimal) -> None:
    """Regla 2: el descuento va de 0 al precio."""
    if not (0 <= descuento <= precio):
        raise DescuentoFueraDeRango()


def _exigir_estado(cotizacion: Cotizacion, estado: str, *, accion: str) -> None:
    if cotizacion.estado != estado:
        raise TransicionInvalida(
            cotizacion=cotizacion.codigo, estado=cotizacion.estado, accion=accion
        )


def _exigir_no_vencida(cotizacion: Cotizacion) -> None:
    if cotizacion.esta_vencida():
        raise CotizacionVencida(
            cotizacion=cotizacion.codigo,
            fecha_vencimiento=cotizacion.fecha_vencimiento,
        )


def _cambiar_estado_bien(cotizacion, *, estado, requerido, motivo, autor, ip) -> None:
    """Cambia el estado de la propiedad o la unidad con el servicio del catálogo."""
    if cotizacion.propiedad_id:
        cambiar_estado_propiedad(
            propiedad=cotizacion.propiedad,
            estado=estado,
            autor=autor,
            ip=ip,
            motivo=motivo,
            estado_requerido=requerido,
        )
    else:
        cambiar_estado_unidad(
            unidad=cotizacion.unidad,
            estado=estado,
            autor=autor,
            ip=ip,
            motivo=motivo,
            estado_requerido=requerido,
        )


def _cambiar_estado_cotizacion(cotizacion, estado, *, accion, autor, ip):
    """Cambia el estado de la cotización y audita el anterior y el nuevo."""
    anterior = cotizacion.estado
    cotizacion.estado = estado
    cotizacion.actualizado_por = autor
    cotizacion.save(update_fields=["estado", "actualizado_por", "actualizado_en"])
    registrar_auditoria(
        usuario=autor,
        entidad=Cotizacion._meta.db_table,
        entidad_id=cotizacion.pk,
        accion=accion,
        valores_anteriores={"estado": anterior},
        valores_nuevos={"estado": estado},
        ip=ip,
    )
    return cotizacion
