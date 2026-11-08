from decimal import Decimal

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import (
    Categoria, Cliente, Compra, DetalleCompra, DetalleVenta, Marca,
    Movimiento, Producto, Proveedor, Venta, Sucursal, Solicitud, DetalleSolicitud,
)


class DiezTablasBodegaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Instrumentos')
        cls.marca = Marca.objects.create(nombre='Marca de prueba', pais='Chile')
        cls.producto = Producto.objects.create(
            codigo='DOC-01', nombre='Guitarra', categoria=cls.categoria,
            marca=cls.marca, ubicacion='A1', cantidad=7,
        )
        cls.otro_producto = Producto.objects.create(
            codigo='DOC-02', nombre='Bajo', categoria=cls.categoria, ubicacion='A2',
        )
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor de prueba', rut='11111111-1')
        cls.cliente = Cliente.objects.create(nombre='Cliente de prueba', rut='22222222-2')
        cls.compra = Compra.objects.create(numero='C-PRUEBA', proveedor=cls.proveedor)
        cls.venta = Venta.objects.create(numero='V-PRUEBA', cliente=cls.cliente)
        cls.detalle_compra = DetalleCompra.objects.create(
            compra=cls.compra, producto=cls.producto, cantidad=10,
            costo_unitario=Decimal('19990.50'),
        )
        cls.detalle_venta = DetalleVenta.objects.create(
            venta=cls.venta, producto=cls.producto, cantidad=3,
            precio_unitario=Decimal('24990.00'),
        )

    def test_conserva_diez_tablas_e2_y_agrega_tres_de_solicitudes_e3(self):
        esperados = {
            Categoria, Marca, Producto, Proveedor, Cliente, Compra, DetalleCompra,
            Venta, DetalleVenta, Movimiento,
        }
        modelos = set(apps.get_app_config('bodega').get_models())
        self.assertEqual(modelos, esperados | {Sucursal, Solicitud, DetalleSolicitud})
        tablas = set(connection.introspection.table_names())
        for modelo in modelos:
            self.assertIn(modelo._meta.db_table, tablas)
            if modelo in esperados:
                self.assertIn(modelo, admin.site._registry)
        self.assertEqual(len([t for t in tablas if t.startswith('bodega_')]), 13)

    def test_documentos_calculan_importes_con_decimal(self):
        self.assertEqual(self.detalle_compra.subtotal, Decimal('199905.00'))
        self.assertEqual(self.detalle_venta.subtotal, Decimal('74970.00'))
        self.assertEqual(self.compra.total, self.detalle_compra.subtotal)
        self.assertEqual(self.venta.total, self.detalle_venta.subtotal)

    def test_admin_muestra_listados_formularios_y_documentos_de_diez_modelos(self):
        usuario = get_user_model().objects.create_superuser('admin-diez-tablas', password=None)
        self.client.force_login(usuario)
        # Las pantallas nuevas de E3 no dependen de Django Admin.
        for modelo in (Categoria, Marca, Proveedor, Cliente, Producto, Compra,
                       DetalleCompra, Venta, DetalleVenta, Movimiento):
            prefijo = f'admin:bodega_{modelo._meta.model_name}'
            for accion in ('changelist', 'add'):
                with self.subTest(modelo=modelo.__name__, accion=accion):
                    self.assertEqual(self.client.get(reverse(f'{prefijo}_{accion}')).status_code, 200)
            objeto = modelo.objects.first()
            if objeto is not None:
                with self.subTest(modelo=modelo.__name__, accion='change'):
                    respuesta = self.client.get(reverse(f'{prefijo}_change', args=[objeto.pk]))
                    self.assertEqual(respuesta.status_code, 200)

    def test_detalles_rechazan_cero_negativos_y_productos_duplicados_en_bd(self):
        for modelo, documento, precio in (
            (DetalleCompra, {'compra': self.compra}, 'costo_unitario'),
            (DetalleVenta, {'venta': self.venta}, 'precio_unitario'),
        ):
            for cambios in ({'cantidad': 0}, {precio: Decimal('0')}, {precio: Decimal('-1')}):
                datos = dict(documento, producto=self.otro_producto, cantidad=1)
                datos[precio] = Decimal('100')
                datos.update(cambios)
                with self.subTest(modelo=modelo.__name__, cambios=cambios):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        modelo.objects.create(**datos)
            datos = dict(documento, producto=self.producto, cantidad=1)
            datos[precio] = Decimal('100')
            with self.assertRaises(IntegrityError), transaction.atomic():
                modelo.objects.create(**datos)

    def test_relaciones_protegen_catalogos_y_documentos_utilizados(self):
        for objeto in (self.proveedor, self.cliente, self.marca, self.compra, self.venta):
            with self.subTest(modelo=type(objeto).__name__):
                with self.assertRaises(ProtectedError):
                    objeto.delete()

    def test_movimiento_valida_producto_y_cantidad_del_documento(self):
        for origen, tipo, detalle in (
            ('detalle_compra', 'INGRESO', self.detalle_compra),
            ('detalle_venta', 'SALIDA', self.detalle_venta),
        ):
            movimiento = Movimiento(
                producto=self.producto, tipo=tipo, cantidad=1,
                motivo='Recepción de mercadería' if tipo == 'INGRESO' else 'Por venta',
                **{origen: detalle},
            )
            movimiento.full_clean()
            movimiento.producto = self.otro_producto
            with self.assertRaises(ValidationError):
                movimiento.full_clean()
            movimiento.producto = self.producto
            movimiento.cantidad = detalle.cantidad + 1
            with self.assertRaises(ValidationError):
                movimiento.full_clean()

    def test_base_impide_vincular_documento_del_tipo_equivocado(self):
        for datos in (
            {'tipo': 'INGRESO', 'detalle_venta': self.detalle_venta},
            {'tipo': 'SALIDA', 'detalle_compra': self.detalle_compra},
            {'tipo': 'INGRESO', 'detalle_compra': self.detalle_compra, 'detalle_venta': self.detalle_venta},
        ):
            with self.subTest(datos=datos):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Movimiento.objects.create(
                        producto=self.producto, cantidad=1, motivo='Operación de prueba', **datos,
                    )

    def test_datos_anteriores_pueden_seguir_sin_marca_ni_documento(self):
        self.assertIsNone(self.otro_producto.marca_id)
        movimiento = Movimiento.objects.create(
            producto=self.otro_producto, tipo='SALIDA', cantidad=1, motivo='Por venta',
        )
        movimiento.full_clean()
        self.assertIsNone(movimiento.detalle_compra_id)
        self.assertIsNone(movimiento.detalle_venta_id)
