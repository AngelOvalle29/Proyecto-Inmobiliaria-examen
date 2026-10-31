"""
Datos de demostración de arrendamientos (spec 008). Solo datos, sin lógica:
los carga cargar_demo_arrendamientos (y seed_demo, después del catálogo, el
CRM y ventas).

Usa el Restaurante Plaza Central del catálogo, el único bien que la demo deja
libre, y un cliente de cargar_demo_crm. Las fechas son relativas a hoy, para
que siempre haya un mes pagado a tiempo, uno pagado tarde con recargo y uno en
mora.
"""

from decimal import Decimal

CONTRATOS = [
    {
        "cliente": "compras@inversiones-demo.test",
        "bien": ("Restaurante Plaza Central", None),
        "dias_desde_inicio": 100,
        "duracion_meses": 12,
        "renta_mensual": Decimal("12000000.00"),
        "deposito": Decimal("24000000.00"),
        "dia_cobro": 5,
        "dias_gracia": 5,
        "porcentaje_mora": Decimal("5.00"),
        # (número de mes, días después del vencimiento en que se pagó)
        "pagos": [(1, 0), (2, 10)],
    },
]
