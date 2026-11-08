from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase

from .models import Categoria, Movimiento, Producto, Proveedor, Solicitud, Sucursal


class DemoBodegaTests(TestCase):
    def test_muestra_idempotente_y_stock_despachado_sin_alterar_datos_ajenos(self):
        categoria = Categoria.objects.create(nombre='Categoría ajena a la demostración')
        ajeno = Producto.objects.create(
            codigo='AJENO-01', nombre='Producto existente', categoria=categoria,
            ubicacion='Original', cantidad=41,
        )
        original = dict(Producto.objects.filter(pk=ajeno.pk).values().get())
        call_command('cargar_demo_bodega', stdout=StringIO())
        demo = Producto.objects.filter(codigo__startswith='DEMO-E3-').order_by('codigo')
        self.assertEqual(list(demo.values_list('cantidad', flat=True)), [17, 12, 25, 8])
        self.assertEqual(set(Solicitud.objects.values_list('estado', flat=True)), {'PENDIENTE', 'APROBADA', 'RECHAZADA', 'DESPACHADA'})
        self.assertEqual(Movimiento.objects.filter(stock_aplicado=True).count(), 6)
        self.assertEqual(Proveedor.objects.filter(rut__startswith='DEMO-E3-').count(), 2)
        self.assertEqual(Sucursal.objects.filter(codigo__startswith='DEMO-E3-').count(), 3)
        antes = list(demo.values())
        movimientos = list(Movimiento.objects.values())
        call_command('cargar_demo_bodega', stdout=StringIO())
        self.assertEqual(list(demo.values()), antes)
        self.assertEqual(list(Movimiento.objects.values()), movimientos)
        self.assertEqual(dict(Producto.objects.filter(pk=ajeno.pk).values().get()), original)
        self.assertEqual(Solicitud.objects.count(), 4)

    def test_fallo_de_carga_revierte_la_muestra_completa(self):
        with patch('Core.management.commands.cargar_demo_bodega.registrar_movimiento', side_effect=ValidationError('Fallo de prueba')):
            with self.assertRaises(CommandError):
                call_command('cargar_demo_bodega', stdout=StringIO())
        self.assertFalse(Producto.objects.exists())
        self.assertFalse(Proveedor.objects.exists())
        self.assertFalse(Categoria.objects.exists())
        self.assertFalse(Sucursal.objects.exists())
        self.assertFalse(Movimiento.objects.exists())

    def test_prefijo_incompleto_no_reescribe_registros(self):
        categoria = Categoria.objects.create(nombre='Categoría anterior')
        producto = Producto.objects.create(
            codigo='DEMO-E3-COLISION', nombre='Registro anterior', categoria=categoria,
            ubicacion='Original', cantidad=9,
        )
        with self.assertRaises(CommandError):
            call_command('cargar_demo_bodega', stdout=StringIO())
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, 9)
        self.assertEqual(Producto.objects.count(), 1)
        self.assertFalse(Proveedor.objects.exists())
