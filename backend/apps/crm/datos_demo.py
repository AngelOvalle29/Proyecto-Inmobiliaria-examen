"""
Datos de demostración de CRM. Solo datos, sin lógica: los carga el servicio
cargar_demo_crm, que invoca el comando del mismo nombre (y seed_demo).

Todo es ficticio: correos *@demo.test, nombres "Demo" numerados y documentos
inventados. Nunca nombres ni documentos de personas reales (CLAUDE.md §11),
porque estos datos podrían llegar a la API de Gemini a través del agente de IA.
"""

from datetime import date
from decimal import Decimal

# (correo, nombre completo, código ISO del país, % de comisión, fecha de ingreso)
AGENTES = [
    ("agente1@demo.test", "Agente Demo Uno", "GTM", Decimal("3.00"), date(2025, 2, 1)),
    ("agente2@demo.test", "Agente Demo Dos", "GTM", Decimal("2.50"), date(2025, 6, 15)),
    (
        "agente3@demo.test",
        "Agente Demo Tres",
        "MEX",
        Decimal("3.50"),
        date(2026, 1, 10),
    ),
]

# Cada cliente indica a qué agente de la lista anterior se asigna (por correo).
# Ciudad: (código ISO del país, nombre), como en los datos de demo de core.
CLIENTES = [
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Uno",
        "documento_identidad": "1000000000101",
        "email": "cliente1@demo.test",
        "ciudad": ("GTM", "Quetzaltenango"),
        "agente": "agente1@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Dos",
        "documento_identidad": "1000000000202",
        "email": "cliente2@demo.test",
        "ciudad": ("GTM", "Quetzaltenango"),
        "agente": "agente1@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Tres",
        "documento_identidad": "1000000000303",
        "email": "",
        "ciudad": ("GTM", "Antigua Guatemala"),
        "agente": "agente1@demo.test",
    },
    {
        "tipo": "EMPRESA",
        "razon_social": "Inversiones Demo Uno, S. A.",
        "nit": "1000001K",
        "email": "compras@inversiones-demo.test",
        "ciudad": ("GTM", "Ciudad de Guatemala"),
        "agente": "agente1@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Cuatro",
        "documento_identidad": "1000000000404",
        "email": "cliente4@demo.test",
        "ciudad": ("GTM", "Ciudad de Guatemala"),
        "agente": "agente2@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Cinco",
        "documento_identidad": "1000000000505",
        "email": "cliente5@demo.test",
        "ciudad": ("GTM", "Ciudad de Guatemala"),
        "agente": "agente2@demo.test",
    },
    {
        "tipo": "EMPRESA",
        "razon_social": "Comercial Demo Dos, S. A.",
        "nit": "1000002K",
        "email": "",
        "ciudad": ("GTM", "Quetzaltenango"),
        "agente": "agente2@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Seis",
        "documento_identidad": "DEMO600000",
        "email": "cliente6@demo.test",
        "ciudad": ("MEX", "Guadalajara"),
        "agente": "agente3@demo.test",
    },
    {
        "tipo": "PERSONA",
        "nombre": "Cliente",
        "apellidos": "Demo Siete",
        "documento_identidad": "DEMO700000",
        "email": "cliente7@demo.test",
        "ciudad": ("MEX", "Ciudad de México"),
        "agente": "agente3@demo.test",
    },
    {
        "tipo": "EMPRESA",
        "razon_social": "Desarrollos Demo Tres, S. A. de C. V.",
        "nit": "DEMO030303",
        "email": "contacto@desarrollos-demo.test",
        "ciudad": ("MEX", "Monterrey"),
        "agente": "agente3@demo.test",
    },
]
