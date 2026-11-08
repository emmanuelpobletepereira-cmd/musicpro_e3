"""Reportes operativos de Bodega, expresados exclusivamente con el ORM.

Las colecciones permanecen como QuerySet para poder paginarlas antes de leerlas.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import (
    Avg, BigIntegerField, Count, DecimalField, Exists, F, OuterRef, Q, Sum, Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    Categoria, DetalleSolicitud, Movimiento, Producto, Proveedor, Solicitud,
    Sucursal,
)


REPORTES = {
    1: 'Todos los productos registrados',
    2: 'Productos de una categoría seleccionada',
    3: 'Productos con stock por debajo del mínimo',
    5: 'Cantidad de productos por categoría',
    6: 'Productos de un proveedor seleccionado',
    7: 'Solicitudes de una sucursal seleccionada',
    8: 'Productos y cantidades de una solicitud',
    9: 'Cantidad de solicitudes por estado',
    10: 'Solicitudes en un rango de fechas',
    11: 'Las cinco sucursales con más unidades solicitadas',
    12: 'Productos más solicitados por las sucursales',
    13: 'Proveedor con más productos diferentes',
    15: 'Productos nunca solicitados',
    16: 'Unidades que salieron durante el último mes',
    17: 'Sucursales con solicitudes pendientes',
    19: 'Promedio de unidades solicitadas por solicitud',
    20: 'Cinco productos más solicitados en un período',
}

PREGUNTAS = {
    1: '¿Cuáles son todos los productos registrados en la bodega?',
    2: '¿Qué productos pertenecen a una categoría seleccionada?',
    3: '¿Cuáles son los productos cuyo stock está por debajo del mínimo establecido?',
    5: '¿Cuántos productos existen registrados por categoría?',
    6: '¿Qué productos suministra un proveedor seleccionado?',
    7: '¿Cuáles son las solicitudes realizadas por una sucursal específica?',
    8: '¿Qué productos y cantidades contiene una solicitud seleccionada?',
    9: '¿Cuántas solicitudes están pendientes, aprobadas, rechazadas o despachadas?',
    10: '¿Cuáles son las solicitudes realizadas durante un rango de fechas?',
    11: '¿Cuáles son las cinco sucursales que han solicitado más unidades?',
    12: '¿Cuáles son los productos más solicitados por las sucursales?',
    13: '¿Qué proveedor suministra más productos diferentes?',
    15: '¿Qué productos nunca han sido solicitados por una sucursal?',
    16: '¿Cuántas unidades de cada producto salieron durante el último mes?',
    17: '¿Qué sucursales tienen solicitudes pendientes de atención?',
    19: '¿Cuál es el promedio de unidades solicitadas por solicitud?',
    20: '¿Cuáles son los cinco productos más solicitados durante un período?',
}

NIVELES = (
    ('Básico', (1, 2, 3, 5)), ('Intermedio', range(6, 13)),
    ('Avanzado', (13, 15, 16, 17)), ('Análisis', (19, 20)),
)

# Fragmentos para estudiar el código fuera de la interfaz.
ORM_BREVES = {
    1: 'Producto.objects.order_by("codigo", "pk")',
    2: 'Producto.objects.filter(categoria_id=categoria)',
    3: 'Producto.objects.filter(cantidad__lt=F("stock_minimo"))',
    5: 'Categoria.objects.annotate(total_productos=Count("producto"))',
    6: 'Producto.objects.filter(proveedor_id=proveedor)',
    7: 'Solicitud.objects.filter(sucursal_id=sucursal)',
    8: 'DetalleSolicitud.objects.filter(solicitud_id=solicitud)',
    9: 'Solicitud.objects.values("estado").annotate(total=Count("pk"))',
    10: 'Solicitud.objects.filter(fecha__gte=inicio, fecha__lt=fin_exclusivo)',
    11: 'Sucursal.objects.annotate(total=Sum("solicitudes__detalles__cantidad_solicitada")).order_by("-total")[:5]',
    12: 'Producto.objects.annotate(total=Sum("detalles_solicitud__cantidad_solicitada")).order_by("-total")',
    13: 'Proveedor.objects.annotate(total=Count("productos", distinct=True)).order_by("-total")[:1]',
    15: 'Producto.objects.filter(~Exists(DetalleSolicitud.objects.filter(producto_id=OuterRef("pk"))))',
    16: 'Movimiento.objects.filter(tipo="SALIDA", fecha__gte=inicio, fecha__lt=fin_exclusivo).values("producto__codigo").annotate(total=Sum("cantidad"))',
    17: 'Sucursal.objects.filter(solicitudes__estado="PENDIENTE").distinct()',
    19: 'Solicitud.objects.annotate(unidades=Sum("detalles__cantidad_solicitada")).aggregate(promedio=Avg("unidades"))',
    20: 'Producto.objects.filter(detalles_solicitud__solicitud__fecha__gte=inicio, detalles_solicitud__solicitud__fecha__lt=fin_exclusivo).annotate(total=Sum("detalles_solicitud__cantidad_solicitada")).order_by("-total")[:5]',
}

FILTROS_REQUERIDOS = {
    2: ('categoria',), 6: ('proveedor',), 7: ('sucursal',),
    8: ('solicitud',), 10: ('desde', 'hasta'), 20: ('desde', 'hasta'),
}

# Además de view_producto (decorador de la vista), se comprueba la autorización
# sobre las entidades que intervienen en cada consulta.
PERMISOS_REPORTE = {
    1: ('categoria', 'proveedor'),
    2: ('categoria', 'proveedor'),
    3: ('categoria', 'proveedor'),
    5: ('categoria',),
    6: ('categoria', 'proveedor'),
    7: ('solicitud', 'sucursal'),
    8: ('solicitud', 'detallesolicitud'),
    9: ('solicitud',),
    10: ('solicitud', 'sucursal'),
    11: ('sucursal', 'solicitud', 'detallesolicitud'),
    12: ('solicitud', 'detallesolicitud'),
    13: ('proveedor',),
    15: ('solicitud', 'detallesolicitud'),
    16: ('movimiento',),
    17: ('sucursal', 'solicitud'),
    19: ('solicitud', 'detallesolicitud'),
    20: ('solicitud', 'detallesolicitud'),
}

COLUMNAS_PRODUCTO = [
    ('codigo', 'Código'), ('nombre', 'Producto'),
    ('categoria__nombre', 'Categoría'), ('proveedor__nombre', 'Proveedor'),
    ('cantidad', 'Stock'), ('stock_minimo', 'Mínimo'),
]
COLUMNAS_SOLICITUD = [
    ('id', 'Solicitud'), ('sucursal__codigo', 'Código sucursal'),
    ('sucursal__nombre', 'Sucursal'), ('fecha', 'Fecha'), ('estado', 'Estado'),
]


def ultimo_mes_calendario():
    """Mes calendario anterior, según la fecha de Chile continental."""
    hoy = timezone.localdate(timezone=ZoneInfo('America/Santiago'))
    inicio_mes_actual = hoy.replace(day=1)
    ultimo_dia = inicio_mes_actual - timedelta(days=1)
    return ultimo_dia.replace(day=1), ultimo_dia


def limites_fechas(desde, hasta):
    """Instantes del período local inclusivo, sin conversiones SQL de zona.

    El límite final exclusivo corresponde al comienzo del día siguiente. Así se
    incluyen todas las horas del último día y los cambios de horario de Chile.
    La vista valida los límites antes de llamar a esta función.
    """
    chile = ZoneInfo('America/Santiago')
    return (
        datetime.combine(desde, time.min, tzinfo=chile),
        datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=chile),
    )


def _unidades(expresion):
    return Coalesce(Sum(expresion), Value(0), output_field=BigIntegerField())


def metricas_inventario():
    """Tres indicadores de productos calculados en una sola consulta ORM."""
    return Producto.objects.aggregate(
        total_productos=Count('pk'),
        stock_critico=Count('pk', filter=Q(cantidad__lt=F('stock_minimo'))),
        total_unidades=Sum('cantidad', default=0),
    )


def _resultado(numero, columnas, filas, orm, nota=''):
    return {'numero': numero, 'titulo': REPORTES[numero],
            'pregunta': PREGUNTAS[numero], 'columnas': columnas,
            'filas': filas, 'orm': orm, 'nota': nota}


def todos_los_productos(filtros):
    """Reporte 1: todos los productos."""
    columnas = COLUMNAS_PRODUCTO
    productos = Producto.objects.order_by('codigo', 'pk')
    campos_producto = [campo for campo, _ in COLUMNAS_PRODUCTO]
    filas = productos.values(*campos_producto)
    orm = 'Producto.objects.order_by("codigo", "pk").values(...)'
    return _resultado(1, columnas, filas, orm)


def productos_por_categoria(filtros):
    """Reporte 2: productos por categoria."""
    columnas = COLUMNAS_PRODUCTO
    productos = Producto.objects.order_by('codigo', 'pk')
    campos_producto = [campo for campo, _ in COLUMNAS_PRODUCTO]
    filas = productos.filter(categoria_id=filtros['categoria']).values(*campos_producto)
    orm = 'Producto.objects.filter(categoria_id=categoria).order_by("codigo", "pk").values(...)'
    return _resultado(2, columnas, filas, orm)


def productos_bajo_minimo(filtros):
    """Reporte 3: productos bajo minimo."""
    columnas = COLUMNAS_PRODUCTO
    productos = Producto.objects.order_by('codigo', 'pk')
    campos_producto = [campo for campo, _ in COLUMNAS_PRODUCTO]
    filas = productos.filter(cantidad__lt=F('stock_minimo')).values(*campos_producto)
    orm = 'Producto.objects.filter(cantidad__lt=F("stock_minimo")).order_by("codigo", "pk").values(...)'
    nota = 'Se compara estrictamente stock < mínimo. Un producto exactamente en el mínimo no aparece.'
    return _resultado(3, columnas, filas, orm, nota)


def cantidad_por_categoria(filtros):
    """Reporte 5: cantidad por categoria."""
    columnas = [('nombre', 'Categoría'), ('total_productos', 'Productos registrados')]
    filas = Categoria.objects.annotate(total_productos=Count('producto')).order_by('nombre', 'pk').values('nombre', 'total_productos')
    orm = 'Categoria.objects.annotate(total_productos=Count("producto")).order_by("nombre", "pk").values("nombre", "total_productos")'
    nota = 'Incluye las categorías sin productos, con conteo cero.'
    return _resultado(5, columnas, filas, orm, nota)


def productos_por_proveedor(filtros):
    """Reporte 6: productos por proveedor."""
    columnas = COLUMNAS_PRODUCTO
    productos = Producto.objects.order_by('codigo', 'pk')
    campos_producto = [campo for campo, _ in COLUMNAS_PRODUCTO]
    filas = productos.filter(proveedor_id=filtros['proveedor']).values(*campos_producto)
    orm = 'Producto.objects.filter(proveedor_id=proveedor).order_by("codigo", "pk").values(...)'
    nota = 'Utiliza el proveedor directo de cada producto; los productos antiguos sin proveedor deben completarse desde su ficha.'
    return _resultado(6, columnas, filas, orm, nota)


def solicitudes_por_sucursal(filtros):
    """Reporte 7: solicitudes por sucursal."""
    campos_solicitud = [campo for campo, _ in COLUMNAS_SOLICITUD]
    columnas = COLUMNAS_SOLICITUD
    filas = Solicitud.objects.filter(sucursal_id=filtros['sucursal']).order_by('-fecha', '-pk').values(*campos_solicitud)
    orm = 'Solicitud.objects.filter(sucursal_id=sucursal).order_by("-fecha", "-pk").values(...)'
    return _resultado(7, columnas, filas, orm)


def detalle_de_solicitud(filtros):
    """Reporte 8: detalle de solicitud."""
    columnas = [('producto__codigo', 'Código'), ('producto__nombre', 'Producto'), ('cantidad_solicitada', 'Solicitado'), ('cantidad_aprobada', 'Aprobado'), ('cantidad_despachada', 'Despachado')]
    filas = DetalleSolicitud.objects.filter(solicitud_id=filtros['solicitud']).order_by('producto__codigo', 'pk').values(*[campo for campo, _ in columnas])
    orm = 'DetalleSolicitud.objects.filter(solicitud_id=solicitud).order_by("producto__codigo", "pk").values(...)'
    return _resultado(8, columnas, filas, orm)


def cantidad_por_estado(filtros):
    """Reporte 9: cantidad por estado."""
    columnas = [('estado', 'Estado'), ('total_solicitudes', 'Solicitudes')]
    agrupadas = Solicitud.objects.values('estado').annotate(total_solicitudes=Count('pk')).order_by('estado')
    conteos = {fila['estado']: fila['total_solicitudes'] for fila in agrupadas}
    filas = [{'estado': etiqueta, 'total_solicitudes': conteos.get(estado, 0)} for estado, etiqueta in Solicitud.ESTADOS]
    orm = 'Solicitud.objects.values("estado").annotate(total_solicitudes=Count("pk")).order_by("estado")'
    nota = 'Los cuatro estados se presentan siempre; los que no tienen solicitudes muestran cero.'
    return _resultado(9, columnas, filas, orm, nota)


def solicitudes_en_periodo(filtros):
    """Reporte 10: solicitudes en periodo."""
    campos_solicitud = [campo for campo, _ in COLUMNAS_SOLICITUD]
    columnas = COLUMNAS_SOLICITUD
    inicio, fin_exclusivo = limites_fechas(filtros['desde'], filtros['hasta'])
    filas = Solicitud.objects.filter(fecha__gte=inicio, fecha__lt=fin_exclusivo).order_by('-fecha', '-pk').values(*campos_solicitud)
    orm = 'inicio, fin_exclusivo = limites_fechas(desde, hasta)\nSolicitud.objects.filter(fecha__gte=inicio, fecha__lt=fin_exclusivo).order_by("-fecha", "-pk").values(...)'
    nota = 'El período incluye el día inicial y el final en America/Santiago: desde las 00:00 del inicio hasta antes de las 00:00 del día posterior al final.'
    return _resultado(10, columnas, filas, orm, nota)


def sucursales_mas_solicitantes(filtros):
    """Reporte 11: sucursales mas solicitantes."""
    columnas = [('codigo', 'Código'), ('nombre', 'Sucursal'), ('total_unidades', 'Unidades solicitadas')]
    filas = Sucursal.objects.annotate(total_unidades=_unidades('solicitudes__detalles__cantidad_solicitada')).order_by('-total_unidades', 'codigo', 'pk').values(*[campo for campo, _ in columnas])[:5]
    orm = 'Sucursal.objects.annotate(total_unidades=Coalesce(Sum("solicitudes__detalles__cantidad_solicitada"), 0)).order_by("-total_unidades", "codigo", "pk").values(...)[:5]'
    nota = 'Suma cantidades solicitadas de todos los estados; no cuenta solamente el número de solicitudes.'
    return _resultado(11, columnas, filas, orm, nota)


def productos_mas_solicitados(filtros):
    """Reporte 12: productos mas solicitados."""
    columnas = [('codigo', 'Código'), ('nombre', 'Producto'), ('total_unidades', 'Unidades solicitadas')]
    filas = Producto.objects.annotate(total_unidades=_unidades('detalles_solicitud__cantidad_solicitada')).filter(total_unidades__gt=0).order_by('-total_unidades', 'codigo', 'pk').values(*[campo for campo, _ in columnas])
    orm = 'Producto.objects.annotate(total_unidades=Coalesce(Sum("detalles_solicitud__cantidad_solicitada"), 0)).filter(total_unidades__gt=0).order_by("-total_unidades", "codigo", "pk").values(...)'
    return _resultado(12, columnas, filas, orm)


def proveedor_con_mas_productos(filtros):
    """Reporte 13: proveedor con mas productos."""
    columnas = [('nombre', 'Proveedor'), ('total_productos', 'Productos diferentes')]
    filas = Proveedor.objects.annotate(total_productos=Count('productos', distinct=True)).order_by('-total_productos', 'nombre', 'pk').values('nombre', 'total_productos')[:1]
    orm = 'Proveedor.objects.annotate(total_productos=Count("productos", distinct=True)).order_by("-total_productos", "nombre", "pk").values("nombre", "total_productos")[:1]'
    nota = 'Cuenta productos diferentes asociados al proveedor, sin multiplicarlos por compras o detalles. En un empate se muestra el primero por nombre e identificador.'
    return _resultado(13, columnas, filas, orm, nota)


def productos_nunca_solicitados(filtros):
    """Reporte 15: productos nunca solicitados."""
    columnas = COLUMNAS_PRODUCTO
    productos = Producto.objects.order_by('codigo', 'pk')
    campos_producto = [campo for campo, _ in COLUMNAS_PRODUCTO]
    subconsulta = DetalleSolicitud.objects.filter(producto_id=OuterRef('pk'))
    filas = productos.filter(~Exists(subconsulta)).values(*campos_producto)
    orm = 'Producto.objects.filter(~Exists(DetalleSolicitud.objects.filter(producto_id=OuterRef("pk")))).order_by("codigo", "pk").values(...)'
    nota = 'NOT EXISTS comprueba que no exista ningún detalle de solicitud para el producto, cualquiera sea el estado de la solicitud.'
    return _resultado(15, columnas, filas, orm, nota)


def salidas_ultimo_mes(filtros):
    """Reporte 16: salidas ultimo mes."""
    desde, hasta = ultimo_mes_calendario()
    inicio, fin_exclusivo = limites_fechas(desde, hasta)
    columnas = [('producto__codigo', 'Código'), ('producto__nombre', 'Producto'), ('total_unidades', 'Unidades de salida')]
    filas = Movimiento.objects.filter(tipo='SALIDA', fecha__gte=inicio, fecha__lt=fin_exclusivo).values('producto__codigo', 'producto__nombre').annotate(total_unidades=Sum('cantidad')).order_by('-total_unidades', 'producto__codigo')
    orm = 'inicio, fin_exclusivo = limites_fechas(inicio_mes_anterior, fin_mes_anterior)\nMovimiento.objects.filter(tipo="SALIDA", fecha__gte=inicio, fecha__lt=fin_exclusivo).values("producto__codigo", "producto__nombre").annotate(total_unidades=Sum("cantidad")).order_by("-total_unidades", "producto__codigo")'
    nota = f'Último mes calendario: {desde:%d-%m-%Y} a {hasta:%d-%m-%Y}, ambos incluidos, en America/Santiago. Cuenta una vez cada movimiento SALIDA, incluidos los registros históricos; no vuelve a restar stock.'
    return _resultado(16, columnas, filas, orm, nota)


def sucursales_con_pendientes(filtros):
    """Reporte 17: sucursales con pendientes."""
    columnas = [('codigo', 'Código'), ('nombre', 'Sucursal')]
    filas = Sucursal.objects.filter(solicitudes__estado='PENDIENTE').order_by('codigo', 'pk').values('codigo', 'nombre').distinct()
    orm = 'Sucursal.objects.filter(solicitudes__estado="PENDIENTE").order_by("codigo", "pk").values("codigo", "nombre").distinct()'
    nota = 'DISTINCT evita repetir una sucursal aunque tenga varias solicitudes pendientes.'
    return _resultado(17, columnas, filas, orm, nota)


def promedio_por_solicitud(filtros):
    """Reporte 19: promedio por solicitud."""
    columnas = [('promedio_unidades', 'Promedio de unidades por solicitud')]
    resumen = Solicitud.objects.annotate(total_unidades=_unidades('detalles__cantidad_solicitada'))
    filas = [resumen.aggregate(promedio_unidades=Coalesce(Avg('total_unidades', output_field=DecimalField(max_digits=24, decimal_places=4)), Value(Decimal('0.0000')), output_field=DecimalField(max_digits=24, decimal_places=4)))]
    orm = 'Solicitud.objects.annotate(total_unidades=Coalesce(Sum("detalles__cantidad_solicitada"), 0)).aggregate(promedio_unidades=Coalesce(Avg("total_unidades"), Decimal("0.0000")))'
    nota = 'Primero suma las unidades de cada solicitud y después promedia esos totales. Una solicitud sin detalles aporta cero; si no hay solicitudes, el resultado es cero.'
    return _resultado(19, columnas, filas, orm, nota)


def productos_mas_solicitados_en_periodo(filtros):
    """Reporte 20: productos mas solicitados en periodo."""
    inicio, fin_exclusivo = limites_fechas(filtros['desde'], filtros['hasta'])
    columnas = [('codigo', 'Código'), ('nombre', 'Producto'), ('total_unidades', 'Unidades solicitadas')]
    filas = Producto.objects.filter(detalles_solicitud__solicitud__fecha__gte=inicio, detalles_solicitud__solicitud__fecha__lt=fin_exclusivo).annotate(total_unidades=Sum('detalles_solicitud__cantidad_solicitada')).order_by('-total_unidades', 'codigo', 'pk').values(*[campo for campo, _ in columnas])[:5]
    orm = 'inicio, fin_exclusivo = limites_fechas(desde, hasta)\nProducto.objects.filter(detalles_solicitud__solicitud__fecha__gte=inicio, detalles_solicitud__solicitud__fecha__lt=fin_exclusivo).annotate(total_unidades=Sum("detalles_solicitud__cantidad_solicitada")).order_by("-total_unidades", "codigo", "pk").values(...)[:5]'
    nota = 'Suma unidades solicitadas de todos los estados. Incluye ambas fechas en America/Santiago mediante límites de instantes: inicio inclusivo y comienzo del día posterior exclusivo.'
    return _resultado(20, columnas, filas, orm, nota)


CONSTRUCTORES = {
    1: todos_los_productos,
    2: productos_por_categoria,
    3: productos_bajo_minimo,
    5: cantidad_por_categoria,
    6: productos_por_proveedor,
    7: solicitudes_por_sucursal,
    8: detalle_de_solicitud,
    9: cantidad_por_estado,
    10: solicitudes_en_periodo,
    11: sucursales_mas_solicitantes,
    12: productos_mas_solicitados,
    13: proveedor_con_mas_productos,
    15: productos_nunca_solicitados,
    16: salidas_ultimo_mes,
    17: sucursales_con_pendientes,
    19: promedio_por_solicitud,
    20: productos_mas_solicitados_en_periodo,
}


def construye_reporte(numero, filtros):
    """Selecciona una consulta ORM con filtros validados por la vista."""
    if numero not in CONSTRUCTORES:
        raise ValueError('El reporte solicitado no está disponible.')
    if any(not filtros.get(campo) for campo in FILTROS_REQUERIDOS.get(numero, ())):
        raise ValueError('Faltan los filtros obligatorios del reporte.')
    return CONSTRUCTORES[numero](filtros)
