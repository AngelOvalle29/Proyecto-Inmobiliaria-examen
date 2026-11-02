"""Metadatos compartidos por API, exportadores y pantalla genérica."""

from dataclasses import asdict

from django.http import Http404

from apps.auditoria.enums import AccionAuditoria
from apps.catalogo.enums import TipoDocumento
from apps.usuarios.enums import NombreRol

from .estructuras import Columna


def filtro(nombre, etiqueta, tipo="texto", origen_opciones="", opciones=None):
    return dict(
        nombre=nombre,
        etiqueta=etiqueta,
        tipo=tipo,
        obligatorio=False,
        origen_opciones=origen_opciones,
        buscable=origen_opciones == "/ciudades/",
        opciones=opciones or [],
    )


CATALOGO = {
    "inventario-disponible": {
        "codigo": "R05",
        "titulo": "Inventario disponible",
        "roles": list(NombreRol.values),
        "columnas": [
            Columna("origen", "Origen"),
            Columna("id", "ID", "entero"),
            Columna("codigo", "Código"),
            Columna("nombre", "Propiedad"),
            Columna("ciudad", "Ciudad"),
            Columna("tipo", "Tipo"),
            Columna("moneda", "Moneda"),
            Columna("area_m2", "Área m²", "decimal", "#,##0.00", "right"),
            Columna("precio_lista", "Precio de lista", "decimal", "#,##0.00", "right"),
        ],
        "filtros": [
            filtro("pais", "País", "entero", "/paises/"),
            filtro("ciudad", "Ciudad", "entero", "/ciudades/"),
            filtro("tipo", "Tipo de propiedad", "entero", "/tipos-propiedad/"),
            filtro("moneda", "Moneda", "texto", "/monedas/"),
            *[
                filtro(n, e, "decimal")
                for n, e in [
                    ("precio_min", "Precio mínimo"),
                    ("precio_max", "Precio máximo"),
                    ("area_min", "Área mínima"),
                    ("area_max", "Área máxima"),
                ]
            ],
        ],
    },
    "documentos-por-vencer": {
        "codigo": "R16",
        "titulo": "Documentos por vencer",
        "roles": list(NombreRol.values),
        "columnas": [
            Columna("id", "ID", "entero"),
            Columna("propiedad", "Propiedad"),
            Columna("nombre", "Documento"),
            Columna("tipo", "Tipo"),
            Columna("fecha_vencimiento", "Vencimiento", "fecha", "dd/mm/yyyy"),
            Columna("estado", "Estado"),
        ],
        "filtros": [
            filtro("tipo", "Tipo de documento", "texto", "documentos"),
            filtro("pais", "País", "entero", "/paises/"),
            filtro("dias_anticipacion", "Días de anticipación (0 a 365)", "entero"),
        ],
    },
    "bitacora-auditoria": {
        "codigo": "R17",
        "titulo": "Bitácora de auditoría",
        "roles": [NombreRol.ADMINISTRADOR],
        "columnas": [
            Columna("id", "ID", "entero"),
            Columna("fecha", "Fecha (Guatemala)", "fecha_hora", "dd/mm/yyyy hh:mm"),
            Columna("usuario_id", "Usuario ID", "entero"),
            Columna("entidad", "Entidad"),
            Columna("entidad_id", "Entidad ID", "entero"),
            Columna("accion", "Acción"),
        ],
        "filtros": [
            filtro("usuario", "Usuario ID", "entero"),
            filtro("entidad", "Entidad"),
            filtro("accion", "Acción", "texto", "acciones"),
            filtro("fecha_desde", "Desde", "fecha"),
            filtro("fecha_hasta", "Hasta", "fecha"),
        ],
    },
}


def definicion_reporte(slug: str) -> dict:
    """Un slug desconocido siempre es 404."""
    if slug not in CATALOGO:
        raise Http404
    return CATALOGO[slug]


def metadatos(slug: str) -> dict:
    definicion = definicion_reporte(slug)
    filtros = []
    for filtro_actual in definicion["filtros"]:
        opciones = filtro_actual["opciones"]
        if filtro_actual["origen_opciones"] == "documentos":
            opciones = [dict(valor=v, etiqueta=e) for v, e in TipoDocumento.choices]
        elif filtro_actual["origen_opciones"] == "acciones":
            opciones = [dict(valor=v, etiqueta=e) for v, e in AccionAuditoria.choices]
        filtros.append({**filtro_actual, "opciones": opciones})
    return {
        **definicion,
        "slug": slug,
        "filtros": filtros,
        "columnas": [asdict(c) for c in definicion["columnas"]],
    }
