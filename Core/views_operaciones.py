"""Solicitudes y movimientos: formularios HTML y autorización en el servidor."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .decorators import permiso_requerido
from .models import Movimiento, Producto, Solicitud, Sucursal
from .services_bodega import (
    aprobar_solicitud, despachar_solicitud, eliminar_solicitud,
    guardar_solicitud, rechazar_solicitud, registrar_movimiento,
)


def _error(request, error):
    texto = ' '.join(error.messages) if isinstance(error, ValidationError) else 'No se pudo guardar. Revisa las referencias; los datos pudieron cambiar.'
    messages.error(request, texto)
    return texto


@login_required
@permiso_requerido('bodega.view_solicitud')
@require_http_methods(['GET'])
def solicitudes(request):
    consulta = Solicitud.objects.select_related('sucursal').order_by('-fecha', '-pk')
    estado = request.GET.get('estado', '')
    if estado:
        if estado in dict(Solicitud.ESTADOS):
            consulta = consulta.filter(estado=estado)
        else:
            messages.error(request, 'El estado del filtro no es válido.')
            consulta = consulta.none()
    return render(request, 'bodega/solicitud_lista.html', {
        'pagina': Paginator(consulta, 20).get_page(request.GET.get('page')),
        'estado': estado, 'estados': Solicitud.ESTADOS,
    })


def _formulario_solicitud(request, solicitud=None):
    error = ''
    if solicitud is not None and solicitud.estado != 'PENDIENTE':
        messages.error(request, 'Solo se pueden editar solicitudes pendientes.')
        return redirect('bodega:solicitud_detalle', pk=solicitud.pk)
    if request.method == 'POST':
        datos = {'sucursal': request.POST.get('sucursal', ''),
                 'observaciones': request.POST.get('observaciones', '')}
        productos = request.POST.getlist('producto')
        cantidades = request.POST.getlist('cantidad')
        lineas = list(zip(productos, cantidades))
        try:
            if len(productos) != len(cantidades):
                raise ValidationError('Los productos y cantidades no coinciden.')
            lineas = [(producto, cantidad) for producto, cantidad in lineas if producto or cantidad]
            guardada = guardar_solicitud(
                sucursal_id=datos['sucursal'], observaciones=datos['observaciones'], lineas=lineas,
                solicitud_id=solicitud.pk if solicitud is not None else None,
            )
        except (ValidationError, IntegrityError, ProtectedError) as exc:
            error = _error(request, exc)
        else:
            messages.success(request, 'Solicitud guardada correctamente. Está pendiente de aprobación.')
            return redirect('bodega:solicitud_detalle', pk=guardada.pk)
    else:
        datos = {'sucursal': solicitud.sucursal_id if solicitud else '',
                 'observaciones': solicitud.observaciones if solicitud else ''}
        lineas = [(d.producto_id, d.cantidad_solicitada) for d in solicitud.detalles.all()] if solicitud else []
    if not lineas:
        lineas = [('', '')]
    return render(request, 'bodega/solicitud_form.html', {
        'solicitud': solicitud, 'datos': datos, 'lineas': lineas, 'error': error,
        'sucursales': Sucursal.objects.filter(activa=True).order_by('nombre'),
        'productos': Producto.objects.filter(estado='ACTIVO').order_by('codigo'),
    })


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.add_solicitud')
@require_http_methods(['GET', 'POST'])
def solicitud_crear(request):
    return _formulario_solicitud(request)


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.change_solicitud')
@require_http_methods(['GET', 'POST'])
def solicitud_editar(request, pk):
    return _formulario_solicitud(request, get_object_or_404(Solicitud, pk=pk))


@login_required
@permiso_requerido('bodega.view_solicitud')
@require_http_methods(['GET'])
def solicitud_detalle(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)
    return render(request, 'bodega/solicitud_detalle.html', {
        'solicitud': solicitud, 'detalles': solicitud.detalles.select_related('producto').order_by('pk'),
    })


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.delete_solicitud')
@require_http_methods(['GET', 'POST'])
def solicitud_eliminar(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)
    if request.method == 'POST':
        try:
            eliminar_solicitud(pk)
        except (ValidationError, IntegrityError, ProtectedError) as exc:
            _error(request, exc)
        else:
            messages.success(request, 'Solicitud eliminada correctamente.')
            return redirect('bodega:solicitudes')
    return render(request, 'bodega/solicitud_eliminar.html', {'solicitud': solicitud})


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.aprobar_solicitud')
@require_POST
def solicitud_aprobar(request, pk):
    get_object_or_404(Solicitud, pk=pk)
    try:
        ids = request.POST.getlist('detalle_id')
        valores = request.POST.getlist('cantidad_aprobada')
        if len(ids) != len(valores) or len(set(ids)) != len(ids):
            raise ValidationError('Revisa las cantidades aprobadas de cada producto.')
        cantidades = {int(k): v for k, v in zip(ids, valores)} if ids else None
        aprobar_solicitud(pk, cantidades=cantidades)
    except (ValueError, ValidationError, IntegrityError) as exc:
        _error(request, exc if not isinstance(exc, ValueError) else ValidationError('Los detalles de la solicitud no son válidos.'))
    else:
        messages.success(request, 'Solicitud aprobada. El stock se descontará al despachar.')
    return redirect('bodega:solicitud_detalle', pk=pk)


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.aprobar_solicitud')
@require_POST
def solicitud_rechazar(request, pk):
    get_object_or_404(Solicitud, pk=pk)
    try:
        rechazar_solicitud(pk)
    except (ValidationError, IntegrityError) as exc:
        _error(request, exc)
    else:
        messages.success(request, 'Solicitud rechazada. El stock se conserva.')
    return redirect('bodega:solicitud_detalle', pk=pk)


@login_required
@permiso_requerido('bodega.view_solicitud', 'bodega.despachar_solicitud')
@require_POST
def solicitud_despachar(request, pk):
    get_object_or_404(Solicitud, pk=pk)
    try:
        despachar_solicitud(pk)
    except (ValidationError, IntegrityError) as exc:
        _error(request, exc)
    else:
        messages.success(request, 'Solicitud despachada. Stock actualizado y salidas registradas.')
    return redirect('bodega:solicitud_detalle', pk=pk)


@login_required
@permiso_requerido('bodega.view_movimiento')
@require_http_methods(['GET'])
def movimientos(request):
    consulta = Movimiento.objects.select_related('producto', 'solicitud').order_by('-fecha', '-pk')
    tipo = request.GET.get('tipo', '')
    if tipo:
        consulta = consulta.filter(tipo=tipo) if tipo in dict(Movimiento.TIPOS) else consulta.none()
    return render(request, 'bodega/movimiento_lista.html', {
        'pagina': Paginator(consulta, 20).get_page(request.GET.get('page')),
        'tipo': tipo, 'tipos': Movimiento.TIPOS,
    })


@login_required
@permiso_requerido('bodega.view_movimiento', 'bodega.add_movimiento')
@require_http_methods(['GET', 'POST'])
def movimiento_crear(request):
    error = ''
    datos = {'producto': '', 'tipo': 'INGRESO', 'cantidad': '', 'motivo': ''}
    if request.method == 'POST':
        datos = {campo: request.POST.get(campo, '').strip() for campo in datos}
        try:
            registrar_movimiento(
                producto_id=datos['producto'], tipo=datos['tipo'],
                cantidad=datos['cantidad'], motivo=datos['motivo'],
            )
        except (ValidationError, IntegrityError) as exc:
            error = _error(request, exc)
        else:
            messages.success(request, 'Movimiento registrado correctamente. El stock fue actualizado.')
            return redirect('bodega:movimientos')
    return render(request, 'bodega/movimiento_form.html', {
        'datos': datos, 'error': error, 'tipos': Movimiento.TIPOS,
        'productos': Producto.objects.filter(estado='ACTIVO').order_by('codigo'),
    })
