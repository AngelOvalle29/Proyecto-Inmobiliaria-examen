"""Servicios de construcción: escrituras con reglas de negocio, transacciones y
auditoría (spec 006, §6 y §7).

No conocen request ni hablan HTTP. Cada escritura registra su auditoría dentro
de la misma transacción: si algo falla, se revierten las dos.
"""

from django.db import transaction
from django.forms.models import model_to_dict

from apps.auditoria.enums import AccionAuditoria
from apps.auditoria.services import registrar_auditoria
from apps.core.normalizacion import normalizar_documento
from apps.core.selectors import listar_paises
from apps.usuarios.models import Usuario

from . import datos_demo
from .exceptions import ConstructoraDuplicada, NitObligatorio
from .models import Constructora
from .selectors import existe_constructora_con_nit

ENTIDAD_CONSTRUCTORA = "construccion_constructora"

# Campos que se guardan en la bitácora y que se pueden editar. El código no
# está: lo genera el sistema y no cambia nunca (regla 8).
CAMPOS_EDITABLES = [
    "nombre",
    "nit",
    "contacto",
    "email",
    "telefono",
    "pais",
    "calificacion",
]


def crear_constructora(*, datos: dict, autor: Usuario, ip: str | None) -> Constructora:
    """
    Registra una constructora y le asigna su código CST-0001.

    - El NIT es obligatorio y se guarda normalizado (reglas 4 y 5).
    - No puede repetirse en el mismo país, aunque la otra constructora esté
      desactivada (regla 5).
    - La calificación, si se indica, va de 1 a 5; la valida el serializador y
      la base (regla 6).
    """
    datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    _validar(datos)

    with transaction.atomic():
        _validar_no_duplicado(pais=datos["pais"], nit=datos["nit"])
        constructora = Constructora.objects.create(
            **datos, creado_por=autor, actualizado_por=autor
        )
        # El código sale del id que da PostgreSQL (mismo patrón que la spec 004).
        constructora.codigo = f"CST-{constructora.pk:04d}"
        constructora.save(update_fields=["codigo"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.CREAR,
            valores_nuevos=_foto(constructora),
            ip=ip,
        )
    return constructora


def actualizar_constructora(
    *, constructora: Constructora, datos: dict, autor: Usuario, ip: str | None
) -> Constructora:
    """Edita los campos enviados y audita solo los que cambiaron.

    Si nada cambia, no se guarda ni se audita.
    """
    if "nit" in datos:
        datos = {**datos, "nit": normalizar_documento(datos["nit"])}
    final = {
        campo: datos.get(campo, getattr(constructora, campo))
        for campo in CAMPOS_EDITABLES
    }
    _validar(final)

    cambios = [
        campo
        for campo in CAMPOS_EDITABLES
        if final[campo] != getattr(constructora, campo)
    ]
    if not cambios:
        return constructora

    with transaction.atomic():
        if "pais" in cambios or "nit" in cambios:
            _validar_no_duplicado(
                pais=final["pais"], nit=final["nit"], excluir_id=constructora.pk
            )
        anteriores = _foto(constructora, cambios)
        for campo in cambios:
            setattr(constructora, campo, final[campo])
        constructora.actualizado_por = autor
        constructora.save(update_fields=[*cambios, "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.ACTUALIZAR,
            valores_anteriores=anteriores,
            valores_nuevos=_foto(constructora, cambios),
            ip=ip,
        )
    return constructora


def desactivar_constructora(
    *, constructora: Constructora, autor: Usuario, ip: str | None
) -> None:
    """Borrado lógico (regla 9): deja de listarse, no se borra."""
    with transaction.atomic():
        constructora.activo = False
        constructora.actualizado_por = autor
        constructora.save(update_fields=["activo", "actualizado_por", "actualizado_en"])
        registrar_auditoria(
            usuario=autor,
            entidad=ENTIDAD_CONSTRUCTORA,
            entidad_id=constructora.pk,
            accion=AccionAuditoria.ELIMINAR,
            valores_anteriores={"activo": True},
            valores_nuevos={"activo": False},
            ip=ip,
        )


def cargar_demo_construccion() -> dict[str, int]:
    """
    Carga las constructoras ficticias de datos_demo.py y devuelve cuántas creó.

    Es idempotente: busca cada una por su país y su NIT y solo crea lo que
    falta. Si un país no existe todavía, esa constructora se omite. No registra
    auditoría: es la foto inicial de la demostración (mismo criterio que la
    spec 004).
    """
    paises = {pais.codigo_iso: pais for pais in listar_paises()}
    creadas = 0
    for (
        nombre,
        nit,
        contacto,
        email,
        codigo_pais,
        calificacion,
    ) in datos_demo.CONSTRUCTORAS:
        pais = paises.get(codigo_pais)
        nit = normalizar_documento(nit)
        if pais is None or Constructora.objects.filter(pais=pais, nit=nit).exists():
            continue
        constructora = Constructora.objects.create(
            nombre=nombre,
            nit=nit,
            contacto=contacto,
            email=email,
            pais=pais,
            calificacion=calificacion,
        )
        constructora.codigo = f"CST-{constructora.pk:04d}"
        constructora.save(update_fields=["codigo"])
        creadas += 1
    return {"constructoras": creadas}


def _validar(datos: dict) -> None:
    if not datos["nit"]:
        raise NitObligatorio()


def _validar_no_duplicado(*, pais, nit: str, excluir_id: int | None = None) -> None:
    if existe_constructora_con_nit(pais=pais, nit=nit, excluir_id=excluir_id):
        raise ConstructoraDuplicada(nit=nit, pais=pais.nombre)


def _foto(constructora: Constructora, campos: list[str] | None = None) -> dict:
    """Valores para la bitácora; el país queda como su id."""
    return model_to_dict(constructora, fields=campos or ["codigo", *CAMPOS_EDITABLES])
