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
