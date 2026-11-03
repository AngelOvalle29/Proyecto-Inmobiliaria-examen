"""Una tasa pequeña no debe parecer cero al presentar un cobro."""

from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import load_workbook

from apps.reportes.estructuras import Columna, Reporte
from apps.reportes.exportadores import contexto_pdf, exportar_excel


def test_pdf_y_excel_conservan_seis_decimales_de_tasa_y_dos_de_dinero():
    reporte = Reporte(
        titulo="Flujo de ingresos",
        subtitulo="",
        generado_en=timezone.now(),
        generado_por="Prueba",
        columnas=[
            Columna("recibido", "Recibido", "decimal", "#,##0.00"),
            Columna("tasa_a_usd", "Tasa a USD", "decimal", "0.000000"),
            Columna("monto_usd", "Recibido USD", "decimal", "#,##0.00"),
        ],
        filas=[
            dict(
                recibido=Decimal("12000000.00"),
                tasa_a_usd=Decimal("0.000243"),
                monto_usd=Decimal("2916.00"),
            )
        ],
        totales={},
        agrupamientos=[],
    )
    assert contexto_pdf(reporte)["filas"] == [["12,000,000.00", "0.000243", "2,916.00"]]
    hoja = load_workbook(BytesIO(exportar_excel(reporte)))["Reporte"]
    assert hoja["B7"].value == 0.000243
    assert hoja["B7"].number_format == "0.000000"
    assert hoja["A7"].number_format == hoja["C7"].number_format == "#,##0.00"
