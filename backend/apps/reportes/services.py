"""Orquesta permisos, vista previa y exportación sobre los mismos selectores."""

from dataclasses import asdict

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils import timezone

from .catalogo import definicion_reporte
from .estructuras import FiltrosReporte, Reporte, ReportePaginado, ResumenReporte
from .exceptions import ReporteDemasiadoGrande
from .selectors import resumir_reporte, seleccionar_filas_reporte


def comprobar_permiso(*, slug: str, usuario: AbstractBaseUser) -> dict:
    """Repite la autorización en JSON y ambas descargas."""
    definicion = definicion_reporte(slug)
    if not usuario.is_authenticated or usuario.rol.nombre not in definicion["roles"]:
        raise PermissionDenied("Su rol no permite consultar este reporte.")
    return definicion


def construir_reporte(
    *,
    slug: str,
    filas: list[dict],
    resumen: ResumenReporte,
    filtros: FiltrosReporte,
    usuario: AbstractBaseUser,
) -> Reporte:
    """Presentación sin consultas; recibe detalles y agregados ya seleccionados."""
    definicion = definicion_reporte(slug)
    subtitulo = "; ".join(
        f"{k}: {v}" for k, v in asdict(filtros).items() if v is not None
    )
    return Reporte(
        definicion["titulo"],
        subtitulo or "Sin filtros",
        timezone.now(),
        usuario.nombre_completo,
        definicion["columnas"],
        filas,
        resumen.totales,
        resumen.agrupamientos,
    )


def obtener_reporte_paginado(
    *, slug: str, filtros: FiltrosReporte, usuario: AbstractBaseUser, pagina: int = 1
) -> ReportePaginado:
    """Comprueba el acceso y devuelve 25 detalles con el resumen completo."""
    comprobar_permiso(slug=slug, usuario=usuario)
    resumen = resumir_reporte(slug=slug, filtros=filtros, usuario=usuario)
    if pagina < 1 or (pagina > 1 and (pagina - 1) * 25 >= resumen.count):
        raise Http404
    filas = seleccionar_filas_reporte(
        slug=slug,
        filtros=filtros,
        offset=(pagina - 1) * 25,
        limite=25,
        usuario=usuario,
    )
    return ReportePaginado(
        construir_reporte(
            slug=slug, filas=filas, resumen=resumen, filtros=filtros, usuario=usuario
        ),
        resumen.count,
        pagina,
    )


def obtener_reporte_exportacion(
    *, slug: str, filtros: FiltrosReporte, usuario: AbstractBaseUser
) -> Reporte:
    """Rechaza más de 5,000 filas antes de cargar el detalle para exportar."""
    comprobar_permiso(slug=slug, usuario=usuario)
    resumen = resumir_reporte(slug=slug, filtros=filtros, usuario=usuario)
    if resumen.count > 5000:
        raise ReporteDemasiadoGrande(
            "El reporte supera 5,000 filas. Acote los filtros."
        )
    filas = seleccionar_filas_reporte(
        slug=slug, filtros=filtros, offset=0, limite=5000, usuario=usuario
    )
    return construir_reporte(
        slug=slug, filas=filas, resumen=resumen, filtros=filtros, usuario=usuario
    )
