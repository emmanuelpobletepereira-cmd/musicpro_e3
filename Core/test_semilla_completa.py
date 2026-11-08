from io import StringIO
from unittest.mock import patch
import warnings

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.test import TestCase

from Core.models import (
    Categoria, Cliente, Compra, DetalleCompra, DetalleVenta, Marca,
    Movimiento, Producto, Proveedor, Venta,
)


class CargaCompletaFakerTests(TestCase):
    def cargar(self, cantidad=7, **opciones):
        salida = StringIO()
        argumentos = {'cantidad': cantidad, 'lote': 3, 'semilla': 42, 'completo': True}
        argumentos.update(opciones)
        call_command('cargar_datos', stdout=salida, **argumentos)
        return salida.getvalue()

    def test_puebla_las_diez_tablas_y_reconcilia_stock_documentos_y_movimientos(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            salida = self.cargar()
        # Este generador conserva el alcance de las diez tablas E2.
        # La muestra E3 tiene su propio comando cargar_demo_bodega.
        modelos = (Categoria, Cliente, Compra, DetalleCompra, DetalleVenta, Marca,
                   Movimiento, Producto, Proveedor, Venta)
        self.assertEqual(len(modelos), 10)
        for modelo in modelos:
            with self.subTest(modelo=modelo.__name__):
                self.assertGreater(modelo.objects.count(), 0)
                for registro in modelo.objects.all():
                    registro.full_clean()

        self.assertEqual(Producto.objects.count(), 7)
        for modelo in (Compra, DetalleCompra, Venta, DetalleVenta):
            self.assertEqual(modelo.objects.count(), 7)
        self.assertEqual(Movimiento.objects.count(), 14)
        for producto in Producto.objects.all():
            comprado = DetalleCompra.objects.get(producto=producto)
            vendido = DetalleVenta.objects.get(producto=producto)
            ingreso = Movimiento.objects.get(producto=producto, tipo='INGRESO')
            salida_venta = Movimiento.objects.get(producto=producto, tipo='SALIDA')
            self.assertIsNotNone(producto.marca_id)
            self.assertEqual(producto.cantidad, comprado.cantidad - vendido.cantidad)
            self.assertGreaterEqual(producto.cantidad, 0)
            self.assertEqual(ingreso.cantidad, comprado.cantidad)
            self.assertEqual(ingreso.detalle_compra_id, comprado.pk)
            self.assertIsNone(ingreso.detalle_venta_id)
            self.assertEqual(ingreso.motivo, 'Recepción de mercadería')
            self.assertEqual(ingreso.fecha, comprado.compra.fecha)
            self.assertEqual(salida_venta.cantidad, vendido.cantidad)
            self.assertEqual(salida_venta.detalle_venta_id, vendido.pk)
            self.assertIsNone(salida_venta.detalle_compra_id)
            self.assertEqual(salida_venta.motivo, 'Por venta')
            self.assertEqual(salida_venta.fecha, vendido.venta.fecha)
            self.assertGreater(salida_venta.fecha, ingreso.fecha)
            self.assertGreater(vendido.precio_unitario, comprado.costo_unitario)
        self.assertIn('Las diez tablas del negocio contienen datos', salida)

    def test_repetir_semilla_reutiliza_catalogos_y_conserva_registros_existentes(self):
        categoria = Categoria.objects.create(nombre='Audio')
        manual = Producto.objects.create(
            codigo='MANUAL-10-TABLAS', nombre='Amplificador del usuario',
            categoria=categoria, ubicacion='Bodega real', cantidad=23,
        )
        self.cargar(cantidad=4, lote=3)
        campos = ('nombre', 'categoria_id', 'marca_id', 'ubicacion', 'cantidad', 'stock_minimo')
        primera = list(Producto.objects.exclude(pk=manual.pk).order_by('pk').values_list(*campos))
        compras_primera = list(
            DetalleCompra.objects.order_by('pk').values_list('cantidad', 'costo_unitario', 'compra__fecha'),
        )
        catalogos = {
            modelo: set(modelo.objects.values_list('pk', flat=True))
            for modelo in (Categoria, Marca, Proveedor, Cliente)
        }
        proveedor = Proveedor.objects.first()
        proveedor.nombre = 'Nombre conservado por el usuario'
        proveedor.save(update_fields=['nombre'])
        self.cargar(cantidad=4, lote=3)

        self.assertEqual(Producto.objects.count(), 9)
        self.assertEqual(Producto.objects.values('codigo').distinct().count(), 9)
        self.assertEqual(Compra.objects.values('numero').distinct().count(), 8)
        self.assertEqual(Venta.objects.values('numero').distinct().count(), 8)
        self.assertEqual(Movimiento.objects.count(), 16)
        self.assertEqual(
            list(Producto.objects.order_by('-pk').values_list(*campos)[:4])[::-1], primera,
        )
        self.assertEqual(
            list(DetalleCompra.objects.order_by('-pk')
                 .values_list('cantidad', 'costo_unitario', 'compra__fecha')[:4])[::-1],
            compras_primera,
        )
        for modelo, ids in catalogos.items():
            self.assertEqual(set(modelo.objects.values_list('pk', flat=True)), ids)
        manual.refresh_from_db()
        proveedor.refresh_from_db()
        self.assertEqual(manual.nombre, 'Amplificador del usuario')
        self.assertEqual(manual.cantidad, 23)
        self.assertEqual(manual.ubicacion, 'Bodega real')
        self.assertEqual(proveedor.nombre, 'Nombre conservado por el usuario')

    def test_error_en_segundo_lote_revierte_toda_su_cadena_de_documentos(self):
        crear_lote = QuerySet.bulk_create
        numero_lote = 0

        def fallar_movimientos(queryset, objetos, *args, **opciones):
            nonlocal numero_lote
            if queryset.model is Movimiento:
                numero_lote += 1
                if numero_lote == 2:
                    raise IntegrityError('Fallo simulado en la cadena de documentos')
            return crear_lote(queryset, objetos, *args, **opciones)

        with patch.object(QuerySet, 'bulk_create', autospec=True, side_effect=fallar_movimientos):
            with self.assertRaisesMessage(CommandError, 'Productos confirmados en esta carga: 3'):
                self.cargar()
        for modelo in (Producto, Compra, DetalleCompra, Venta, DetalleVenta):
            self.assertEqual(modelo.objects.count(), 3)
        self.assertEqual(Movimiento.objects.count(), 6)
        self.assertEqual(
            set(DetalleCompra.objects.values_list('producto_id', flat=True)),
            set(Producto.objects.values_list('pk', flat=True)),
        )

    def test_completo_con_movimientos_no_duplica_los_ingresos(self):
        self.cargar(cantidad=2, con_movimientos=True)
        self.assertEqual(Movimiento.objects.filter(tipo='INGRESO').count(), 2)
        self.assertEqual(Movimiento.objects.filter(tipo='SALIDA').count(), 2)

    def test_recupera_pk_en_motores_que_no_las_devuelven_en_bulk_create(self):
        crear_lote = QuerySet.bulk_create

        def no_devolver_pk(queryset, objetos, *args, **opciones):
            resultado = crear_lote(queryset, objetos, *args, **opciones)
            for objeto in objetos:
                objeto.pk = None
            return resultado

        with patch.object(QuerySet, 'bulk_create', autospec=True, side_effect=no_devolver_pk):
            self.cargar(cantidad=4)
        self.assertEqual(Movimiento.objects.count(), 8)
        for movimiento in Movimiento.objects.all():
            movimiento.full_clean()
            self.assertTrue(movimiento.detalle_compra_id or movimiento.detalle_venta_id)

    def test_argumentos_invalidos_en_modo_completo_no_crean_catalogos(self):
        with self.assertRaises(CommandError):
            self.cargar(cantidad=0)
        for modelo in apps.get_app_config('bodega').get_models():
            self.assertEqual(modelo.objects.count(), 0)

    def test_verificar_bd_distingue_diez_tablas_propias_de_infraestructura(self):
        salida = StringIO()
        call_command('verificar_bd', stdout=salida)
        texto = salida.getvalue()
        self.assertIn('Tablas propias del negocio: 13 (presentes en la base: 13)', texto)
        self.assertIn('no cuentan como tablas propias del negocio', texto)
        for modelo in apps.get_app_config('bodega').get_models():
            self.assertIn(f'{modelo._meta.db_table}: 0 registros', texto)
        self.assertIn('django_migrations', texto)
