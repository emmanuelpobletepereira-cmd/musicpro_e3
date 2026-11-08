"""Panel y fichas de consulta inspirados en el recorrido del módulo docente."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .decorators import permiso_requerido
from .models import Producto, Solicitud, Sucursal


@login_required
@permiso_requerido('bodega.view_producto')
@require_GET
def panel(request):
    metricas = Producto.objects.aggregate(
        total_productos=Count('pk'), total_unidades=Sum('cantidad', default=0),
    )
    puede_ver_sucursales = request.user.has_perm('bodega.view_sucursal')
    puede_ver_solicitudes = request.user.has_perm('bodega.view_solicitud')
    puede_ver_ultimas_solicitudes = puede_ver_sucursales and puede_ver_solicitudes
    metricas['sucursales_activas'] = (
        Sucursal.objects.filter(activa=True).count() if puede_ver_sucursales else None
    )
    metricas['solicitudes_pendientes'] = (
        Solicitud.objects.filter(estado='PENDIENTE').count() if puede_ver_solicitudes else None
    )
    ultimas_solicitudes = []
    if puede_ver_ultimas_solicitudes:
        ultimas_solicitudes = list(
            Solicitud.objects.select_related('sucursal').order_by('-fecha', '-pk')[:10]
        )
    return render(request, 'bodega/panel.html', {
        'metricas': metricas, 'puede_ver_sucursales': puede_ver_sucursales,
        'puede_ver_solicitudes': puede_ver_solicitudes,
        'puede_ver_ultimas_solicitudes': puede_ver_ultimas_solicitudes,
        'ultimas_solicitudes': ultimas_solicitudes,
    })


@login_required
@permiso_requerido('bodega.view_producto')
@require_GET
def producto_detalle(request, pk):
    producto = get_object_or_404(
        Producto.objects.select_related('categoria', 'marca', 'proveedor'), pk=pk,
    )
    puede_ver_movimientos = request.user.has_perm('bodega.view_movimiento')
    puede_ver_solicitudes_relacionadas = request.user.has_perms((
        'bodega.view_solicitud', 'bodega.view_detallesolicitud', 'bodega.view_sucursal',
    ))
    movimientos = []
    if puede_ver_movimientos:
        movimientos = list(producto.movimiento_set.order_by('-fecha', '-pk')[:10])
    solicitudes_relacionadas = []
    if puede_ver_solicitudes_relacionadas:
        solicitudes_relacionadas = list(
            producto.detalles_solicitud.select_related('solicitud__sucursal')
            .order_by('-solicitud__fecha', '-pk')[:10]
        )
    return render(request, 'bodega/producto_detalle.html', {
        'producto': producto, 'puede_ver_movimientos': puede_ver_movimientos,
        'puede_ver_solicitudes_relacionadas': puede_ver_solicitudes_relacionadas,
        'movimientos': movimientos, 'solicitudes_relacionadas': solicitudes_relacionadas,
    })
