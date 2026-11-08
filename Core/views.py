import re

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .decorators import permiso_requerido
from .models import Categoria, Marca, Producto, Proveedor
from .services_bodega import registrar_movimiento


@sensitive_post_parameters('password')
@never_cache
@require_http_methods(['GET', 'POST'])
def iniciar_sesion(request):
    destino = request.POST.get('next', '') if request.method == 'POST' else request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        destino = reverse('bodega:inicio')
    if request.user.is_authenticated:
        return redirect(destino)
    error = ''
    username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        usuario = authenticate(request, username=username, password=password)
        if usuario is not None:
            login(request, usuario)
            messages.success(request, 'Sesión iniciada correctamente.')
            return redirect(destino)
        error = 'Usuario o contraseña incorrectos.'
    return render(request, 'bodega/login.html', {
        'error': error, 'username': username, 'next': destino,
    })


@login_required
@require_POST
def cerrar_sesion(request):
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('bodega:login')


def _filtrar_productos(request):
    """La tabla y la demostración QUERY comparten exactamente los filtros."""
    filtros = {
        'q': request.GET.get('q', '').strip()[:120],
        'categoria': request.GET.get('categoria', '').strip(),
        'estado': request.GET.get('estado', '').strip(),
        'critico': '1' if request.GET.get('critico') == '1' else '',
    }
    consulta = Producto.objects.select_related('categoria', 'marca', 'proveedor')
    if filtros['q']:
        consulta = consulta.filter(
            Q(codigo__icontains=filtros['q']) | Q(nombre__icontains=filtros['q'])
        )
    if filtros['categoria']:
        if re.fullmatch(r'[0-9]{1,18}', filtros['categoria']):
            consulta = consulta.filter(categoria_id=int(filtros['categoria']))
        else:
            messages.error(request, 'La categoría del filtro no es válida.')
            consulta = consulta.filter(pk=0)
    if filtros['estado']:
        if filtros['estado'] in dict(Producto.ESTADOS):
            consulta = consulta.filter(estado=filtros['estado'])
        else:
            messages.error(request, 'El estado del filtro no es válido.')
            consulta = consulta.filter(pk=0)
    if filtros['critico']:
        consulta = consulta.filter(cantidad__lt=F('stock_minimo'))
    return consulta.order_by('codigo', 'pk'), filtros


@login_required
@permiso_requerido('bodega.view_producto')
@require_http_methods(['GET'])
def productos(request):
    consulta, filtros = _filtrar_productos(request)
    pagina = Paginator(consulta, 20).get_page(request.GET.get('page'))
    return render(request, 'bodega/producto_lista.html', {
        'pagina': pagina, 'filtros': filtros,
        'categorias': Categoria.objects.order_by('nombre'), 'estados': Producto.ESTADOS,
    })


def _formulario_producto(request, producto=None):
    """Lee solo campos autorizados de request.POST; no utiliza formularios Django."""
    es_nuevo = producto is None
    producto = producto or Producto()
    campos = ('codigo', 'nombre', 'categoria', 'marca', 'proveedor', 'ubicacion', 'cantidad',
              'stock_minimo', 'estado')
    errores = {}
    if request.method == 'POST':
        datos = {campo: request.POST.get(campo, '').strip() for campo in campos}
        for campo in ('codigo', 'nombre', 'ubicacion', 'estado'):
            setattr(producto, campo, datos[campo])
        for campo in ('cantidad', 'stock_minimo'):
            valor = datos[campo]
            if not re.fullmatch(r'[0-9]{1,10}', valor) or int(valor) > 2147483647:
                errores[campo] = ['Ingresa un entero entre 0 y 2147483647.']
            else:
                setattr(producto, campo, int(valor))
        for campo in ('categoria', 'marca', 'proveedor'):
            valor = datos[campo]
            if not valor and campo == 'marca':
                producto.marca_id = None
            elif re.fullmatch(r'[0-9]{1,18}', valor) and int(valor) > 0:
                setattr(producto, f'{campo}_id', int(valor))
            else:
                errores[campo] = ['Selecciona una referencia válida.']
        try:
            # Valida tipos, longitudes, FK, código único y restricciones del modelo.
            producto.full_clean(exclude=set(errores))
        except ValidationError as exc:
            errores.update(exc.message_dict)
        if 'proveedor' not in errores and not Proveedor.objects.filter(
            pk=producto.proveedor_id, activo=True
        ).exists():
            errores['proveedor'] = ['Selecciona un proveedor activo.']
        if not errores:
            try:
                # La ficha y el movimiento se confirman juntos. Nunca se pierde una
                # entrada/salida concurrente por guardar una instancia desactualizada.
                with transaction.atomic():
                    objetivo = producto.cantidad
                    if es_nuevo:
                        producto.cantidad = 0
                        producto.save()
                        if objetivo:
                            if producto.estado != 'ACTIVO':
                                raise ValidationError('Para registrar stock inicial el producto debe estar activo.')
                            registrar_movimiento(producto_id=producto.pk, tipo='INGRESO',
                                                 cantidad=objetivo, motivo='Stock inicial desde ficha de producto')
                    else:
                        vigente = get_object_or_404(Producto.objects.select_for_update(), pk=producto.pk)
                        original = request.POST.get('cantidad_original')
                        if (objetivo != vigente.cantidad or original is not None) and original != str(vigente.cantidad):
                            raise ValidationError('El stock cambió desde que abriste la ficha. Recarga la página y revisa las existencias.')
                        diferencia = objetivo - vigente.cantidad
                        if diferencia:
                            registrar_movimiento(producto_id=vigente.pk,
                                                 tipo='INGRESO' if diferencia > 0 else 'SALIDA',
                                                 cantidad=abs(diferencia), motivo='Ajuste desde ficha de producto')
                        # El servicio actualiza el stock con F(); el resto de campos
                        # se guarda sin sobrescribir esa columna.
                        producto.save(update_fields=[campo if campo not in ('categoria', 'marca', 'proveedor')
                                                     else f'{campo}_id' for campo in campos if campo != 'cantidad'])
            except ValidationError as exc:
                errores['__all__'] = exc.messages
            except IntegrityError:
                errores['__all__'] = ['No se pudo guardar. Revisa el código y las referencias; los datos pudieron cambiar.']
            else:
                messages.success(request, 'Producto creado correctamente.' if es_nuevo else 'Producto actualizado correctamente.')
                return redirect('bodega:producto_detalle', pk=producto.pk)
        messages.error(request, 'No se guardaron los cambios. Revisa los campos indicados.')
    else:
        datos = {campo: getattr(producto, f'{campo}_id' if campo in ('categoria', 'marca', 'proveedor') else campo)
                 for campo in campos}
    return render(request, 'bodega/producto_form.html', {
        'producto': None if es_nuevo else producto,
        'cantidad_original': request.POST.get('cantidad_original', '') if request.method == 'POST' else str(producto.cantidad),
        'datos': datos, 'errores': errores,
        'titulo': 'Crear producto' if es_nuevo else 'Editar producto',
        'categorias': Categoria.objects.order_by('nombre'),
        'marcas': Marca.objects.order_by('nombre'), 'proveedores': Proveedor.objects.order_by('nombre'),
        'estados': Producto.ESTADOS,
    })


@login_required
@permiso_requerido('bodega.view_producto', 'bodega.add_producto')
@require_http_methods(['GET', 'POST'])
def producto_crear(request):
    return _formulario_producto(request)


@login_required
@permiso_requerido('bodega.view_producto', 'bodega.change_producto')
@require_http_methods(['GET', 'POST'])
def producto_editar(request, pk):
    return _formulario_producto(request, get_object_or_404(Producto, pk=pk))


@login_required
@permiso_requerido('bodega.view_producto', 'bodega.delete_producto')
@require_http_methods(['GET', 'POST'])
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                producto.delete()
        except ProtectedError:
            messages.error(request, 'No se puede eliminar: el producto tiene movimientos o detalles de compras/ventas asociados.')
        else:
            messages.success(request, 'Producto eliminado correctamente.')
            return redirect('bodega:productos')
    return render(request, 'bodega/producto_eliminar.html', {'producto': producto})


@login_required
@permiso_requerido('bodega.view_producto')
@require_http_methods(['GET'])
def consultas(request):
    return redirect('bodega:panel_consultas')
