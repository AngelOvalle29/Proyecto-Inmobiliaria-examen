"""
Datos de demostración del catálogo. Solo datos, sin lógica: los carga el
servicio cargar_demo_catalogo, que invoca el comando del mismo nombre.

Nombres, direcciones y precios son FICTICIOS. Las ciudades y monedas son las de
core/datos_demo.py, que seed_demo carga antes.
"""

from datetime import date
from decimal import Decimal

# Cada propiedad: nombre (identifica la propiedad al volver a correr la carga),
# tipo, (código ISO del país, ciudad), dirección, área, área construida,
# precio de lista, moneda, estado, es_publica y descripción.
PROPIEDADES = [
    {
        "nombre": "Torre Mirador del Valle",
        "tipo": "Apartamentos",
        "ciudad": ("GTM", "Quetzaltenango"),
        "direccion": "Avenida Demo 12-34, zona 3",
        "area_m2": Decimal("1800.00"),
        "area_construida_m2": Decimal("5400.00"),
        "precio_lista": Decimal("12500000.00"),
        "moneda": "GTQ",
        "estado": "DISPONIBLE",
        "es_publica": True,
        "descripcion": "Edificio de apartamentos de seis niveles con parqueo.",
    },
    {
        "nombre": "Casa Jardines de la Montaña",
        "tipo": "Casa",
        "ciudad": ("GTM", "Antigua Guatemala"),
        "direccion": "Calle Ficticia 5, colonia Demo",
        "area_m2": Decimal("320.00"),
        "area_construida_m2": Decimal("210.00"),
        "precio_lista": Decimal("1850000.00"),
        "moneda": "GTQ",
        "estado": "DISPONIBLE",
        "es_publica": True,
        "descripcion": "Casa de tres habitaciones con jardín.",
    },
    {
        "nombre": "Terreno Las Lomas",
        "tipo": "Terreno",
        "ciudad": ("GTM", "Ciudad de Guatemala"),
        "direccion": "Kilómetro demo 18, carretera ficticia",
        "area_m2": Decimal("5000.00"),
        "area_construida_m2": None,
        "precio_lista": Decimal("450000.00"),
        "moneda": "USD",
        "estado": "EN_NEGOCIACION",
        "es_publica": False,
        "descripcion": "Terreno plano con acceso a servicios.",
    },
    {
        "nombre": "Hotel Brisas del Pacífico",
        "tipo": "Hotel",
        "ciudad": ("CRI", "Liberia"),
        "direccion": "Paseo Demo 100",
        "area_m2": Decimal("3200.00"),
        "area_construida_m2": Decimal("4100.00"),
        "precio_lista": Decimal("3200000.00"),
        "moneda": "USD",
        "estado": "EN_CONSTRUCCION",
        "es_publica": False,
        "descripcion": "Hotel de playa en construcción.",
    },
    {
        "nombre": "Bodega Parque Industrial Norte",
        "tipo": "Bodega",
        "ciudad": ("MEX", "Monterrey"),
        "direccion": "Boulevard Ficticio 2500",
        "area_m2": Decimal("2400.00"),
        "area_construida_m2": Decimal("2000.00"),
        "precio_lista": Decimal("38000.00"),
        "moneda": "MXN",
        "estado": "ARRENDADA",
        "es_publica": False,
        "descripcion": "Bodega con andén de carga, arrendada por mes.",
    },
    {
        "nombre": "Restaurante Plaza Central",
        "tipo": "Restaurante",
        "ciudad": ("COL", "Medellín"),
        "direccion": "Carrera Demo 45 # 10-20",
        "area_m2": Decimal("260.00"),
        "area_construida_m2": Decimal("240.00"),
        "precio_lista": Decimal("1450000000.00"),
        "moneda": "COP",
        "estado": "DISPONIBLE",
        "es_publica": True,
        "descripcion": "Local equipado para restaurante en zona comercial.",
    },
    {
        "nombre": "Gasolinera Ruta Sur",
        "tipo": "Gasolinera",
        "ciudad": ("SLV", "Santa Ana"),
        "direccion": "Carretera Demo, kilómetro 64",
        "area_m2": Decimal("1500.00"),
        "area_construida_m2": Decimal("350.00"),
        "precio_lista": Decimal("950000.00"),
        "moneda": "USD",
        "estado": "ADQUIRIDA",
        "es_publica": False,
        "descripcion": "Estación de servicio con tienda de conveniencia.",
    },
]

# Unidades por nombre de propiedad: (código, nivel, área, habitaciones, baños,
# precio de lista, estado). La moneda es la de la propiedad.
UNIDADES = {
    "Torre Mirador del Valle": [
        ("A-101", 1, Decimal("85.00"), 2, 1, Decimal("650000.00"), "DISPONIBLE"),
        ("A-102", 1, Decimal("85.00"), 2, 1, Decimal("650000.00"), "RESERVADA"),
        ("A-201", 2, Decimal("110.00"), 3, 2, Decimal("820000.00"), "DISPONIBLE"),
        ("A-202", 2, Decimal("110.00"), 3, 2, Decimal("820000.00"), "VENDIDA"),
        ("L-001", 0, Decimal("60.00"), 0, 1, Decimal("540000.00"), "ARRENDADA"),
    ],
    "Hotel Brisas del Pacífico": [
        ("S-101", 1, Decimal("45.00"), 1, 1, Decimal("95000.00"), "EN_CONSTRUCCION"),
        ("S-102", 1, Decimal("45.00"), 1, 1, Decimal("95000.00"), "EN_CONSTRUCCION"),
        ("S-201", 2, Decimal("70.00"), 2, 2, Decimal("140000.00"), "EN_CONSTRUCCION"),
    ],
}

# Avalúos por nombre de propiedad: (fecha, valor, perito, metodología,
# observaciones). Son fechas pasadas y nombres ficticios. La moneda es la de la
# propiedad. Torre Mirador tiene dos para mostrar la plusvalía en el historial.
AVALUOS = {
    "Torre Mirador del Valle": [
        (
            date(2025, 3, 10),
            Decimal("11000000.00"),
            "Perito de demostración uno",
            "Comparativo de mercado",
            "Avalúo inicial del edificio.",
        ),
        (
            date(2026, 3, 12),
            Decimal("12500000.00"),
            "Perito de demostración uno",
            "Comparativo de mercado",
            "Actualización anual para la venta.",
        ),
    ],
    "Casa Jardines de la Montaña": [
        (
            date(2026, 1, 20),
            Decimal("1750000.00"),
            "Perito de demostración dos",
            "Comparativo de mercado",
            "Avalúo para la ficha de la casa.",
        ),
    ],
    "Terreno Las Lomas": [
        (
            date(2025, 11, 5),
            Decimal("420000.00"),
            "Perito de demostración dos",
            "Costo de reposición",
            "Terreno sin construcción.",
        ),
    ],
    "Hotel Brisas del Pacífico": [
        (
            date(2026, 2, 10),
            Decimal("2900000.00"),
            "Perito de demostración tres",
            "Costo de reposición",
            "Avalúo de la obra en construcción.",
        ),
    ],
    "Bodega Parque Industrial Norte": [
        (
            date(2025, 9, 18),
            Decimal("36000.00"),
            "Perito de demostración tres",
            "Comparativo de mercado",
            "Bodega en operación.",
        ),
    ],
    "Restaurante Plaza Central": [
        (
            date(2026, 4, 2),
            Decimal("1350000000.00"),
            "Perito de demostración uno",
            "Comparativo de mercado",
            "Local comercial con mobiliario.",
        ),
    ],
    "Gasolinera Ruta Sur": [
        (
            date(2025, 12, 12),
            Decimal("900000.00"),
            "Perito de demostración dos",
            "Costo de reposición",
            "Estación de servicio en operación.",
        ),
    ],
}
