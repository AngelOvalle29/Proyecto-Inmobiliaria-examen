"""Servicios de compras: escrituras con reglas de negocio, transacciones y
auditoría (spec 006, §6 y §7).

No conocen request ni hablan HTTP. Cada escritura registra su auditoría dentro
de la misma transacción: si algo falla, se revierten las dos.
"""

from django.db import transaction
from django.forms.models import model_to_dict

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.exceptions import CiudadFueraDelPais
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_ciudades, listar_paises
from apps.usuarios.models import Usuario

from . import datos_demo
from .enums import TipoProveedor
from .exceptions import NitObligatorio, ProveedorDuplicado
from .models import Proveedor
from .selectors import existe_proveedor_con_nit

ENTIDAD_PROVEEDOR = "compras_proveedor"

# Campos que se guardan en la bitácora y que se pueden editar. El código no
# está: lo genera el sistema y no cambia nunca (regla 8).
CAMPOS_EDITABLES = [
    "tipo",
    "nombre",
    "nit",
    "email",
    "telefono",
    "pais",
    "ciudad",
    "direccion",
]


def crear_proveedor(*, datos: dict, autor: Usuario, ip: str | None) -> Proveedor:
    """
    Registra un proveedor y le asigna su código PRV-0001.

    - El NIT se guarda normalizado y solo puede faltar en un propietario
      particular (reglas 2 y 3).
    - No puede repetirse el NIT en el mismo país, aunque el otro proveedor
      esté desactivado (regla 3).
    - La ciudad, si se indica, debe ser del país (regla 7).

    datos ya viene validado por el serializador: pais y ciudad son instancias.
    """
    datos = {**datos, "nit": normalizar_documento(datos.get("nit", ""))}
    _validar(datos)

    with transaction.atomic():
        _validar_no_duplicado(pais=datos["pais"], nit=datos["nit"])
        proveedor = Proveedor.objects.create(
            **datos, creado_por=autor, actualizado_por=autor
        )
        # El código sale del id que da PostgreSQL: dos proveedores creados al
        # mismo tiempo nunca reciben el mismo (mismo patrón que la spec 004).
        proveedor.codigo = f"PRV-{proveedor.pk:04d}"
        proveedor.save(update_fields=["codigo"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.CREAR,
            valores_nuevos=_foto(proveedor),
            ip=ip,
        )
    return proveedor


def actualizar_proveedor(
    *, proveedor: Proveedor, datos: dict, autor: Usuario, ip: str | None
) -> Proveedor:
    """
    Edita los campos enviados y audita solo los que cambiaron.

    Las reglas se revisan sobre el resultado final: si cambia solo el tipo a
    BANCO, el NIT que ya tenía debe existir; si cambia solo el país, la ciudad
    que ya tenía debe seguir siendo de ese país. Si nada cambia, no se guarda
    ni se audita.
    """
    if "nit" in datos:
        datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    final = {
        campo: datos.get(campo, getattr(proveedor, campo)) for campo in CAMPOS_EDITABLES
    }
    _validar(final)

    cambios = [
        campo for campo in CAMPOS_EDITABLES if final[campo] != getattr(proveedor, campo)
    ]
    if not cambios:
        return proveedor

    with transaction.atomic():
        if "pais" in cambios or "nit" in cambios:
            _validar_no_duplicado(
                pais=final["pais"], nit=final["nit"], excluir_id=proveedor.pk
            )
        anteriores = _foto(proveedor, cambios)
        for campo in cambios:
            setattr(proveedor, campo, final[campo])
        proveedor.actualizado_por = autor
        proveedor.save(update_fields=[*cambios, "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores=anteriores,
            valores_nuevos=_foto(proveedor, cambios),
            ip=ip,
        )
    return proveedor


def desactivar_proveedor(
    *, proveedor: Proveedor, autor: Usuario, ip: str | None
) -> None:
    """Borrado lógico (regla 9): el proveedor deja de listarse, no se borra."""
    with transaction.atomic():
        proveedor.activo = False
        proveedor.actualizado_por = autor
        proveedor.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_PROVEEDOR,
            entidad_id=proveedor.pk,
            accion=AccionAuditoria.ELIMINAR,
            valores_anteriores={"activo": True},
            valores_nuevos={"activo": False},
            ip=ip,
        )


def cargar_demo_compras() -> dict[str, int]:
    """
    Carga los proveedores ficticios de datos_demo.py y devuelve cuántos creó.

    Es idempotente: busca cada proveedor por su país y su NIT (o por su nombre
    si es un particular sin NIT) y solo crea lo que falta. Necesita los países
    de core, que seed_demo carga antes; si un país no existe, ese proveedor se
    omite. No registra auditoría: es la foto inicial de la demostración, no una
    operación del negocio (mismo criterio que la spec 004).
    """
    paises = {pais.codigo_iso: pais for pais in listar_paises()}
    ciudades = {(c.pais.codigo_iso, c.nombre): c for c in listar_ciudades()}
    creados = 0
    for tipo, nombre, nit, email, codigo_pais, nombre_ciudad in datos_demo.PROVEEDORES:
        pais = paises.get(codigo_pais)
        if pais is None:
            continue
        nit = normalizar_documento(nit)
        existentes = Proveedor.objects.filter(pais=pais)
        existentes = (
            existentes.filter(nit=nit) if nit else existentes.filter(nombre=nombre)
        )
        if existentes.exists():
            continue
        proveedor = Proveedor.objects.create(
            tipo=tipo,
            nombre=nombre,
            nit=nit,
            email=email,
            pais=pais,
            ciudad=ciudades.get((codigo_pais, nombre_ciudad)),
        )
        proveedor.codigo = f"PRV-{proveedor.pk:04d}"
        proveedor.save(update_fields=["codigo"])
        creados += 1
    return {"proveedores": creados}


def _validar(datos: dict) -> None:
    if not datos["nit"] and datos["tipo"] != TipoProveedor.PROPIETARIO_PARTICULAR:
        raise NitObligatorio()
    ciudad, pais = datos.get("ciudad"), datos["pais"]
    if ciudad is not None and ciudad.pais_id != pais.pk:
        raise CiudadFueraDelPais(ciudad=ciudad.nombre, pais=pais.nombre)


def _validar_no_duplicado(*, pais, nit: str, excluir_id: int | None = None) -> None:
    # Sin NIT no hay duplicado posible: varios particulares pueden no tenerlo.
    if nit and existe_proveedor_con_nit(pais=pais, nit=nit, excluir_id=excluir_id):
        raise ProveedorDuplicado(nit=nit, pais=pais.nombre)


def _foto(proveedor: Proveedor, campos: list[str] | None = None) -> dict:
    """Valores para la bitácora; las relaciones quedan como su id."""
    return model_to_dict(proveedor, fields=campos or ["codigo", *CAMPOS_EDITABLES])
