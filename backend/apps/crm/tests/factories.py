"""
Fábricas de datos de prueba para los modelos de CRM.

Datos ficticios y numerados: nunca nombres ni documentos de personas reales.
"""

from datetime import date
from decimal import Decimal

import factory

from apps.core.tests.factories import PaisFactory
from apps.crm.enums import TipoCliente
from apps.crm.models import Agente, Cliente
from apps.usuarios.enums import NombreRol
from apps.usuarios.models import Rol
from apps.usuarios.tests.factories import UsuarioFactory


class AgenteFactory(factory.django.DjangoModelFactory):
    """
    Agente con su usuario de rol AGENTE. El código queda nulo: lo asigna el
    servicio, y las pruebas de modelo no lo necesitan.
    """

    class Meta:
        model = Agente

    usuario = factory.SubFactory(
        UsuarioFactory,
        rol=factory.LazyFunction(lambda: Rol.objects.get(nombre=NombreRol.AGENTE)),
    )
    porcentaje_comision = Decimal("3.00")
    fecha_ingreso = date(2026, 1, 15)


class ClienteFactory(factory.django.DjangoModelFactory):
    """Persona con sus tres datos obligatorios. Para una empresa, ver abajo."""

    class Meta:
        model = Cliente

    tipo = TipoCliente.PERSONA
    nombre = "Cliente"
    apellidos = factory.Sequence(lambda n: f"Demo {n}")
    documento_identidad = factory.Sequence(lambda n: f"DOC{n:010d}")
    pais = factory.SubFactory(PaisFactory)
    agente_asignado = factory.SubFactory(AgenteFactory)


class EmpresaFactory(ClienteFactory):
    tipo = TipoCliente.EMPRESA
    nombre = ""
    apellidos = ""
    documento_identidad = ""
    razon_social = factory.Sequence(lambda n: f"Empresa Demo {n}, S. A.")
    nit = factory.Sequence(lambda n: f"NIT{n:08d}")
