"""
Permisos de acceso por rol, reutilizables por las vistas de todas las apps
(spec 004, §6 y §10).

Es capa HTTP: decide si una petición puede entrar a una vista según el rol de
quien la hace. Qué registros ve cada usuario (la cartera de un agente) no se
decide aquí, sino en el selector de cada app.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class TieneRol(BasePermission):
    """
    Permite cada método HTTP solo a los roles que la vista declara en
    roles_por_metodo:

        permission_classes = [TieneRol]
        roles_por_metodo = {
            "POST": [NombreRol.ADMINISTRADOR, NombreRol.GERENTE],
        }

    Lo que la vista no declara se resuelve así:
    - Un método seguro (GET, HEAD, OPTIONS) queda para cualquier usuario
      autenticado: leer no cambia nada.
    - Un método de escritura (POST, PUT, PATCH, DELETE) se rechaza con 403.
      Olvidar declararlo deja la escritura cerrada, no abierta: es el mismo
      criterio del permiso global de la spec 001.

    Un usuario sin autenticar nunca pasa. DRF responde 401 en ese caso, y 403
    cuando el usuario sí se autenticó pero su rol no alcanza.
    """

    message = "Su rol no permite realizar esta operación."

    def has_permission(self, request, view) -> bool:
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            return False

        roles_por_metodo = getattr(view, "roles_por_metodo", {})
        # HEAD es un GET sin cuerpo: si la vista restringe GET, HEAD sigue la
        # misma regla en vez de quedar abierto como método seguro (spec 024,
        # regla 4).
        metodo = "GET" if request.method == "HEAD" else request.method
        roles = roles_por_metodo.get(metodo)
        if roles is None:
            return request.method in SAFE_METHODS
        return usuario.rol.nombre in roles
