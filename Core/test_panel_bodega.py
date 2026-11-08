from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Categoria, DetalleSolicitud, Marca, Movimiento, Producto, Proveedor, Solicitud, Sucursal


def dar_permisos(usuario, *codigos):
    usuario.user_permissions.add(*Permission.objects.filter(
        content_type__app_label='bodega', codename__in=codigos,
    ))


class PanelBodegaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user('panel-lector')
        dar_permisos(cls.usuario, 'view_producto')
        cls.completo = get_user_model().objects.create_user('panel-lector-completo')
        dar_permisos(cls.completo, 'view_producto', 'view_sucursal', 'view_solicitud', 'view_detallesolicitud', 'view_movimiento')
        cls.categoria = Categoria.objects.create(nombre='Instrumentos del panel')
        cls.marca = Marca.objects.create(nombre='Marca de ficha')
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor de ficha', rut='PANEL-01')
        cls.producto = Producto.objects.create(
            codigo='FICHA-01', nombre='Guitarra de ficha', categoria=cls.categoria,
            marca=cls.marca, proveedor=cls.proveedor, ubicacion='Estante de ficha',
            precio=Decimal('24990.00'), cantidad=7, stock_minimo=5,
        )
        Producto.objects.create(codigo='FICHA-02', nombre='Producto agotado', categoria=cls.categoria, ubicacion='B', cantidad=0)
        Producto.objects.create(codigo='FICHA-03', nombre='Producto inactivo', categoria=cls.categoria, ubicacion='C', cantidad=3, estado='INACTIVO')
        cls.sucursal = Sucursal.objects.create(codigo='PANEL-S01', nombre='Sucursal confidencial')
        Sucursal.objects.create(codigo='PANEL-S02', nombre='Sucursal inactiva', activa=False)
        cls.solicitudes = []
        for numero in range(12):
            solicitud = Solicitud.objects.create(sucursal=cls.sucursal, estado='PENDIENTE' if numero % 2 else 'RECHAZADA')
            DetalleSolicitud.objects.create(solicitud=solicitud, producto=cls.producto, cantidad_solicitada=numero+1)
            cls.solicitudes.append(solicitud)
        cls.movimiento = Movimiento.objects.create(
            producto=cls.producto, tipo='INGRESO', cantidad=7, motivo='Motivo de acceso restringido',
        )

    def test_panel_y_ficha_exigen_sesion_y_permiso_de_producto(self):
        urls = [reverse('bodega:inicio'), reverse('bodega:producto_detalle', args=[self.producto.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        sin_permiso = get_user_model().objects.create_user('panel-sin-permiso')
        self.client.force_login(sin_permiso)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_panel_agrega_datos_reales_y_limita_ultimas_solicitudes(self):
        self.client.force_login(self.completo)
        respuesta = self.client.get(reverse('bodega:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['metricas'], {
            'total_productos': 3, 'total_unidades': 10,
            'sucursales_activas': 1, 'solicitudes_pendientes': 6,
        })
        recientes = respuesta.context['ultimas_solicitudes']
        self.assertEqual(len(recientes), 10)
        self.assertEqual(recientes[0].pk, self.solicitudes[-1].pk)
        self.assertContains(respuesta, 'Sucursal confidencial')
        self.assertContains(respuesta, reverse('bodega:productos'))

    def test_panel_no_consulta_ni_revela_entidades_sin_permiso(self):
        self.client.force_login(self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('bodega:inicio'))
        self.assertIsNone(respuesta.context['metricas']['sucursales_activas'])
        self.assertIsNone(respuesta.context['metricas']['solicitudes_pendientes'])
        self.assertEqual(respuesta.context['ultimas_solicitudes'], [])
        self.assertNotContains(respuesta, 'Sucursal confidencial')
        sql = ' '.join(consulta['sql'].lower() for consulta in consultas)
        self.assertNotIn('bodega_sucursal', sql)
        self.assertNotIn('bodega_solicitud', sql)

    def test_ficha_muestra_campos_y_relaciones_solo_con_todos_los_permisos(self):
        self.client.force_login(self.completo)
        respuesta = self.client.get(reverse('bodega:producto_detalle', args=[self.producto.pk]))
        for valor in ('Guitarra de ficha', 'FICHA-01', 'Instrumentos del panel', 'Marca de ficha', 'Proveedor de ficha', 'Estante de ficha', 'Motivo de acceso restringido', 'Sucursal confidencial'):
            self.assertContains(respuesta, valor)
        self.assertEqual(len(respuesta.context['solicitudes_relacionadas']), 10)
        self.assertEqual(respuesta.context['movimientos'][0].pk, self.movimiento.pk)

    def test_ficha_sin_permisos_relacionados_no_consulta_ni_revela_sus_datos(self):
        self.client.force_login(self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('bodega:producto_detalle', args=[self.producto.pk]))
        self.assertEqual(respuesta.context['movimientos'], [])
        self.assertEqual(respuesta.context['solicitudes_relacionadas'], [])
        self.assertNotContains(respuesta, 'Motivo de acceso restringido')
        self.assertNotContains(respuesta, 'Sucursal confidencial')
        sql = ' '.join(consulta['sql'].lower() for consulta in consultas)
        for tabla in ('bodega_movimiento', 'bodega_detallesolicitud', 'bodega_solicitud', 'bodega_sucursal'):
            self.assertNotIn(tabla, sql)

    def test_permiso_solicitud_solo_no_habilita_sucursal_ni_detalles(self):
        dar_permisos(self.usuario, 'view_solicitud')
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse('bodega:inicio'))
        self.assertEqual(respuesta.context['metricas']['solicitudes_pendientes'], 6)
        self.assertEqual(respuesta.context['ultimas_solicitudes'], [])
        self.assertNotContains(respuesta, 'Sucursal confidencial')
        detalle = self.client.get(reverse('bodega:producto_detalle', args=[self.producto.pk]))
        self.assertEqual(detalle.context['solicitudes_relacionadas'], [])
        self.assertNotContains(detalle, 'Sucursal confidencial')

    def test_consultas_son_get_y_no_modifican_datos(self):
        self.client.force_login(self.completo)
        antes = list(Producto.objects.order_by('pk').values())
        solicitudes = list(Solicitud.objects.order_by('pk').values())
        movimientos = list(Movimiento.objects.order_by('pk').values())
        for url in (reverse('bodega:inicio'), reverse('bodega:producto_detalle', args=[self.producto.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.post(url, {'cantidad': 999, 'estado': 'DESPACHADA'}).status_code, 405)
        self.assertEqual(list(Producto.objects.order_by('pk').values()), antes)
        self.assertEqual(list(Solicitud.objects.order_by('pk').values()), solicitudes)
        self.assertEqual(list(Movimiento.objects.order_by('pk').values()), movimientos)

    def test_producto_inexistente_devuelve_404(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('bodega:producto_detalle', args=[9999999])).status_code, 404)


class PanelVacioTests(TestCase):
    def test_inventario_vacio_muestra_cero_en_suma_y_conteo(self):
        usuario = get_user_model().objects.create_user('panel-vacio')
        dar_permisos(usuario, 'view_producto')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('bodega:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['metricas']['total_productos'], 0)
        self.assertEqual(respuesta.context['metricas']['total_unidades'], 0)
