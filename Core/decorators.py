from functools import wraps

from django.core.exceptions import PermissionDenied


def permiso_requerido(*permisos):
    """Autoriza cada petición por permisos efectivos, incluidos los de grupos."""
    def decorar(vista):
        @wraps(vista)
        def comprobar(request, *args, **kwargs):
            if not request.user.is_active or not request.user.has_perms(permisos):
                raise PermissionDenied('No tienes permisos para realizar esta acción.')
            return vista(request, *args, **kwargs)
        return comprobar
    return decorar
