"""Reglas de stock y solicitudes compartidas por las vistas propias de E3.

Las transacciones agrupan documento, detalles, stock y trazabilidad. En el servidor,
select_for_update bloquea las filas; el descuento condicional evita stock negativo
también al utilizar SQLite para las pruebas locales.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .models import DetalleSolicitud, Movimiento, Producto, Solicitud, Sucursal

MAX_STOCK = 2147483647


def _solicitud_bloqueada(solicitud_id):
    try:
        return Solicitud.objects.select_for_update().get(pk=solicitud_id)
    except Solicitud.DoesNotExist as exc:
        raise ValidationError('La solicitud ya no existe. Recarga la página.') from exc


def _referencia(valor):
    texto = str(valor)
    if not texto.isascii() or not texto.isdigit() or not 1 <= len(texto) <= 18 or int(texto) < 1:
        raise ValidationError('Selecciona una referencia válida.')
    return int(texto)


def _entero(valor, minimo=1):
    if isinstance(valor, bool):
        raise ValidationError('La cantidad debe ser un número entero.')
    texto = str(valor)
    if not texto.isascii() or not texto.isdigit() or len(texto) > 10:
        raise ValidationError('La cantidad debe ser un número entero válido.')
    numero = int(texto)
    if not minimo <= numero <= MAX_STOCK:
        raise ValidationError(f'La cantidad debe estar entre {minimo} y {MAX_STOCK}.')
    return numero


@transaction.atomic
def registrar_movimiento(*, producto_id, tipo, cantidad, motivo, solicitud=None):
    producto_id = _referencia(producto_id)
    cantidad = _entero(cantidad)
    if tipo not in dict(Movimiento.TIPOS):
        raise ValidationError('Selecciona un tipo de movimiento válido.')
    try:
        producto = Producto.objects.select_for_update().get(pk=producto_id)
    except (Producto.DoesNotExist, ValueError, TypeError):
        raise ValidationError('El producto seleccionado no existe.')
    if producto.estado != 'ACTIVO':
        raise ValidationError('Solo se pueden registrar movimientos de productos activos.')
    movimiento = Movimiento(
        producto=producto, tipo=tipo, cantidad=cantidad, motivo=motivo.strip(),
        solicitud=solicitud, stock_aplicado=True,
    )
    movimiento.full_clean()
    if tipo == 'SALIDA':
        actualizados = Producto.objects.filter(pk=producto.pk, cantidad__gte=cantidad).update(
            cantidad=F('cantidad') - cantidad
        )
        if actualizados != 1:
            raise ValidationError(f'Stock insuficiente para {producto.codigo}.')
    else:
        actualizados = Producto.objects.filter(pk=producto.pk, cantidad__lte=MAX_STOCK-cantidad).update(
            cantidad=F('cantidad') + cantidad
        )
        if actualizados != 1:
            raise ValidationError('El ingreso supera el stock máximo permitido.')
    movimiento.save()
    return movimiento


@transaction.atomic
def guardar_solicitud(*, sucursal_id, observaciones, lineas, solicitud_id=None):
    """Crea o reemplaza los detalles de una solicitud que todavía esté pendiente."""
    if solicitud_id is None:
        solicitud = Solicitud()
    else:
        solicitud = _solicitud_bloqueada(solicitud_id)
        if solicitud.estado != 'PENDIENTE':
            raise ValidationError('Solo se pueden editar solicitudes pendientes.')
    sucursal_id = _referencia(sucursal_id)
    try:
        sucursal = Sucursal.objects.get(pk=sucursal_id, activa=True)
    except (Sucursal.DoesNotExist, ValueError, TypeError):
        raise ValidationError('Selecciona una sucursal activa.')
    if not lineas or len(lineas) > 100:
        raise ValidationError('Incluye entre 1 y 100 productos en la solicitud.')
    vistos = set()
    detalles = []
    for producto_id, cantidad in lineas:
        producto_id = _referencia(producto_id)
        cantidad = _entero(cantidad)
        try:
            producto = Producto.objects.get(pk=producto_id, estado='ACTIVO')
        except (Producto.DoesNotExist, ValueError, TypeError):
            raise ValidationError('Selecciona productos activos y existentes.')
        if producto.pk in vistos:
            raise ValidationError('No repitas el mismo producto en una solicitud.')
        vistos.add(producto.pk)
        detalles.append(DetalleSolicitud(producto=producto, cantidad_solicitada=cantidad))
    solicitud.sucursal = sucursal
    solicitud.observaciones = observaciones.strip()
    solicitud.full_clean()
    solicitud.save()
    solicitud.detalles.all().delete()
    for detalle in detalles:
        detalle.solicitud = solicitud
        detalle.full_clean()
        detalle.save()
    return solicitud


@transaction.atomic
def eliminar_solicitud(solicitud_id):
    solicitud = _solicitud_bloqueada(solicitud_id)
    if solicitud.estado != 'PENDIENTE':
        raise ValidationError('Solo se pueden eliminar solicitudes pendientes.')
    solicitud.detalles.all().delete()
    solicitud.delete()


@transaction.atomic
def aprobar_solicitud(solicitud_id, cantidades=None):
    solicitud = _solicitud_bloqueada(solicitud_id)
    if solicitud.estado != 'PENDIENTE':
        raise ValidationError('Solo se pueden aprobar solicitudes pendientes.')
    detalles = list(solicitud.detalles.select_for_update().order_by('producto_id'))
    if not detalles:
        raise ValidationError('La solicitud no tiene productos.')
    if cantidades is not None and set(cantidades) != {d.pk for d in detalles}:
        raise ValidationError('Las cantidades no corresponden a los detalles de la solicitud.')
    total = 0
    for detalle in detalles:
        valor = detalle.cantidad_solicitada if cantidades is None else cantidades[detalle.pk]
        detalle.cantidad_aprobada = _entero(valor, minimo=0)
        detalle.full_clean()
        detalle.save(update_fields=['cantidad_aprobada'])
        total += detalle.cantidad_aprobada
    if total == 0:
        raise ValidationError('Aprueba al menos una unidad o rechaza la solicitud.')
    solicitud.estado = 'APROBADA'
    solicitud.save(update_fields=['estado'])
    return solicitud


@transaction.atomic
def rechazar_solicitud(solicitud_id):
    solicitud = _solicitud_bloqueada(solicitud_id)
    if solicitud.estado != 'PENDIENTE':
        raise ValidationError('Solo se pueden rechazar solicitudes pendientes.')
    solicitud.estado = 'RECHAZADA'
    solicitud.save(update_fields=['estado'])
    return solicitud


@transaction.atomic
def despachar_solicitud(solicitud_id):
    solicitud = _solicitud_bloqueada(solicitud_id)
    if solicitud.estado != 'APROBADA':
        raise ValidationError('Solo se pueden despachar solicitudes aprobadas; no se repite un despacho.')
    detalles = list(solicitud.detalles.select_for_update().order_by('producto_id'))
    if not detalles or not any(d.cantidad_aprobada for d in detalles):
        raise ValidationError('La solicitud no tiene cantidades aprobadas.')
    for detalle in detalles:
        if detalle.cantidad_despachada:
            raise ValidationError('La solicitud ya tiene unidades despachadas.')
        if detalle.cantidad_aprobada:
            registrar_movimiento(
                producto_id=detalle.producto_id, tipo='SALIDA',
                cantidad=detalle.cantidad_aprobada,
                motivo=f'Despacho de solicitud {solicitud.pk}', solicitud=solicitud,
            )
            detalle.cantidad_despachada = detalle.cantidad_aprobada
            detalle.full_clean()
            detalle.save(update_fields=['cantidad_despachada'])
    solicitud.estado = 'DESPACHADA'
    solicitud.save(update_fields=['estado'])
    return solicitud
