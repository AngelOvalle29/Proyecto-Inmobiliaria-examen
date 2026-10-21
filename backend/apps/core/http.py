"""
Utilidades de la capa HTTP compartidas por las vistas de todas las apps.

Solo las usan las vistas: servicios y selectores reciben los datos ya
extraídos de la petición y nunca conocen request.
"""

from django.conf import settings
from rest_framework.request import Request


def obtener_ip_cliente(request: Request) -> str | None:
    """
    IP real del cliente, para la auditoría.

    Detrás de un proxy (Render), REMOTE_ADDR es la IP del proxy y la del
    cliente viaja en X-Forwarded-For. Pero esa cabecera la puede escribir
    cualquiera: un atacante puede enviar "X-Forwarded-For: 1.2.3.4" y, si se
    tomara el primer valor, la bitácora registraría una IP inventada. Cada
    proxy agrega al final la IP de quien le habló, así que el valor confiable
    es el que agregó nuestro propio proxy: el que está NUM_PROXIES posiciones
    desde el final.

    Usa la misma regla que DRF para el límite de peticiones, así la IP
    auditada y la IP limitada son siempre la misma.
    """
    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies and reenviada:
        direcciones = [direccion.strip() for direccion in reenviada.split(",")]
        return direcciones[-min(num_proxies, len(direcciones))]
    return request.META.get("REMOTE_ADDR")


def obtener_user_agent(request: Request) -> str:
    """Navegador o cliente que hizo la petición, para la auditoría."""
    return request.META.get("HTTP_USER_AGENT", "")
