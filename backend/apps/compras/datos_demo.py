"""Proveedores de demostración (spec 006). Todos ficticios.

Los NIT son inventados y los correos usan el dominio reservado .test: ningún
dato corresponde a una persona o empresa real.
"""

# Tipo, nombre, NIT, correo, código ISO del país y nombre de la ciudad (o None).
PROVEEDORES = [
    (
        "BANCO",
        "Banco Demo de Occidente",
        "9000001-1",
        "adjudicados@bancodemo.test",
        "GTM",
        None,
    ),
    (
        "INMOBILIARIA",
        "Inmobiliaria Altos del Valle",
        "9000002-2",
        "ventas@altosvalle.test",
        "GTM",
        None,
    ),
    (
        "PROPIETARIO_PARTICULAR",
        "Propietario Demo Uno",
        "",
        "propietario1@demo.test",
        "GTM",
        None,
    ),
    (
        "GOBIERNO",
        "Municipalidad Demo",
        "9000003-3",
        "bienes@municipalidad.test",
        "GTM",
        None,
    ),
    (
        "BANCO",
        "Banco Demo del Norte",
        "DEMO900101AB1",
        "inmuebles@bancodemo-mx.test",
        "MEX",
        None,
    ),
    (
        "PROPIETARIO_PARTICULAR",
        "Propietario Demo Dos",
        "",
        "propietario2@demo.test",
        "MEX",
        None,
    ),
]

# Contratos de compra (spec 017) sobre las propiedades de cargar_demo_catalogo,
# buscadas por su nombre, y los proveedores de arriba, por su NIT. Cada estado
# coincide con el de la propiedad en la demo del catálogo:
# - el terreno sigue EN_NEGOCIACION, así su contrato queda EN_PROCESO para
#   mostrar Completar y Anular;
# - la gasolinera (ADQUIRIDA) y el hotel (EN_CONSTRUCCION) ya se compraron.
# Las fechas son días antes de hoy. Montos en la moneda de la propiedad.
CONTRATOS = [
    {
        "propiedad": "Terreno Las Lomas",
        "proveedor_nit": "9000001-1",
        "estado": "EN_PROCESO",
        "dias_desde_compra": 5,
        "monto": "250000.00",
        "gastos_legales": "5000.00",
        "impuestos": "7500.00",
        "observaciones": "Terreno adjudicado por el banco; escritura en trámite.",
    },
    {
        "propiedad": "Gasolinera Ruta Sur",
        "proveedor_nit": "9000003-3",
        "estado": "COMPLETADO",
        "dias_desde_compra": 60,
        "monto": "420000.00",
        "gastos_legales": "8000.00",
        "impuestos": "12600.00",
        "observaciones": "Compra a la municipalidad por subasta pública.",
    },
    {
        "propiedad": "Hotel Brisas del Pacífico",
        "proveedor_nit": "9000002-2",
        "estado": "COMPLETADO",
        "dias_desde_compra": 200,
        "monto": "1800000.00",
        "gastos_legales": "25000.00",
        "impuestos": "54000.00",
        "observaciones": "Hotel en obra gris comprado para terminarlo.",
    },
]
