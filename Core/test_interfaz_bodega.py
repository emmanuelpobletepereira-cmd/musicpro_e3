"""La interfaz presenta operaciones del negocio, sin material de estudio."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Categoria, DetalleSolicitud, Producto, Proveedor, Solicitud, Sucursal


class InterfazBodegaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser('interfaz-bodega', password=None)
        categoria = Categoria.objects.create(nombre='Instrumentos')
        proveedor = Proveedor.objects.create(nombre='Proveedor de instrumentos', rut='INTERFAZ-01')
        cls.producto = Producto.objects.create(
            codigo='INTERFAZ-01', nombre='Guitarra', categoria=categoria,
            proveedor=proveedor, ubicacion='A1', cantidad=2,
        )
        sucursal = Sucursal.objects.create(codigo='CENTRO', nombre='Sucursal Centro')
        cls.solicitud = Solicitud.objects.create(sucursal=sucursal)
        DetalleSolicitud.objects.create(solicitud=cls.solicitud, producto=cls.producto, cantidad_solicitada=1)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_pantallas_del_negocio_sin_guias_codigo_ni_referencias_docentes(self):
        rutas = [reverse(f'bodega:{nombre}') for nombre in (
            'inicio', 'productos', 'producto_crear', 'panel_consultas',
            'movimientos', 'movimiento_crear', 'solicitudes', 'solicitud_crear',
            'usuarios', 'usuario_crear',
        )]
        rutas += [reverse(f'bodega:{nombre}', args=[self.producto.pk]) for nombre in (
            'producto_detalle', 'producto_editar', 'producto_eliminar',
        )]
        rutas += [reverse('bodega:solicitud_detalle', args=[self.solicitud.pk])]
        rutas += [reverse('bodega:catalogo_lista', args=[tipo]) for tipo in (
            'categorias', 'proveedores', 'sucursales',
        )]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                for fragmento in ('<pre', '<code', 'QUERY', 'QuerySet', 'Guía CRUD',
                                  'Del modelo al CRUD seguro', 'profesor', '/guia-crud/',
                                  'Base de datos:', 'Precio', 'precio', '$'):
                    self.assertNotContains(respuesta, fragmento)

    def test_guia_retirada_y_direccion_antigua_de_consultas_abre_reportes(self):
        self.assertEqual(self.client.get('/guia-crud/').status_code, 404)
        self.assertRedirects(self.client.get(reverse('bodega:consultas')), reverse('bodega:panel_consultas'))

    def test_reporte_de_stock_sigue_filtrando_datos_reales(self):
        respuesta = self.client.get(reverse('bodega:reportes'), {'n': 3})
        self.assertContains(respuesta, self.producto.codigo)
        self.assertEqual([fila[0] for fila in respuesta.context['filas']], [self.producto.codigo])
        self.assertNotContains(respuesta, '<pre')
        self.assertNotContains(respuesta, 'ORM')
        self.assertNotContains(respuesta, 'SQL')
        self.assertNotIn('consultas', respuesta.context)
