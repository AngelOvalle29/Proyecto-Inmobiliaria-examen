"""Servicios de core: escrituras con reglas de negocio, transacciones y
auditoría.

No conocen request ni hablan HTTP.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction

from . import datos_demo
from .models import Ciudad, Moneda, Pais, TipoCambio

# Precisión del campo TipoCambio.tasa (decimal_places=6).
SEIS_DECIMALES = Decimal("0.000001")


@transaction.atomic
def cargar_catalogos_demo(*, hasta: date) -> dict[str, int]:
    """
    Carga monedas, países, ciudades y tipos de cambio de demostración
    (datos_demo.py) y devuelve cuántos registros de cada tipo creó.

    Es idempotente: solo crea lo que falta (get_or_create) y nunca modifica lo
    que ya existe. Correrlo dos veces no duplica nada, y si alguien corrigió
    un dato desde el panel, la corrección se conserva.

    Las tasas se cargan en las dos direcciones respecto al dólar porque el
    sistema no calcula inversas (regla 7). Una por mes, el día 1, durante los
    últimos MESES_DE_HISTORIAL meses hasta la fecha `hasta`.

    Es atómico: si algo falla a la mitad, no queda una carga parcial.

    No registra auditoría: son datos de referencia que carga el sistema, no
    operaciones del negocio (spec 001, §7 y §10).
    """
    creados = {"monedas": 0, "paises": 0, "ciudades": 0, "tipos_cambio": 0}

    # get_or_create devuelve (objeto, creado): creado es True solo si no
    # existía y lo acaba de insertar.
    monedas = {}
    for codigo, nombre, simbolo in datos_demo.MONEDAS:
        moneda, creada = Moneda.objects.get_or_create(
            codigo=codigo, defaults={"nombre": nombre, "simbolo": simbolo}
        )
        monedas[codigo] = moneda
        if creada:
            creados["monedas"] += 1

    for nombre, codigo_iso, codigo_moneda in datos_demo.PAISES:
        pais, creado = Pais.objects.get_or_create(
            codigo_iso=codigo_iso,
            defaults={"nombre": nombre, "moneda_principal": monedas[codigo_moneda]},
        )
        if creado:
            creados["paises"] += 1

        for nombre_ciudad, region in datos_demo.CIUDADES[codigo_iso]:
            _, creada = Ciudad.objects.get_or_create(
                nombre=nombre_ciudad, pais=pais, defaults={"region": region}
            )
            if creada:
                creados["ciudades"] += 1

    dolar = monedas[datos_demo.MONEDA_REFERENCIA]
    fechas = _primeros_de_mes(hasta=hasta, cantidad=datos_demo.MESES_DE_HISTORIAL)
    for codigo, tasa_base in datos_demo.TASAS_BASE.items():
        for numero_mes, fecha in enumerate(fechas):
            tasa = tasa_base * (1 + datos_demo.VARIACION_MENSUAL * numero_mes)
            pares = [
                (dolar, monedas[codigo], tasa),
                (monedas[codigo], dolar, 1 / tasa),
            ]
            for origen, destino, valor in pares:
                _, creado = TipoCambio.objects.get_or_create(
                    moneda_origen=origen,
                    moneda_destino=destino,
                    fecha=fecha,
                    defaults={"tasa": valor.quantize(SEIS_DECIMALES)},
                )
                if creado:
                    creados["tipos_cambio"] += 1

    return creados


def _primeros_de_mes(*, hasta: date, cantidad: int) -> list[date]:
    """
    Día 1 de los últimos `cantidad` meses hasta `hasta`, del más antiguo al
    más reciente. Con hasta=2026-02-15 y cantidad=3: 2025-12-01, 2026-01-01 y
    2026-02-01.
    """
    fechas = []
    anio, mes = hasta.year, hasta.month
    for _ in range(cantidad):
        fechas.append(date(anio, mes, 1))
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return list(reversed(fechas))
