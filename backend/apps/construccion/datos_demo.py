"""Constructoras de demostración (spec 006). Todas ficticias.

Los NIT son inventados y los correos usan el dominio reservado .test.
"""

# Nombre, NIT, contacto, correo, código ISO del país y calificación (o None).
CONSTRUCTORAS = [
    (
        "Constructora Demo Altiplano",
        "8000001-1",
        "Ingeniería de obra",
        "obras@altiplano.test",
        "GTM",
        5,
    ),
    (
        "Edificaciones Demo Occidente",
        "8000002-2",
        "Gerencia de proyectos",
        "proyectos@occidente.test",
        "GTM",
        4,
    ),
    (
        "Remodelaciones Demo",
        "8000003-3",
        "Atención a clientes",
        "contacto@remodelaciones.test",
        "GTM",
        None,
    ),
    (
        "Constructora Demo del Bajío",
        "DEMO850101XY2",
        "Dirección técnica",
        "obras@bajio.test",
        "MEX",
        3,
    ),
]

# Proyectos de construcción (spec 017) sobre las propiedades de
# cargar_demo_catalogo, buscadas por su nombre, con las constructoras de arriba,
# por su NIT. Cada estado coincide con el de la propiedad en la demo:
# - el hotel está EN_CONSTRUCCION: su obra va EN_EJECUCION al 60 %, con un
#   anticipo y un avance pagados y otro avance programado;
# - la gasolinera está ADQUIRIDA: su remodelación está PLANIFICADA, con el
#   anticipo programado.
# Las fechas son días relativos a hoy (negativos, en el pasado). Montos en la
# moneda de la propiedad. Pagos: (tipo, monto, días de la fecha programada,
# días de la fecha de pago o None si sigue programado).
PROYECTOS = [
    {
        "propiedad": "Hotel Brisas del Pacífico",
        "constructora_nit": "8000001-1",
        "nombre": "Terminación del hotel",
        "estado": "EN_EJECUCION",
        "porcentaje_avance": 60,
        "dias_inicio": -120,
        "dias_fin_estimada": 120,
        "presupuesto_total": "1200000.00",
        "pagos": [
            ("ANTICIPO", "240000.00", -125, -125),
            ("AVANCE", "300000.00", -30, -28),
            ("AVANCE", "200000.00", 15, None),
        ],
    },
    {
        "propiedad": "Gasolinera Ruta Sur",
        "constructora_nit": "8000003-3",
        "nombre": "Remodelación de la gasolinera",
        "estado": "PLANIFICADO",
        "porcentaje_avance": 0,
        "dias_inicio": 10,
        "dias_fin_estimada": 70,
        "presupuesto_total": "80000.00",
        "pagos": [("ANTICIPO", "16000.00", 5, None)],
    },
]
