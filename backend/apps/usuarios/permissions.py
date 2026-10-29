"""
Permisos de acceso por rol (spec 004, §6).

Viven en usuarios porque el rol es parte del usuario, y son de la capa HTTP:
los usan las vistas de todas las apps, nunca los servicios.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class TieneRol(BasePermission):
    """
    Permite cada método HTTP solo a los roles que la vista declara en
    roles_por_metodo, por ejemplo:

        roles_por_metodo = {"POST": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE]}

    Un método seguro (GET, HEAD, OPTIONS) que no aparece queda para cualquier
    usuario autenticado. Un método de escritura (POST, PUT, PATCH, DELETE) que
    no aparece se rechaza con 403: olvidar declararlo cierra, no abre.
    """

    message = "Su rol no tiene permiso para esta operación."

    def has_permission(self, request: Request, view: APIView) -> bool:
        # Sin sesión, DRF responde 401 (no autenticado) y no 403.
        if not request.user or not request.user.is_authenticated:
            return False

        roles = getattr(view, "roles_por_metodo", {}).get(request.method)
        if roles is None:
            return request.method in SAFE_METHODS
        return request.user.rol.nombre in roles
