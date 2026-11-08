from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from .models import Categoria, Producto, Movimiento


class EvaluacionDosTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('prueba', password='Clave-de-prueba-123')
        self.client.force_login(user)
        self.categoria = Categoria.objects.create(nombre='Audio')

    def test_crud_producto_en_admin(self):
        datos = dict(codigo='DEF-01', nombre='Amplificador', categoria=self.categoria.pk,
                     ubicacion='A1', cantidad=10, stock_minimo=5, precio='24990.00', estado='ACTIVO')
        respuesta = self.client.post(reverse('admin:bodega_producto_add'), datos)
        self.assertEqual(respuesta.status_code, 302)
        producto = Producto.objects.get(codigo='DEF-01')
        datos['cantidad'] = 20
        respuesta = self.client.post(reverse('admin:bodega_producto_change', args=[producto.pk]), datos)
        self.assertEqual(respuesta.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.cantidad, 20)
        self.assertContains(self.client.get(reverse('admin:bodega_producto_changelist'), {'q': 'DEF-01'}), 'Amplificador')
        respuesta = self.client.post(reverse('admin:bodega_producto_delete', args=[producto.pk]), {'post': 'yes'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=producto.pk).exists())

    def test_faker_y_paginacion_en_admin(self):
        call_command('cargar_datos', cantidad=100)
        self.assertEqual(Producto.objects.count(), 100)
        self.assertEqual(Producto.objects.values('codigo').distinct().count(), 100)
        respuesta = self.client.get(reverse('admin:bodega_producto_changelist'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['cl'].result_list), 50)
        self.assertEqual(self.client.get(reverse('admin:bodega_movimiento_changelist')).status_code, 200)

    def test_movimiento_rechaza_cero_en_admin(self):
        producto = Producto.objects.create(codigo='P1', nombre='Cable', categoria=self.categoria, ubicacion='A')
        respuesta = self.client.post(reverse('admin:bodega_movimiento_add'), {
            'producto': producto.pk, 'tipo': 'SALIDA', 'cantidad': 0,
            'fecha_0': '2026-10-12', 'fecha_1': '10:00:00', 'motivo': 'Prueba',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('cantidad', respuesta.context['adminform'].form.errors)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_admin_filtra_movimientos_por_tipo(self):
        producto = Producto.objects.create(
            codigo='VENTA-01', nombre='Guitarra', categoria=self.categoria, ubicacion='A1',
        )
        ingreso = Movimiento.objects.create(
            producto=producto, tipo='INGRESO', cantidad=10, motivo='Recepción de mercadería',
        )
        salida = Movimiento.objects.create(
            producto=producto, tipo='SALIDA', cantidad=2, motivo='Por venta',
        )
        url = reverse('admin:bodega_movimiento_changelist')
        respuesta = self.client.get(url, {'tipo__exact': 'SALIDA'})
        self.assertEqual([m.pk for m in respuesta.context['cl'].result_list], [salida.pk])
        self.assertContains(respuesta, 'Por venta')
        self.assertNotContains(respuesta, 'Recepción de mercadería')
        respuesta = self.client.get(url, {'tipo__exact': 'INGRESO'})
        self.assertEqual([m.pk for m in respuesta.context['cl'].result_list], [ingreso.pk])

    def test_admin_se_conserva_junto_al_crud_web(self):
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('bodega:productos')).status_code, 200)
        self.assertEqual(self.client.get(reverse('bodega:inicio')).status_code, 200)
