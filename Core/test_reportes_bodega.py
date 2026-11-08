from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import (
    Categoria, DetalleSolicitud, Movimiento, Producto, Proveedor, Solicitud,
    Sucursal,
)
from .reportes import REPORTES, construye_reporte, ultimo_mes_calendario


def fecha_chile(texto):
    return datetime.fromisoformat(texto).replace(tzinfo=ZoneInfo('America/Santiago'))


class ReportesBodegaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('reportes-admin', password=None)
        cls.categoria_a = Categoria.objects.create(nombre='Audio')
        cls.categoria_b = Categoria.objects.create(nombre='Instrumentos')
        cls.categoria_vacia = Categoria.objects.create(nombre='Sin productos')
        cls.proveedor_a = Proveedor.objects.create(nombre='Proveedor A', rut='11111111-1')
        cls.proveedor_b = Proveedor.objects.create(nombre='Proveedor B', rut='22222222-2')
        cls.p1 = Producto.objects.create(codigo='G-01', nombre='Guitarra', categoria=cls.categoria_a, proveedor=cls.proveedor_a, ubicacion='A1', precio=Decimal('100.50'), cantidad=2, stock_minimo=5)
        cls.p2 = Producto.objects.create(codigo='C-01', nombre='Cable', categoria=cls.categoria_a, proveedor=cls.proveedor_a, ubicacion='A2', precio=Decimal('10.00'), cantidad=5, stock_minimo=5)
        cls.p3 = Producto.objects.create(codigo='P-01', nombre='Piano', categoria=cls.categoria_b, proveedor=cls.proveedor_b, ubicacion='B1', precio=Decimal('1000.00'), cantidad=1, stock_minimo=0)
        cls.p4 = Producto.objects.create(codigo='F-01', nombre='Funda', categoria=cls.categoria_b, ubicacion='B2', precio=Decimal('20.00'), cantidad=0, stock_minimo=1)
        cls.sucursal_a = Sucursal.objects.create(codigo='A', nombre='Centro')
        cls.sucursal_b = Sucursal.objects.create(codigo='B', nombre='Norte')
        cls.sucursal_c = Sucursal.objects.create(codigo='C', nombre='Sur')
        cls.s1 = Solicitud.objects.create(sucursal=cls.sucursal_a, fecha=fecha_chile('2026-10-01T00:00:00'), estado='PENDIENTE')
        cls.s2 = Solicitud.objects.create(sucursal=cls.sucursal_a, fecha=fecha_chile('2026-10-31T23:59:59'), estado='APROBADA')
        cls.s3 = Solicitud.objects.create(sucursal=cls.sucursal_b, fecha=fecha_chile('2026-11-01T00:00:00'), estado='RECHAZADA')
        cls.s4 = Solicitud.objects.create(sucursal=cls.sucursal_b, fecha=fecha_chile('2026-09-30T23:59:59'), estado='DESPACHADA')
        cls.s5 = Solicitud.objects.create(sucursal=cls.sucursal_c, fecha=fecha_chile('2026-10-15T12:00:00'), estado='PENDIENTE')
        for solicitud, producto, unidades in ((cls.s1, cls.p1, 3), (cls.s1, cls.p2, 2), (cls.s2, cls.p1, 1), (cls.s3, cls.p3, 8), (cls.s4, cls.p2, 4)):
            DetalleSolicitud.objects.create(solicitud=solicitud, producto=producto, cantidad_solicitada=unidades)
        for producto, tipo, unidades, fecha, aplicado in (
            (cls.p1, 'SALIDA', 2, '2026-10-01T00:00:00', False),
            (cls.p1, 'SALIDA', 3, '2026-10-31T23:59:59', True),
            (cls.p2, 'SALIDA', 9, '2026-09-30T23:59:59', False),
            (cls.p3, 'INGRESO', 50, '2026-10-15T12:00:00', True),
            (cls.p3, 'SALIDA', 7, '2026-11-01T00:00:00', True),
        ):
            Movimiento.objects.create(producto=producto, tipo=tipo, cantidad=unidades, fecha=fecha_chile(fecha), motivo='Prueba del reporte', stock_aplicado=aplicado)

    def filas(self, numero, **filtros):
        return list(construye_reporte(numero, filtros)['filas'])

    def test_reportes_1_a_8_productos_catalogos_y_detalle(self):
        self.assertEqual(len(self.filas(1)), 4)
        self.assertEqual({f['codigo'] for f in self.filas(2, categoria=self.categoria_a.pk)}, {'G-01', 'C-01'})
        self.assertEqual({f['codigo'] for f in self.filas(3)}, {'G-01', 'F-01'})
        self.assertEqual({f['nombre']: f['total_productos'] for f in self.filas(5)}, {'Audio': 2, 'Instrumentos': 2, 'Sin productos': 0})
        self.assertEqual({f['codigo'] for f in self.filas(6, proveedor=self.proveedor_a.pk)}, {'G-01', 'C-01'})
        self.assertEqual({f['id'] for f in self.filas(7, sucursal=self.sucursal_a.pk)}, {self.s1.pk, self.s2.pk})
        self.assertEqual({f['producto__codigo']: f['cantidad_solicitada'] for f in self.filas(8, solicitud=self.s1.pk)}, {'G-01': 3, 'C-01': 2})

    def test_reportes_9_a_15_estados_rankings_y_nunca_solicitados(self):
        self.assertEqual({f['estado']: f['total_solicitudes'] for f in self.filas(9)}, {'Pendiente': 2, 'Aprobada': 1, 'Rechazada': 1, 'Despachada': 1})
        self.assertEqual({f['id'] for f in self.filas(10, desde=date(2026, 10, 1), hasta=date(2026, 10, 31))}, {self.s1.pk, self.s2.pk, self.s5.pk})
        self.assertEqual([(f['codigo'], f['total_unidades']) for f in self.filas(11)], [('B', 12), ('A', 6), ('C', 0)])
        self.assertEqual([(f['codigo'], f['total_unidades']) for f in self.filas(12)], [('P-01', 8), ('C-01', 6), ('G-01', 4)])
        self.assertEqual(self.filas(13), [{'nombre': 'Proveedor A', 'total_productos': 2}])
        self.assertEqual([f['codigo'] for f in self.filas(15)], ['F-01'])

    @patch('Core.reportes.timezone.localdate', return_value=date(2026, 11, 7))
    def test_reportes_16_a_20_movimientos_pendientes_agrupaciones_y_periodo(self, _fecha):
        self.assertEqual(ultimo_mes_calendario(), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(self.filas(16), [{'producto__codigo': 'G-01', 'producto__nombre': 'Guitarra', 'total_unidades': 5}])
        self.assertEqual([f['codigo'] for f in self.filas(17)], ['A', 'C'])
        self.assertEqual(self.filas(19)[0]['promedio_unidades'], Decimal('3.6'))
        self.assertEqual([(f['codigo'], f['total_unidades']) for f in self.filas(20, desde=date(2026, 10, 1), hasta=date(2026, 10, 31))], [('G-01', 4), ('C-01', 2)])

    @patch('Core.reportes.timezone.localdate', return_value=date(2027, 1, 3))
    def test_ultimo_mes_cruza_el_anio(self, _fecha):
        self.assertEqual(ultimo_mes_calendario(), (date(2026, 12, 1), date(2026, 12, 31)))

    def test_los_diecisiete_reportes_ejecutan_consultas_sin_columnas_monetarias(self):
        self.assertEqual(len(REPORTES), 17)
        self.client.force_login(self.admin)
        filtros = {'categoria': self.categoria_a.pk, 'proveedor': self.proveedor_a.pk, 'sucursal': self.sucursal_a.pk, 'solicitud': self.s1.pk, 'desde': '2026-10-01', 'hasta': '2026-10-31'}
        for numero in REPORTES:
            with self.subTest(reporte=numero):
                with CaptureQueriesContext(connection) as consultas:
                    respuesta = self.client.get(reverse('bodega:reportes'), {'n': numero, **filtros})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context['errores'], [])
                self.assertEqual(respuesta.context['reporte']['numero'], numero)
                self.assertTrue(any(c['sql'].lstrip().upper().startswith('SELECT') for c in consultas))
                self.assertNotContains(respuesta, '<pre')
                self.assertNotContains(respuesta, 'QUERY')
                self.assertNotContains(respuesta, 'Precio')
                self.assertNotContains(respuesta, 'Valor del inventario')
                self.assertTrue(all('precio' not in campo and 'valor' not in campo
                                    for campo, _ in respuesta.context['reporte']['columnas']))
                self.assertNotIn('consultas', respuesta.context)

    def test_reportes_economicos_retirados_no_se_ejecutan_desde_una_url_directa(self):
        self.client.force_login(self.admin)
        for numero in (4, 14, 18):
            with self.subTest(reporte=numero):
                self.assertNotIn(numero, REPORTES)
                with self.assertNumQueries(0):
                    with self.assertRaises(ValueError):
                        construye_reporte(numero, {})
                with patch('Core.views_reportes.construye_reporte') as construir:
                    respuesta = self.client.get(reverse('bodega:reportes'), {'n': numero})
                self.assertEqual(respuesta.status_code, 404)
                construir.assert_not_called()

    def test_filtros_obligatorios_invalidos_y_fechas_invertidas_no_ejecutan_reporte(self):
        self.client.force_login(self.admin)
        for parametros in (
            {'n': 2}, {'n': 6}, {'n': 7}, {'n': 8}, {'n': 10}, {'n': 20},
            {'n': 2, 'categoria': '1 OR 1=1'}, {'n': 2, 'categoria': '999999999999999999'},
            {'n': 10, 'desde': '2026-02-30', 'hasta': '2026-11-01'},
            {'n': 10, 'desde': '2026-11-02', 'hasta': '2026-11-01'},
            {'n': 10, 'desde': '0001-01-01', 'hasta': '2026-11-01'},
            {'n': 20, 'desde': '2026-11-01', 'hasta': '9999-12-31'},
            {'n': 21}, {'n': '<script>alert(1)</script>'},
        ):
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(reverse('bodega:reportes'), parametros)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context['errores'])
                self.assertIsNone(respuesta.context['reporte'])

    def test_acceso_anonimo_y_permisos_por_entidad_y_metodo(self):
        url = reverse('bodega:reportes')
        self.assertRedirects(self.client.get(url), reverse('bodega:login') + '?next=' + url, fetch_redirect_response=False)
        usuario = get_user_model().objects.create_user('reportes-limitado', password=None)
        usuario.user_permissions.add(Permission.objects.get(content_type__app_label='bodega', codename='view_producto'))
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(url, {'n': 9}).status_code, 403)
        self.assertEqual(self.client.get(url, {'n': 8, 'solicitud': self.s1.pk}).status_code, 403)
        usuario.user_permissions.add(Permission.objects.get(content_type__app_label='bodega', codename='view_solicitud'))
        self.assertEqual(self.client.get(url, {'n': 9}).status_code, 200)
        self.assertEqual(self.client.get(url, {'n': 9, 'categoria': self.categoria_a.pk}).status_code, 403)
        self.assertEqual(self.client.post(url, {'n': 9}).status_code, 405)

    def test_paginacion_permita_consultar_todos_y_escapa_datos(self):
        self.p1.nombre = '<script>alert("producto")</script>'
        self.p1.save()
        Producto.objects.bulk_create([Producto(codigo=f'PAG-{n:02d}', nombre='Producto paginado', categoria=self.categoria_a, ubicacion='C') for n in range(30)])
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('bodega:reportes'), {'n': 1})
        self.assertEqual(respuesta.context['pagina'].paginator.count, 34)
        self.assertEqual(len(respuesta.context['filas']), 25)
        self.assertContains(respuesta, '&lt;script&gt;')
        self.assertNotContains(respuesta, '<script>')
        siguiente = self.client.get(reverse('bodega:reportes'), {'n': 1, 'page': 2})
        self.assertEqual(len(siguiente.context['filas']), 9)

    def test_panel_presenta_diecisiete_preguntas_y_metricas_de_existencias_sin_modificar_datos(self):
        self.client.force_login(self.admin)
        stock_antes = list(Producto.objects.order_by('pk').values_list('pk', 'cantidad'))
        conteos_antes = (Solicitud.objects.count(), DetalleSolicitud.objects.count(), Movimiento.objects.count())
        respuesta = self.client.get(reverse('bodega:panel_consultas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'data-reporte="', count=17)
        self.assertEqual([(g['nivel'], len(g['tarjetas'])) for g in respuesta.context['grupos']],
                         [('Básico', 4), ('Intermedio', 7), ('Avanzado', 4), ('Análisis', 2)])
        self.assertEqual(respuesta.context['metricas'], {
            'total_productos': 4, 'stock_critico': 2,
            'total_unidades': 8, 'solicitudes_pendientes': 2,
        })
        tarjetas = [t for grupo in respuesta.context['grupos'] for t in grupo['tarjetas']]
        self.assertEqual([t['numero'] for t in tarjetas], [n for n in range(1, 21) if n not in (4, 14, 18)])
        self.assertTrue(all(t['pregunta'] and t['autorizada'] for t in tarjetas))
        self.assertTrue(all('orm' not in t for t in tarjetas))
        self.assertEqual([c['nombre'] for c in tarjetas[1]['campos']], ['categoria'])
        self.assertEqual([c['nombre'] for c in tarjetas[-1]['campos']], ['desde', 'hasta'])
        self.assertEqual(list(Producto.objects.order_by('pk').values_list('pk', 'cantidad')), stock_antes)
        self.assertEqual((Solicitud.objects.count(), DetalleSolicitud.objects.count(), Movimiento.objects.count()), conteos_antes)

    def test_panel_protege_acceso_y_no_consulta_entidades_sin_permiso(self):
        url = reverse('bodega:panel_consultas')
        self.assertRedirects(self.client.get(url), reverse('bodega:login') + '?next=' + url, fetch_redirect_response=False)
        usuario = get_user_model().objects.create_user('panel-limitado', password=None)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(url).status_code, 403)
        usuario.user_permissions.add(Permission.objects.get(content_type__app_label='bodega', codename='view_producto'))
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('solicitudes_pendientes', respuesta.context['metricas'])
        self.assertFalse(respuesta.context['puede_ver_solicitudes'])
        self.assertFalse(any('bodega_solicitud' in consulta['sql'].lower() for consulta in consultas))
        self.assertNotContains(respuesta, self.proveedor_a.nombre)
        self.assertNotContains(respuesta, self.sucursal_a.nombre)
        tarjetas = [t for grupo in respuesta.context['grupos'] for t in grupo['tarjetas']]
        self.assertEqual([t['numero'] for t in tarjetas if t['autorizada']], [])
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_reporte_filtra_por_nombre_e_id_manual_fuera_de_las_cien_opciones(self):
        Categoria.objects.bulk_create([Categoria(nombre=f'Extra {n:03d}') for n in range(100)])
        categoria = Categoria.objects.create(nombre='ZZZ Categoría fuera de las sugerencias')
        Producto.objects.create(codigo='MANUAL-01', nombre='Producto por ID', categoria=categoria, ubicacion='M')
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('bodega:reportes'), {
            'n': 2, 'categoria': self.categoria_a.pk, 'categoria_manual': categoria.pk,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['errores'], [])
        self.assertEqual(respuesta.context['pagina'].paginator.count, 1)
        self.assertEqual(respuesta.context['criterios'], [('Categoría', categoria.nombre)])
        campo = respuesta.context['campos'][0]
        self.assertEqual(campo['manual'], str(categoria.pk))
        self.assertEqual(len(campo['opciones']), 100)
        self.assertTrue(all(opcion['etiqueta'] for opcion in campo['opciones']))
        self.assertContains(respuesta, 'MANUAL-01')
        self.assertNotContains(respuesta, 'name="proveedor"')
        self.assertNotContains(respuesta, 'name="desde"')
        invalida = self.client.get(reverse('bodega:reportes'), {
            'n': 2, 'categoria_manual': '1 OR 1=1',
        })
        self.assertTrue(invalida.context['errores'])
        self.assertIsNone(invalida.context['reporte'])

    def test_resultado_muestra_solo_sus_filtros_y_datos_sin_explicaciones(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('bodega:reportes'), {
            'n': 20, 'desde': '2026-10-01', 'hasta': '2026-10-31',
        })
        self.assertEqual([c['nombre'] for c in respuesta.context['campos']], ['desde', 'hasta'])
        self.assertContains(respuesta, 'name="desde"')
        self.assertContains(respuesta, 'name="hasta"')
        self.assertNotContains(respuesta, 'name="categoria"')
        self.assertNotContains(respuesta, 'QUERY')
        self.assertNotContains(respuesta, '<pre')
        self.assertNotContains(respuesta, 'Parámetros separados')
        self.assertEqual([fila[0] for fila in respuesta.context['filas']], ['G-01', 'C-01'])

    def test_filtro_solicitud_no_revela_sucursal_sin_permiso_sobre_ella(self):
        usuario = get_user_model().objects.create_user('detalle-sin-sucursal', password=None)
        usuario.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='bodega',
            codename__in=['view_producto', 'view_solicitud', 'view_detallesolicitud'],
        ))
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('bodega:reportes'), {'n': 8, 'solicitud': self.s1.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.sucursal_a.nombre)
        self.assertTrue(respuesta.context['criterios'])


class ReportesVaciosTests(TestCase):
    def test_sin_datos_los_agregados_devuelven_cero_y_estados_completos(self):
        self.assertEqual(construye_reporte(19, {})['filas'][0]['promedio_unidades'], Decimal('0'))
        self.assertEqual([f['total_solicitudes'] for f in construye_reporte(9, {})['filas']], [0, 0, 0, 0])
        self.assertEqual(list(construye_reporte(13, {})['filas']), [])
