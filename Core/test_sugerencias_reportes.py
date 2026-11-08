from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Categoria, DetalleSolicitud, Producto, Solicitud, Sucursal


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SugerenciasReportesPermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user('lector-solicitud-sin-sucursal')
        cls.usuario.user_permissions.set(Permission.objects.filter(
            content_type__app_label='bodega',
            codename__in=['view_producto', 'view_solicitud', 'view_detallesolicitud'],
        ))
        cls.sucursal = Sucursal.objects.create(
            codigo='SUC-RESERVADA', nombre='SUCURSAL_RESERVADA_NO_REVELAR',
        )
        categoria = Categoria.objects.create(nombre='Categoría sugerencias')
        cls.producto = Producto.objects.create(
            codigo='SUG-01', nombre='Producto del detalle', categoria=categoria,
            ubicacion='A1', cantidad=0,
        )
        cls.solicitud = Solicitud.objects.create(
            sucursal=cls.sucursal,
            fecha=datetime(2026, 11, 3, 15, 0, tzinfo=ZoneInfo('America/Santiago')),
        )
        DetalleSolicitud.objects.create(
            solicitud=cls.solicitud, producto=cls.producto, cantidad_solicitada=4,
        )

    def setUp(self):
        # La creación de la sesión queda fuera de la captura de consultas.
        self.client.force_login(self.usuario)

    def assert_sin_consultas_sucursal(self, consultas):
        for consulta in consultas:
            self.assertNotIn('bodega_sucursal', consulta['sql'].lower())

    def test_panel_ofrece_solicitud_por_id_y_fecha_sin_cargar_sucursal(self):
        self.assertFalse(self.usuario.has_perm('bodega.view_sucursal'))
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('bodega:panel_consultas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assert_sin_consultas_sucursal(consultas)
        self.assertNotContains(respuesta, self.sucursal.nombre)
        self.assertNotContains(respuesta, self.sucursal.codigo)
        tarjetas = [tarjeta for grupo in respuesta.context['grupos'] for tarjeta in grupo['tarjetas']]
        tarjeta = next(tarjeta for tarjeta in tarjetas if tarjeta['numero'] == 8)
        self.assertTrue(tarjeta['autorizada'])
        campo = next(campo for campo in tarjeta['campos'] if campo['nombre'] == 'solicitud')
        opcion = next(opcion for opcion in campo['opciones'] if opcion['id'] == self.solicitud.pk)
        self.assertIn(f'#{self.solicitud.pk}', opcion['etiqueta'])
        self.assertIn('2026', opcion['etiqueta'])
        self.assertNotIn(self.sucursal.nombre, opcion['etiqueta'])

    def test_reporte_ocho_muestra_detalle_y_criterio_sin_revelar_sucursal(self):
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('bodega:reportes'), {
                'n': '8', 'solicitud': self.solicitud.pk,
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assert_sin_consultas_sucursal(consultas)
        self.assertNotContains(respuesta, self.sucursal.nombre)
        self.assertNotContains(respuesta, self.sucursal.codigo)
        self.assertEqual(respuesta.context['filas'], [[
            self.producto.codigo, self.producto.nombre, 4, 0, 0,
        ]])
        criterio = dict(respuesta.context['criterios'])['Solicitud']
        self.assertIn(f'#{self.solicitud.pk}', criterio)
        self.assertNotIn(self.sucursal.nombre, criterio)

    def test_id_manual_de_solicitud_tampoco_carga_o_revela_sucursal(self):
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('bodega:reportes'), {
                'n': '8', 'solicitud_manual': str(self.solicitud.pk),
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assert_sin_consultas_sucursal(consultas)
        self.assertNotContains(respuesta, self.sucursal.nombre)
        self.assertEqual(respuesta.context['filas'][0][2], 4)
        self.assertIn(f'#{self.solicitud.pk}', dict(respuesta.context['criterios'])['Solicitud'])
