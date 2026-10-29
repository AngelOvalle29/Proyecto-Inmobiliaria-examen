"""
Datos de demostración de ventas (spec 007). Solo datos, sin lógica: los carga
el servicio cargar_demo_ventas, que invoca el comando del mismo nombre (y
seed_demo, después del catálogo y del CRM).

Usa las propiedades de cargar_demo_catalogo y los clientes de cargar_demo_crm,
por su nombre y su correo. Las fechas son relativas a hoy, para que siempre
haya cuotas pagadas, una parcial y otras en mora.
"""

from decimal import Decimal

# Un bien es (nombre de la propiedad, código de la unidad o None).

CONTRATOS = [
    {
        # Financiado, firmado hace 95 días: sus tres primeras cuotas ya
        # vencieron. La 1 está pagada, la 2 a medias y la 3 sin pagar.
        "cliente": "cliente1@demo.test",
        "bien": ("Torre Mirador del Valle", "A-201"),
        "dias_desde_firma": 95,
        "modalidad": "FINANCIADO",
        "porcentaje_enganche": Decimal("20"),
        "numero_cuotas": 60,
        "tasa_interes_anual": Decimal("8.50"),
        "pagos": [(1, Decimal("1")), (2, Decimal("0.5"))],  # (cuota, fracción)
    },
    {
        "cliente": "cliente4@demo.test",
        "bien": ("Casa Jardines de la Montaña", None),
        "dias_desde_firma": 40,
        "modalidad": "CONTADO",
    },
]

# (cliente, bien, hasta qué estado se lleva)
COTIZACIONES = [
    ("cliente2@demo.test", ("Torre Mirador del Valle", "A-101"), "APROBADA"),
    ("compras@inversiones-demo.test", ("Restaurante Plaza Central", None), "ENVIADA"),
]
