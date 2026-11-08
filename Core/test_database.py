from io import StringIO
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.db.models.query import QuerySet
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse

from .models import Categoria, Movimiento, Producto


class IntegridadBaseDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Audio')
        cls.producto = Producto.objects.create(
            codigo='INTEGRIDAD-01', nombre='Amplificador',
            categoria=cls.categoria, ubicacion='A1', cantidad=10,
        )

    def test_etiqueta_historica_conserva_tablas_y_migraciones(self):
        self.assertEqual(apps.get_app_config('bodega').name, 'Core')
        self.assertEqual(Producto._meta.db_table, 'bodega_producto')
        self.assertEqual(Categoria._meta.db_table, 'bodega_categoria')
        self.assertEqual(Movimiento._meta.db_table, 'bodega_movimiento')

    def test_base_rechaza_cantidad_cero_y_tipo_invalido_sin_formulario(self):
        for cambios in ({'cantidad': 0}, {'tipo': 'AJUSTE'}):
            datos = dict(
                producto=self.producto, tipo='INGRESO',
                cantidad=1, motivo='Validación de la base',
            )
            datos.update(cambios)
            with self.subTest(cambios=cambios):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Movimiento.objects.create(**datos)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_relaciones_protegen_productos_y_categorias_utilizados(self):
        movimiento = Movimiento.objects.create(
            producto=self.producto, tipo='SALIDA', cantidad=2, motivo='Prueba',
        )
        with self.assertRaises(ProtectedError):
            self.categoria.delete()
        with self.assertRaises(ProtectedError):
            self.producto.delete()
        self.assertTrue(Movimiento.objects.filter(pk=movimiento.pk).exists())
        movimiento.delete()
        self.producto.delete()
        self.categoria.delete()
        self.assertFalse(Categoria.objects.exists())


class CargaFakerTests(TestCase):
    def cargar(self, cantidad, **opciones):
        salida = StringIO()
        call_command('cargar_datos', cantidad=cantidad, stdout=salida, **opciones)
        return salida.getvalue()

    def test_lotes_con_remanente_guardan_todos_los_productos(self):
        self.cargar(7, lote=3, semilla=42)
        self.assertEqual(Producto.objects.count(), 7)
        self.assertEqual(Producto.objects.values('codigo').distinct().count(), 7)
        self.assertEqual(Movimiento.objects.count(), 0)
        for producto in Producto.objects.select_related('categoria'):
            self.assertTrue(producto.nombre)
            self.assertLessEqual(len(producto.codigo), 40)
            self.assertLessEqual(len(producto.nombre), 120)
            self.assertLessEqual(len(producto.ubicacion), 100)
            self.assertGreaterEqual(producto.cantidad, 0)
            self.assertGreaterEqual(producto.stock_minimo, 0)
            self.assertTrue(producto.categoria.nombre)

    @override_settings(DEBUG=True)
    def test_carga_no_acumula_sql_de_inserciones_y_restaura_debug(self):
        connection.queries_log.clear()
        self.cargar(50, lote=7, semilla=42)
        consultas = list(connection.queries_log)
        self.assertTrue(settings.DEBUG)
        # La comprobación previa de migraciones puede registrar SELECTs. Las
        # inserciones con todos sus valores no deben crecer con la carga.
        self.assertLess(len(consultas), 10)
        self.assertFalse(any(
            re.match(r'\s*INSERT\b', consulta['sql'], re.I)
            for consulta in consultas
        ))
        self.assertEqual(Producto.objects.count(), 50)
        with self.assertRaises(CommandError):
            self.cargar(0)
        self.assertTrue(settings.DEBUG)

    def test_dos_cargas_suman_sin_reemplazar_datos_ni_duplicar_categorias(self):
        categoria = Categoria.objects.create(nombre='Audio')
        manual = Producto.objects.create(
            codigo='MANUAL-01', nombre='Registro del usuario',
            categoria=categoria, ubicacion='Original', cantidad=17,
        )
        self.cargar(4, lote=3, semilla=5)
        categorias = set(Categoria.objects.values_list('pk', flat=True))
        campos_ficticios = ('nombre', 'categoria_id', 'ubicacion', 'cantidad', 'stock_minimo')
        primera_carga = list(
            Producto.objects.exclude(pk=manual.pk).order_by('pk').values_list(*campos_ficticios)
        )
        self.cargar(4, lote=3, semilla=5)
        self.assertEqual(Producto.objects.count(), 9)
        self.assertEqual(Producto.objects.values('codigo').distinct().count(), 9)
        self.assertEqual(set(Categoria.objects.values_list('pk', flat=True)), categorias)
        self.assertEqual(
            list(Producto.objects.order_by('-pk').values_list(*campos_ficticios)[:4])[::-1],
            primera_carga,
        )
        manual.refresh_from_db()
        self.assertEqual(manual.nombre, 'Registro del usuario')
        self.assertEqual(manual.cantidad, 17)

    def test_argumentos_fuera_de_rango_no_crean_registros(self):
        casos = [
            {'cantidad': 0}, {'cantidad': -1}, {'cantidad': 1_000_001},
            {'cantidad': 2, 'lote': 0}, {'cantidad': 2, 'lote': -1},
            {'cantidad': 2, 'lote': 10_001},
            {'cantidad': 2, 'database': 'alias_inexistente'},
        ]
        for opciones in casos:
            with self.subTest(opciones=opciones):
                with self.assertRaises(CommandError):
                    call_command('cargar_datos', stdout=StringIO(), **opciones)
                self.assertEqual(Categoria.objects.count(), 0)
                self.assertEqual(Producto.objects.count(), 0)
                self.assertEqual(Movimiento.objects.count(), 0)

    def test_movimientos_ficticios_referencian_los_productos_creados(self):
        self.cargar(7, lote=3, semilla=12, con_movimientos=True)
        productos = set(Producto.objects.values_list('pk', flat=True))
        self.assertEqual(len(productos), 7)
        self.assertEqual(Movimiento.objects.count(), 7)
        self.assertEqual(
            set(Movimiento.objects.values_list('producto_id', flat=True)), productos,
        )
        for movimiento in Movimiento.objects.all():
            self.assertEqual(movimiento.tipo, 'INGRESO')
            self.assertGreaterEqual(movimiento.cantidad, 1)
            self.assertEqual(movimiento.cantidad, movimiento.producto.cantidad)

    def test_fallo_revierte_solo_el_lote_actual_y_preserva_los_anteriores(self):
        crear_lote = QuerySet.bulk_create
        lotes_movimientos = 0

        def fallar_segundo_lote(queryset, objetos, *args, **opciones):
            nonlocal lotes_movimientos
            if queryset.model is Movimiento:
                lotes_movimientos += 1
                if lotes_movimientos == 2:
                    raise IntegrityError('Fallo simulado al guardar movimientos')
            return crear_lote(queryset, objetos, *args, **opciones)

        with patch.object(QuerySet, 'bulk_create', autospec=True, side_effect=fallar_segundo_lote):
            with self.assertRaises(CommandError):
                self.cargar(7, lote=3, semilla=10, con_movimientos=True)
        self.assertEqual(Producto.objects.count(), 3)
        self.assertEqual(Movimiento.objects.count(), 3)
        self.assertEqual(
            set(Movimiento.objects.values_list('producto_id', flat=True)),
            set(Producto.objects.values_list('pk', flat=True)),
        )


class VerificacionBaseDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre='Audio')
        Producto.objects.create(
            codigo='LECTURA-01', nombre='Micrófono', categoria=categoria, ubicacion='A1',
        )

    def test_verificacion_consulta_esquema_y_conteos_sin_escribir(self):
        salida = StringIO()
        with CaptureQueriesContext(connection) as consultas:
            call_command('verificar_bd', stdout=salida)
        self.assertIn('Conexión:', salida.getvalue())
        self.assertIn(Producto._meta.db_table, salida.getvalue())
        self.assertEqual(Producto.objects.count(), 1)
        self.assertFalse(any(
            re.match(r'\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b', consulta['sql'], re.I)
            for consulta in consultas
        ))

    def test_verificacion_informa_migraciones_pendientes_sin_aplicarlas(self):
        pendiente = SimpleNamespace(app_label='bodega', name='migracion_pendiente_prueba')
        salida = StringIO()
        with patch(
            'Core.management.commands.verificar_bd.MigrationExecutor.migration_plan',
            return_value=[(pendiente, False)],
        ):
            with self.assertRaises(CommandError):
                call_command('verificar_bd', stdout=salida)
        self.assertIn(pendiente.name, salida.getvalue())
        self.assertEqual(Producto.objects.count(), 1)

    def test_uri_de_archivo_se_rechaza_sin_abrir_la_conexion(self):
        conexion_uri = SimpleNamespace(
            vendor='sqlite', settings_dict={'NAME': 'file:nueva.sqlite3?mode=rwc'},
        )
        with patch('Core.management.commands.verificar_bd.connections', {'default': conexion_uri}):
            with self.assertRaisesMessage(CommandError, 'ruta de archivo normal'):
                call_command('verificar_bd', stdout=StringIO())


class ConsultasAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            'admin-base-datos', password='Clave-de-prueba-123',
        )
        cls.categoria = Categoria.objects.create(nombre='Audio')
        cls.otra_categoria = Categoria.objects.create(nombre='Accesorios')
        cls.bajo = Producto.objects.create(
            codigo='STOCK-BAJO', nombre='Amplificador', categoria=cls.categoria,
            ubicacion='A1', cantidad=9, stock_minimo=10,
        )
        cls.igual = Producto.objects.create(
            codigo='STOCK-IGUAL', nombre='Monitor', categoria=cls.categoria,
            ubicacion='A2', cantidad=3, stock_minimo=3,
        )
        cls.normal = Producto.objects.create(
            codigo='STOCK-NORMAL', nombre='Cable', categoria=cls.otra_categoria,
            ubicacion='B1', cantidad=4, stock_minimo=1,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def ids_productos_admin(self, **filtros):
        respuesta = self.client.get(reverse('admin:bodega_producto_changelist'), filtros)
        self.assertEqual(respuesta.status_code, 200)
        return set(respuesta.context['cl'].queryset.values_list('pk', flat=True))

    def test_filtro_stock_compara_el_minimo_de_cada_producto_incluyendo_igualdad(self):
        self.assertEqual(
            self.ids_productos_admin(stock='critico'), {self.bajo.pk, self.igual.pk},
        )
        self.assertEqual(self.ids_productos_admin(stock='normal'), {self.normal.pk})

    def test_busqueda_y_filtro_categoria_se_combinan(self):
        self.assertEqual(
            self.ids_productos_admin(q='Amplificador', categoria__id__exact=self.categoria.pk),
            {self.bajo.pk},
        )
        self.assertEqual(
            self.ids_productos_admin(q='Amplificador', categoria__id__exact=self.otra_categoria.pk),
            set(),
        )

    def test_busqueda_movimientos_por_codigo_y_tipo(self):
        ingreso = Movimiento.objects.create(
            producto=self.bajo, tipo='INGRESO', cantidad=2, motivo='Recepción',
        )
        Movimiento.objects.create(
            producto=self.bajo, tipo='SALIDA', cantidad=1, motivo='Venta',
        )
        respuesta = self.client.get(reverse('admin:bodega_movimiento_changelist'), {
            'q': self.bajo.codigo, 'tipo__exact': 'INGRESO',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            list(respuesta.context['cl'].queryset.values_list('pk', flat=True)), [ingreso.pk],
        )
