"""Muestra pequeña y ficticia del flujo completo de Bodega para la defensa E3."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from Core.models import Categoria, Producto, Proveedor, Sucursal
from Core.services_bodega import (
    aprobar_solicitud, despachar_solicitud, guardar_solicitud,
    rechazar_solicitud, registrar_movimiento,
)


class Command(BaseCommand):
    help = 'Añade una muestra ficticia DEMO-E3 de bodega, sin modificar registros existentes.'

    def handle(self, *args, **options):
        prefijo = 'DEMO-E3-'
        centinela = 'DEMO-E3-P01'
        if Producto.objects.filter(codigo__startswith=prefijo).exists():
            if not Producto.objects.filter(codigo=centinela).exists():
                raise CommandError('Existe el prefijo DEMO-E3 pero falta el producto centinela DEMO-E3-P01. No se modificó ningún dato.')
            self.stdout.write(self.style.WARNING('La muestra DEMO-E3 ya existe. Se omite la carga completa y se conservan todos sus valores actuales.'))
            return
        try:
            with transaction.atomic():
                self._crear_muestra()
        except (ValidationError, IntegrityError) as exc:
            raise CommandError(f'No se creó la muestra; la transacción fue revertida. {exc}') from exc
        self.stdout.write(self.style.SUCCESS(
            'Muestra ficticia DEMO-E3 creada: 2 categorías, 2 proveedores, 4 productos, '
            '3 sucursales, 4 solicitudes y 6 movimientos aplicados al stock.'
        ))

    def _crear_muestra(self):
        categorias = []
        for nombre in ('DEMO-E3 · Instrumentos', 'DEMO-E3 · Audio y accesorios'):
            categoria = Categoria(nombre=nombre, descripcion='Categoría ficticia de demostración E3.')
            categoria.full_clean()
            categoria.save()
            categorias.append(categoria)
        proveedores = []
        for numero in (1, 2):
            proveedor = Proveedor(
                nombre=f'DEMO-E3 · Proveedor ficticio {numero}', rut=f'DEMO-E3-0{numero}',
                email=f'demo-proveedor{numero}@example.invalid', direccion='Dirección ficticia de demostración',
                activo=True,
            )
            proveedor.full_clean()
            proveedor.save()
            proveedores.append(proveedor)
        productos = []
        ejemplos = [
            ('Guitarra eléctrica de demostración', 20, 0, 0),
            ('Amplificador de demostración', 12, 1, 0),
            ('Cable de audio de demostración', 30, 1, 1),
            ('Pedal de efectos de demostración', 8, 0, 1),
        ]
        for numero, (nombre, stock, categoria, proveedor) in enumerate(ejemplos, 1):
            producto = Producto(
                codigo=f'DEMO-E3-P0{numero}', nombre=nombre,
                categoria=categorias[categoria], proveedor=proveedores[proveedor],
                ubicacion=f'DEMO-E3 · Estante {numero}', cantidad=0, stock_minimo=5,
                estado='ACTIVO',
            )
            producto.full_clean()
            producto.save()
            registrar_movimiento(
                producto_id=producto.pk, tipo='INGRESO', cantidad=stock,
                motivo='DEMO-E3 · Ingreso inicial ficticio',
            )
            productos.append(producto)
        sucursales = []
        for numero, nombre in enumerate(('Centro', 'Norte', 'Sur'), 1):
            sucursal = Sucursal(
                codigo=f'DEMO-E3-S0{numero}', nombre=f'DEMO-E3 · Sucursal ficticia {nombre}',
                direccion='Dirección ficticia de demostración', activa=True,
            )
            sucursal.full_clean()
            sucursal.save()
            sucursales.append(sucursal)

        def pedido(sucursal, lineas, observacion):
            return guardar_solicitud(
                sucursal_id=sucursal.pk, lineas=[(productos[p].pk, cantidad) for p, cantidad in lineas],
                observaciones=f'DEMO-E3 · Solicitud ficticia {observacion}',
            )

        pedido(sucursales[0], [(0, 4), (2, 6)], 'pendiente de revisión')
        aprobada = pedido(sucursales[1], [(1, 3), (3, 2)], 'con aprobación parcial')
        cantidades = {d.pk: d.cantidad_solicitada - 1 for d in aprobada.detalles.all()}
        aprobar_solicitud(aprobada.pk, cantidades)
        rechazada = pedido(sucursales[2], [(2, 10)], 'rechazada sin afectar stock')
        rechazar_solicitud(rechazada.pk)
        despachada = pedido(sucursales[1], [(0, 3), (2, 5)], 'despachada con trazabilidad')
        aprobar_solicitud(despachada.pk)
        despachar_solicitud(despachada.pk)
