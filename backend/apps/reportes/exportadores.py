"""Exportadores genéricos: solo reciben Reporte; no consultan modelos."""

from datetime import datetime
from io import BytesIO
from math import ceil
from zoneinfo import ZoneInfo

from django.template.loader import render_to_string
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .estructuras import Reporte

GUATEMALA = ZoneInfo("America/Guatemala")


def _valor_excel(valor):
    if valor is None:
        return "Sin dato"
    if isinstance(valor, datetime) and timezone.is_aware(valor):
        return timezone.localtime(valor, GUATEMALA).replace(tzinfo=None)
    return valor


def _escribir(hoja, fila, columna, valor, formato=""):
    celda = hoja.cell(fila, columna, _valor_excel(valor))
    if isinstance(valor, str):
        # Incluso '=SUM(...)' se guarda como texto, nunca como fórmula.
        celda.data_type = "s"
    if formato:
        celda.number_format = formato
    return celda


def _resumen(valores: dict, prefijo: str = "") -> list[tuple[str, object]]:
    filas = []
    for clave, valor in valores.items():
        etiqueta = (prefijo + " / " + clave if prefijo else clave).replace("_", " ")
        if isinstance(valor, dict):
            filas.extend(_resumen(valor, etiqueta))
        else:
            filas.append((etiqueta, valor))
    return filas


def exportar_excel(reporte: Reporte) -> bytes:
    """Fechas y números tipados; textos externos literales; resumen completo."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"
    fecha_local = timezone.localtime(reporte.generado_en, GUATEMALA)
    for i, texto in enumerate(
        (
            reporte.titulo,
            reporte.subtitulo,
            f"Generado por: {reporte.generado_por}",
            f"Fecha: {fecha_local:%d/%m/%Y %H:%M}",
        ),
        1,
    ):
        _escribir(hoja, i, 1, texto)
    hoja["A1"].font = Font(size=16, bold=True, color="15324F")
    for j, columna in enumerate(reporte.columnas, 1):
        celda = _escribir(hoja, 6, j, columna.etiqueta)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="15324F")
        celda.alignment = Alignment(wrap_text=True, vertical="center")
    hoja.row_dimensions[6].height = 30
    for i, fila in enumerate(reporte.filas, 7):
        for j, columna in enumerate(reporte.columnas, 1):
            celda = _escribir(hoja, i, j, fila.get(columna.nombre), columna.formato)
            celda.alignment = Alignment(
                horizontal=columna.alineacion, wrap_text=True, vertical="top"
            )
    hoja.freeze_panes = "A7"
    hoja.auto_filter.ref = (
        f"A6:{get_column_letter(len(reporte.columnas))}{max(6, 6 + len(reporte.filas))}"
    )
    for j, columna in enumerate(reporte.columnas, 1):
        ancho = max(
            [
                len(columna.etiqueta),
                *[len(str(f.get(columna.nombre) or "")) for f in reporte.filas],
            ]
        )
        hoja.column_dimensions[get_column_letter(j)].width = min(48, max(14, ancho + 2))
    for i, fila in enumerate(reporte.filas, 7):
        lineas = max(
            ceil(
                len(str(fila.get(c.nombre) or ""))
                / (hoja.column_dimensions[get_column_letter(j)].width - 2)
            )
            for j, c in enumerate(reporte.columnas, 1)
        )
        hoja.row_dimensions[i].height = max(16, 15 * lineas)
    resumen = libro.create_sheet("Totales y grupos")
    registros = [("Totales", None), *_resumen(reporte.totales)]
    for grupo in reporte.agrupamientos:
        registros += [(grupo.etiqueta, None), *_resumen(grupo.valores)]
    for i, (etiqueta, valor) in enumerate(registros, 1):
        celda = _escribir(resumen, i, 1, etiqueta)
        celda.font = Font(bold=True)
        _escribir(
            resumen,
            i,
            2,
            valor,
            "#,##0.00" if not isinstance(valor, (str, int)) else "General",
        )
    resumen.column_dimensions["A"].width = 60
    resumen.column_dimensions["B"].width = 28
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _mostrar(valor, tipo="texto") -> str:
    if valor is None:
        return "Sin dato"
    if tipo == "decimal":
        return f"{valor:,.2f}"
    if tipo == "fecha_hora":
        return timezone.localtime(valor, GUATEMALA).strftime("%d/%m/%Y %H:%M")
    if tipo == "fecha":
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def contexto_pdf(reporte: Reporte) -> dict:
    """La plantilla autoescapa texto y no incluye URLs procedentes de datos."""
    pesos = []
    for columna in reporte.columnas:
        longitudes = [len(columna.etiqueta)]
        longitudes.extend(
            len(_mostrar(fila.get(columna.nombre), columna.tipo))
            for fila in reporte.filas
        )
        pesos.append(max(5, min(30, max(longitudes))))
    anchos = [100 * peso / sum(pesos) for peso in pesos]
    return dict(
        anchos=anchos,
        reporte=reporte,
        horizontal=len(reporte.columnas) > 6,
        fecha=timezone.localtime(reporte.generado_en, GUATEMALA),
        filas=[
            [_mostrar(f.get(c.nombre), c.tipo) for c in reporte.columnas]
            for f in reporte.filas
        ],
        totales=_resumen(reporte.totales),
        grupos=[
            dict(etiqueta=g.etiqueta, valores=_resumen(g.valores))
            for g in reporte.agrupamientos
        ],
    )


def exportar_pdf(reporte: Reporte) -> bytes:
    """WeasyPrint se importa al descargar; deniega cualquier recurso externo."""
    from weasyprint import HTML

    def sin_recursos(url, *args, **kwargs):
        raise ValueError("Los reportes no cargan recursos externos.")

    html = render_to_string("reportes/reporte.html", contexto_pdf(reporte))
    return HTML(string=html, url_fetcher=sin_recursos).write_pdf()
