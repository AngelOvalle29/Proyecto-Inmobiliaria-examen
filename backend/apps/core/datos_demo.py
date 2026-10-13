"""
Datos de demostración de los catálogos de core. Solo datos, sin lógica: los
carga el servicio cargar_catalogos_demo, que invoca el comando seed_demo.

Países, ciudades y monedas son geografía pública, no datos personales. Las
tasas de cambio son ficticias: se parecen a las reales para que los montos
convertidos se vean razonables en una demostración, pero no se deben usar
para nada más.
"""

from decimal import Decimal

# (código ISO 4217, nombre, símbolo)
MONEDAS = [
    ("USD", "Dólar estadounidense", "$"),
    ("GTQ", "Quetzal", "Q"),
    ("MXN", "Peso mexicano", "$"),
    ("COP", "Peso colombiano", "$"),
    ("CRC", "Colón costarricense", "₡"),
]

# (nombre, código ISO 3166-1 alfa-3, código de su moneda principal)
PAISES = [
    ("Guatemala", "GTM", "GTQ"),
    ("México", "MEX", "MXN"),
    ("Colombia", "COL", "COP"),
    ("Costa Rica", "CRI", "CRC"),
    # El Salvador usa el dólar como moneda oficial.
    ("El Salvador", "SLV", "USD"),
]

# código ISO del país: [(ciudad, región)]
CIUDADES = {
    "GTM": [
        ("Ciudad de Guatemala", "Guatemala"),
        ("Quetzaltenango", "Quetzaltenango"),
        ("Antigua Guatemala", "Sacatepéquez"),
    ],
    "MEX": [
        ("Ciudad de México", "Ciudad de México"),
        ("Guadalajara", "Jalisco"),
        ("Monterrey", "Nuevo León"),
    ],
    "COL": [
        ("Bogotá", "Bogotá D. C."),
        ("Medellín", "Antioquia"),
        ("Cartagena", "Bolívar"),
    ],
    "CRI": [
        ("San José", "San José"),
        ("Liberia", "Guanacaste"),
    ],
    "SLV": [
        ("San Salvador", "San Salvador"),
        ("Santa Ana", "Santa Ana"),
    ],
}

# Moneda de referencia: todas las tasas se cargan contra ella.
MONEDA_REFERENCIA = "USD"

# Cuántas unidades de cada moneda vale un dólar al inicio del periodo. FICTICIAS.
TASAS_BASE = {
    "GTQ": Decimal("7.75"),
    "MXN": Decimal("18.50"),
    "COP": Decimal("4100.00"),
    "CRC": Decimal("515.00"),
}

# Variación de la tasa de un mes al siguiente (0.2 %), para que el historial no
# sea plano y se note qué tasa se usó en cada fecha.
VARIACION_MENSUAL = Decimal("0.002")

# Cuántos meses de historial se cargan, contando el mes actual.
MESES_DE_HISTORIAL = 6
