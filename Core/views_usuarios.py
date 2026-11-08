from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .decorators import permiso_requerido


ROLES_USUARIOS = ('Administrador', 'Operador')


def _usuario_gestionable(pk):
    usuario = get_object_or_404(get_user_model(), pk=pk)
    if usuario.is_superuser or usuario.is_staff:
        raise PermissionDenied('Las cuentas de administración técnica se gestionan desde Django Admin.')
    return usuario


@login_required
@permiso_requerido('auth.view_user')
@never_cache
@require_http_methods(['GET'])
def usuarios(request):
    busqueda = request.GET.get('q', '').strip()[:150]
    consulta = get_user_model().objects.prefetch_related('groups').order_by('username', 'pk')
    if busqueda:
        consulta = consulta.filter(
            Q(username__icontains=busqueda) | Q(first_name__icontains=busqueda)
            | Q(last_name__icontains=busqueda) | Q(email__icontains=busqueda)
        )
    return render(request, 'bodega/usuarios/lista.html', {
        'pagina': Paginator(consulta, 20).get_page(request.GET.get('page')), 'q': busqueda,
    })


def _formulario_usuario(request, usuario=None):
    nuevo = usuario is None
    usuario = usuario or get_user_model()()
    errores = {}
    if request.method == 'POST':
        # Solo estos datos se aceptan: POST nunca decide staff, superuser o permisos.
        datos = {campo: request.POST.get(campo, '').strip() for campo in (
            'username', 'first_name', 'last_name', 'email', 'rol',
        )}
        for campo in ('username', 'first_name', 'last_name', 'email'):
            setattr(usuario, campo, datos[campo])
        password = request.POST.get('password', '')
        confirmacion = request.POST.get('password_confirm', '')
        grupo = None
        if datos['rol'] not in ROLES_USUARIOS:
            errores['rol'] = ['Selecciona Administrador u Operador.']
        else:
            grupo = Group.objects.filter(name=datos['rol']).first()
            if grupo is None:
                errores['rol'] = ['Falta configurar los roles de la aplicación. Ejecuta configurar_roles.']
        if nuevo and not password:
            errores['password'] = ['Ingresa una contraseña.']
        if password or confirmacion:
            if password != confirmacion:
                errores['password_confirm'] = ['Las contraseñas no coinciden.']
            try:
                validate_password(password, usuario)
            except ValidationError as exc:
                errores['password'] = exc.messages
        try:
            usuario.full_clean(exclude=['password'])
        except ValidationError as exc:
            errores.update(exc.message_dict)
        if not errores:
            try:
                with transaction.atomic():
                    if nuevo:
                        # create_user aplica set_password y nunca recibe flags del POST.
                        usuario = get_user_model().objects.create_user(
                            username=datos['username'], email=datos['email'], password=password,
                            first_name=datos['first_name'], last_name=datos['last_name'],
                            is_staff=False, is_superuser=False,
                        )
                    else:
                        # Revalida el privilegio bajo bloqueo si otra sesión cambió la cuenta.
                        usuario = get_user_model().objects.select_for_update().get(pk=usuario.pk)
                        if usuario.is_staff or usuario.is_superuser:
                            raise PermissionDenied('La cuenta pasó a administración técnica y no se puede editar aquí.')
                        for campo in ('username', 'first_name', 'last_name', 'email'):
                            setattr(usuario, campo, datos[campo])
                        if password:
                            usuario.set_password(password)
                        usuario.save(update_fields=[
                            'username', 'first_name', 'last_name', 'email', 'password',
                        ])
                    # Las cuentas gestionadas reciben exactamente el rol elegido.
                    usuario.groups.set([grupo])
                    usuario.user_permissions.clear()
            except IntegrityError:
                errores['__all__'] = ['No se pudo guardar. El nombre de usuario puede haber sido utilizado por otra petición.']
            else:
                if usuario.pk == request.user.pk and password:
                    update_session_auth_hash(request, usuario)
                messages.success(request, 'Usuario creado correctamente.' if nuevo else 'Usuario actualizado correctamente.')
                # Editar el propio rol puede quitar el permiso de gestionar usuarios.
                destino = 'bodega:productos' if usuario.pk == request.user.pk else 'bodega:usuarios'
                return redirect(destino)
        messages.error(request, 'No se guardaron los cambios. Revisa los campos indicados.')
    else:
        datos = {campo: getattr(usuario, campo) for campo in (
            'username', 'first_name', 'last_name', 'email',
        )}
        datos['rol'] = usuario.groups.filter(name__in=ROLES_USUARIOS).values_list('name', flat=True).first() if usuario.pk else 'Operador'
    return render(request, 'bodega/usuarios/form.html', {
        'usuario_objetivo': None if nuevo else usuario, 'datos': datos, 'errores': errores,
        'roles': ROLES_USUARIOS, 'nuevo': nuevo,
        'titulo': 'Crear usuario' if nuevo else 'Editar usuario',
    })


@login_required
@permiso_requerido('auth.view_user', 'auth.add_user')
@sensitive_post_parameters('password', 'password_confirm')
@never_cache
@require_http_methods(['GET', 'POST'])
def usuario_crear(request):
    return _formulario_usuario(request)


@login_required
@permiso_requerido('auth.view_user', 'auth.change_user')
@sensitive_post_parameters('password', 'password_confirm')
@never_cache
@require_http_methods(['GET', 'POST'])
def usuario_editar(request, pk):
    return _formulario_usuario(request, _usuario_gestionable(pk))


@login_required
@permiso_requerido('auth.view_user', 'auth.change_user')
@never_cache
@require_http_methods(['GET', 'POST'])
def usuario_desactivar(request, pk):
    usuario = _usuario_gestionable(pk)
    if usuario.pk == request.user.pk:
        raise PermissionDenied('No puedes desactivar tu propia cuenta.')
    if request.method == 'POST':
        # Desactivación lógica: conserva la trazabilidad y bloquea la autenticación.
        get_user_model().objects.filter(pk=usuario.pk, is_staff=False, is_superuser=False).update(is_active=False)
        messages.success(request, 'Usuario desactivado correctamente.')
        return redirect('bodega:usuarios')
    return render(request, 'bodega/usuarios/desactivar.html', {'usuario_objetivo': usuario})
