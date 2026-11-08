from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import Categoria, Proveedor, Sucursal


# Lista cerrada: la URL no permite elegir modelos o campos arbitrarios.
CATALOGOS = {
    'categorias': (Categoria, 'Categorías', (
        ('nombre', 'Nombre', 'text', True, 80),
        ('descripcion', 'Descripción', 'textarea', False, None),
    )),
    'proveedores': (Proveedor, 'Proveedores', (
        ('nombre', 'Razón social', 'text', True, 120),
        ('rut', 'RUT', 'text', True, 12),
        ('email', 'Correo electrónico', 'email', False, 254),
        ('telefono', 'Teléfono', 'text', False, 20),
        ('direccion', 'Dirección', 'text', False, 200),
        ('activo', 'Proveedor activo', 'checkbox', False, None),
    )),
    'sucursales': (Sucursal, 'Sucursales', (
        ('codigo', 'Código', 'text', True, 30),
        ('nombre', 'Nombre', 'text', True, 120),
        ('direccion', 'Dirección', 'text', False, 200),
        ('activa', 'Sucursal activa', 'checkbox', False, None),
    )),
}


def _autorizar(request, tipo, accion):
    try:
        modelo, titulo, campos = CATALOGOS[tipo]
    except KeyError as exc:
        raise Http404('Catálogo no encontrado.') from exc
    permisos = (f'bodega.view_{modelo._meta.model_name}', f'bodega.{accion}_{modelo._meta.model_name}')
    if not request.user.is_active or not request.user.has_perms(permisos):
        raise PermissionDenied
    return modelo, titulo, campos


@login_required
@require_http_methods(['GET'])
def catalogo_lista(request, tipo):
    modelo, titulo, campos = _autorizar(request, tipo, 'view')
    consulta = modelo.objects.order_by('nombre', 'pk')
    texto = request.GET.get('q', '').strip()[:120]
    if texto:
        consulta = consulta.filter(nombre__icontains=texto)
    pagina = Paginator(consulta, 20).get_page(request.GET.get('page'))
    registros = []
    for objeto in pagina:
        valores = []
        for campo, etiqueta, entrada, _, _ in campos:
            valor = getattr(objeto, campo)
            valores.append(('Sí' if valor else 'No') if entrada == 'checkbox' else valor)
        registros.append({'objeto': objeto, 'valores': valores})
    nombre = modelo._meta.model_name
    return render(request, 'bodega/catalogo_lista.html', {
        'titulo': titulo, 'tipo': tipo, 'campos': campos, 'registros': registros,
        'pagina': pagina, 'q': texto,
        'puede_crear': request.user.has_perm(f'bodega.add_{nombre}'),
        'puede_editar': request.user.has_perm(f'bodega.change_{nombre}'),
        'puede_eliminar': request.user.has_perm(f'bodega.delete_{nombre}'),
    })


def _formulario(request, tipo, pk=None):
    modelo, titulo, definiciones = _autorizar(request, tipo, 'add' if pk is None else 'change')
    objeto = modelo() if pk is None else get_object_or_404(modelo, pk=pk)
    errores = {}
    if request.method == 'POST':
        datos = {}
        for nombre, _, entrada, _, _ in definiciones:
            valor = request.POST.get(nombre) == '1' if entrada == 'checkbox' else request.POST.get(nombre, '').strip()
            datos[nombre] = valor
            setattr(objeto, nombre, valor)
        try:
            objeto.full_clean()
        except ValidationError as exc:
            errores = exc.message_dict
        if not errores:
            try:
                with transaction.atomic():
                    objeto.save()
            except IntegrityError:
                errores['__all__'] = ['No se pudo guardar. Revisa los valores únicos y vuelve a intentarlo.']
            else:
                messages.success(request, 'Registro guardado correctamente.')
                return redirect('bodega:catalogo_lista', tipo=tipo)
        messages.error(request, 'Revisa los campos indicados; no se guardaron cambios.')
    else:
        datos = {nombre: getattr(objeto, nombre) for nombre, *_ in definiciones}
    campos = [dict(nombre=nombre, etiqueta=etiqueta, entrada=entrada, requerido=requerido,
                   maximo=maximo, valor=datos[nombre], errores=errores.get(nombre, []))
              for nombre, etiqueta, entrada, requerido, maximo in definiciones]
    return render(request, 'bodega/catalogo_form.html', {
        'titulo': titulo, 'tipo': tipo, 'objeto': objeto, 'campos': campos,
        'errores_generales': errores.get('__all__', []),
        'es_nuevo': pk is None,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def catalogo_crear(request, tipo):
    return _formulario(request, tipo)


@login_required
@require_http_methods(['GET', 'POST'])
def catalogo_editar(request, tipo, pk):
    return _formulario(request, tipo, pk)


@login_required
@require_http_methods(['GET', 'POST'])
def catalogo_eliminar(request, tipo, pk):
    modelo, titulo, _ = _autorizar(request, tipo, 'delete')
    objeto = get_object_or_404(modelo, pk=pk)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                objeto.delete()
        except ProtectedError:
            messages.error(request, 'El registro está en uso y no puede eliminarse. Puedes desactivarlo si tiene esa opción.')
        else:
            messages.success(request, 'Registro eliminado correctamente.')
            return redirect('bodega:catalogo_lista', tipo=tipo)
    return render(request, 'bodega/catalogo_eliminar.html', {
        'titulo': titulo, 'tipo': tipo, 'objeto': objeto,
    })
