from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .models import Categoria, DetalleSolicitud, Movimiento, Producto, Solicitud, Sucursal
from .services_bodega import (
    aprobar_solicitud, despachar_solicitud, eliminar_solicitud, guardar_solicitud,
    rechazar_solicitud, registrar_movimiento,
)


class OperacionesStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Instrumentos operaciones')
        cls.producto = Producto.objects.create(
            codigo='OP-01', nombre='Guitarra', categoria=cls.categoria,
            ubicacion='A1', cantidad=10,
        )
        cls.otro = Producto.objects.create(
            codigo='OP-02', nombre='Bajo', categoria=cls.categoria,
            ubicacion='A2', cantidad=2,
        )
        cls.sucursal = Sucursal.objects.create(codigo='SC-01', nombre='Sucursal Centro')
        cls.admin = get_user_model().objects.create_superuser('operaciones-admin', password='Clave-E3-12345')

    def solicitud(self, lineas=None):
        return guardar_solicitud(
            sucursal_id=self.sucursal.pk, observaciones='Prueba',
            lineas=lineas or [(self.producto.pk, 3)],
        )

    def test_movimiento_actualiza_stock_y_registra_traza_inmutable(self):
        ingreso = registrar_movimiento(producto_id=self.producto.pk, tipo='INGRESO', cantidad=5, motivo='Recepción')
        salida = registrar_movimiento(producto_id=self.producto.pk, tipo='SALIDA', cantidad=4, motivo='Entrega')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 11)
        self.assertTrue(ingreso.stock_aplicado)
        with self.assertRaises(ValidationError):
            salida.cantidad = 1
            salida.save()
        with self.assertRaises(ValidationError):
            salida.delete()

    def test_no_hay_stock_negativo_ni_movimiento_invalido(self):
        for cambios in ({'cantidad': 11}, {'cantidad': 0}, {'cantidad': '-2'}, {'cantidad': '1.5'}, {'tipo': 'OTRO'}):
            datos = dict(producto_id=self.producto.pk, tipo='SALIDA', cantidad=1, motivo='Prueba')
            datos.update(cambios)
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                registrar_movimiento(**datos)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 10)
        self.assertFalse(Movimiento.objects.exists())

    def test_fallo_guardando_movimiento_revierte_actualizacion_stock(self):
        with patch('Core.services_bodega.Movimiento.save', side_effect=IntegrityError('Fallo simulado')):
            with self.assertRaises(IntegrityError):
                registrar_movimiento(producto_id=self.producto.pk, tipo='INGRESO', cantidad=2, motivo='Recepción')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 10)

    def test_historico_e2_no_modifica_stock(self):
        movimiento = Movimiento.objects.create(producto=self.producto, tipo='SALIDA', cantidad=2, motivo='Histórico')
        self.assertFalse(movimiento.stock_aplicado)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 10)

    def test_aprobacion_parcial_despacho_y_no_repeticion(self):
        solicitud = self.solicitud()
        detalle = solicitud.detalles.get()
        aprobar_solicitud(solicitud.pk, {detalle.pk: 2})
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 10)
        despachar_solicitud(solicitud.pk)
        self.producto.refresh_from_db()
        detalle.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 8)
        self.assertEqual(detalle.cantidad_despachada, 2)
        self.assertEqual(solicitud.estado, 'DESPACHADA')
        self.assertEqual(solicitud.movimientos.get().cantidad, 2)
        with self.assertRaises(ValidationError):
            despachar_solicitud(solicitud.pk)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 8)
        self.assertEqual(solicitud.movimientos.count(), 1)

    def test_despacho_sin_stock_revierte_todos_los_productos(self):
        solicitud = self.solicitud([(self.producto.pk, 3), (self.otro.pk, 5)])
        aprobar_solicitud(solicitud.pk)
        with self.assertRaises(ValidationError):
            despachar_solicitud(solicitud.pk)
        self.producto.refresh_from_db()
        self.otro.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual((self.producto.cantidad, self.otro.cantidad), (10, 2))
        self.assertEqual(solicitud.estado, 'APROBADA')
        self.assertFalse(solicitud.movimientos.exists())
        self.assertFalse(solicitud.detalles.exclude(cantidad_despachada=0).exists())

    def test_validacion_lineas_y_aprobacion_no_deja_datos_parciales(self):
        with self.assertRaises(ValidationError):
            self.solicitud([(self.producto.pk, 3), (self.producto.pk, 1)])
        self.assertEqual(Solicitud.objects.count(), 0)
        solicitud = self.solicitud()
        detalle = solicitud.detalles.get()
        for cantidades in ({detalle.pk: 4}, {detalle.pk: 0}, {999: 2}):
            with self.subTest(cantidades=cantidades), self.assertRaises(ValidationError):
                aprobar_solicitud(solicitud.pk, cantidades)
        detalle.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(detalle.cantidad_aprobada, 0)
        self.assertEqual(solicitud.estado, 'PENDIENTE')

    def test_estado_rechazado_bloquea_edicion_borrado_y_despacho(self):
        solicitud = self.solicitud()
        rechazar_solicitud(solicitud.pk)
        for operacion in (
            lambda: guardar_solicitud(sucursal_id=self.sucursal.pk, observaciones='Cambio', lineas=[(self.otro.pk, 1)], solicitud_id=solicitud.pk),
            lambda: aprobar_solicitud(solicitud.pk), lambda: eliminar_solicitud(solicitud.pk),
            lambda: despachar_solicitud(solicitud.pk),
        ):
            with self.assertRaises(ValidationError):
                operacion()
        self.assertTrue(Solicitud.objects.filter(pk=solicitud.pk, estado='RECHAZADA').exists())

    def test_bd_impide_cantidades_incoherentes(self):
        solicitud = self.solicitud()
        detalle = solicitud.detalles.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            DetalleSolicitud.objects.filter(pk=detalle.pk).update(cantidad_aprobada=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DetalleSolicitud.objects.filter(pk=detalle.pk).update(cantidad_despachada=1)

    def test_vistas_autorizacion_post_y_csrf(self):
        solicitud = self.solicitud()
        url = reverse('bodega:solicitud_aprobar', args=[solicitud.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        sin_permisos = get_user_model().objects.create_user('operaciones-sin-permiso')
        self.client.force_login(sin_permisos)
        self.assertEqual(self.client.post(url).status_code, 403)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'PENDIENTE')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.admin)
        self.assertEqual(protegido.post(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'APROBADA')

    def test_vistas_crear_consultar_editar_eliminar_solicitud(self):
        self.client.force_login(self.admin)
        url = reverse('bodega:solicitud_crear')
        self.assertEqual(self.client.get(url).status_code, 200)
        respuesta = self.client.post(url, {
            'sucursal': self.sucursal.pk, 'observaciones': 'Pedido web',
            'producto': [self.producto.pk, self.otro.pk], 'cantidad': ['3', '1'],
        })
        self.assertEqual(respuesta.status_code, 302)
        solicitud = Solicitud.objects.get()
        self.assertEqual(solicitud.detalles.count(), 2)
        self.assertContains(self.client.get(reverse('bodega:solicitudes')), self.sucursal.nombre)
        self.assertContains(self.client.get(reverse('bodega:solicitud_detalle', args=[solicitud.pk])), 'Pedido web')
        self.assertEqual(self.client.post(reverse('bodega:solicitud_editar', args=[solicitud.pk]), {
            'sucursal': self.sucursal.pk, 'observaciones': 'Cambio web',
            'producto': [self.producto.pk], 'cantidad': ['4'],
        }).status_code, 302)
        self.assertEqual(solicitud.detalles.get().cantidad_solicitada, 4)
        eliminar = reverse('bodega:solicitud_eliminar', args=[solicitud.pk])
        self.assertEqual(self.client.get(eliminar).status_code, 200)
        self.assertTrue(Solicitud.objects.filter(pk=solicitud.pk).exists())
        self.assertEqual(self.client.post(eliminar).status_code, 302)
        self.assertFalse(Solicitud.objects.filter(pk=solicitud.pk).exists())

    def test_vistas_movimientos_rechazan_entrada_maliciosa_y_muestran_historial(self):
        self.client.force_login(self.admin)
        url = reverse('bodega:movimiento_crear')
        self.assertEqual(self.client.get(url).status_code, 200)
        for cantidad in ('0', '-1', '1.5', '999999999999999999999'):
            self.assertEqual(self.client.post(url, {'producto': self.producto.pk, 'tipo': 'INGRESO', 'cantidad': cantidad, 'motivo': 'Prueba'}).status_code, 200)
        self.assertFalse(Movimiento.objects.exists())
        self.assertEqual(self.client.post(url, {'producto': self.producto.pk, 'tipo': 'INGRESO', 'cantidad': 3, 'motivo': 'Recepción web'}).status_code, 302)
        self.assertContains(self.client.get(reverse('bodega:movimientos')), 'Recepción web')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 13)
