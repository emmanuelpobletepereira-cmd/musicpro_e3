"""El administrador conserva filtros aunque el servidor no tenga zonas horarias."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import Categoria, Cliente, Compra, Movimiento, Producto, Proveedor, Venta


class FechasAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser('admin-fechas', password=None)
        categoria = Categoria.objects.create(nombre='Categoría fechas')
        producto = Producto.objects.create(codigo='FECHA-01', nombre='Cable', categoria=categoria, ubicacion='A1')
        proveedor = Proveedor.objects.create(nombre='Proveedor fechas', rut='FECHAS-PROV')
        cliente = Cliente.objects.create(nombre='Cliente fechas', rut='FECHAS-CLI')
        cls.fecha_actual = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
        cls.actuales = {}
        for numero, fecha in enumerate((cls.fecha_actual - timedelta(days=5), cls.fecha_actual)):
            registros = (
                Compra.objects.create(numero=f'FECHA-C{numero}', proveedor=proveedor, fecha=fecha),
                Venta.objects.create(numero=f'FECHA-V{numero}', cliente=cliente, fecha=fecha),
                Movimiento.objects.create(producto=producto, tipo='INGRESO', cantidad=1, motivo='Prueba fechas', fecha=fecha),
            )
            if fecha == cls.fecha_actual:
                cls.actuales = {type(registro): registro.pk for registro in registros}

    def test_sin_zonas_los_listados_renderizan_y_el_filtro_fecha_funciona(self):
        self.client.force_login(self.usuario)
        with patch.object(connection.features, 'has_zoneinfo_database', False):
            for modelo, pk_actual in self.actuales.items():
                with self.subTest(modelo=modelo.__name__):
                    respuesta = self.client.get(
                        reverse(f'admin:bodega_{modelo._meta.model_name}_changelist'),
                        {'fecha__gte': self.fecha_actual.isoformat()},
                    )
                    self.assertEqual(respuesta.status_code, 200)
                    listado = respuesta.context['cl']
                    self.assertIsNone(listado.date_hierarchy)
                    self.assertEqual([registro.pk for registro in listado.result_list], [pk_actual])
                    self.assertTrue(any(getattr(filtro, 'field_path', None) == 'fecha' for filtro in listado.filter_specs))

    def test_con_zonas_se_conserva_la_jerarquia_sin_mutar_la_configuracion_compartida(self):
        request = RequestFactory().get('/admin/')
        request.user = self.usuario
        for modelo in self.actuales:
            administrador = admin.site._registry[modelo]
            with self.subTest(modelo=modelo.__name__):
                with patch.object(connection.features, 'has_zoneinfo_database', False):
                    self.assertIsNone(administrador.get_changelist_instance(request).date_hierarchy)
                with patch.object(connection.features, 'has_zoneinfo_database', True):
                    self.assertEqual(administrador.get_changelist_instance(request).date_hierarchy, 'fecha')
                self.assertEqual(administrador.date_hierarchy, 'fecha')
