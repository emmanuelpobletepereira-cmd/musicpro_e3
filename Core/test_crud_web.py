"""Pruebas del CRUD HTML y sus controles de acceso para la evaluación 3."""

from decimal import Decimal
from io import StringIO
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Categoria, Marca, Movimiento, Producto, Proveedor


# Solo estas pruebas usan un hash rápido; la configuración de la aplicación no cambia.
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DatosWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Instrumentos de prueba')
        cls.otra_categoria = Categoria.objects.create(nombre='Audio de prueba')
        cls.marca = Marca.objects.create(nombre='Marca de prueba')
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor web', rut='11111111-1')
        cls.producto = Producto.objects.create(
            codigo='WEB-001', nombre='Guitarra de prueba', categoria=cls.categoria,
            marca=cls.marca, ubicacion='A1', cantidad=8, stock_minimo=5,
            precio=Decimal('24990.00'), estado='ACTIVO',
        )
        usuarios = get_user_model()
        cls.administrador = usuarios.objects.create_user(
            'administrador-web', password='Clave-web-prueba-123',
        )
        cls.operador = usuarios.objects.create_user('operador-web', password='Clave-web-prueba-123')
        cls.sin_permisos = usuarios.objects.create_user('sin-permisos-web', password='Clave-web-prueba-123')
        cls.lector = usuarios.objects.create_user('lector-web', password='Clave-web-prueba-123')
        for usuario, acciones in (
            (cls.administrador, ('view', 'add', 'change', 'delete')),
            (cls.operador, ('view', 'add', 'change')),
            (cls.lector, ('view',)),
        ):
            usuario.user_permissions.set(Permission.objects.filter(
                content_type__app_label='bodega', content_type__model='producto',
                codename__in=[f'{accion}_producto' for accion in acciones],
            ))

    def datos_producto(self, **cambios):
        datos = {
            'codigo': 'WEB-NUEVO', 'nombre': 'Teclado de prueba',
            'categoria': str(self.categoria.pk), 'marca': str(self.marca.pk),
            'proveedor': str(self.proveedor.pk),
            'ubicacion': 'B2', 'cantidad': '12', 'stock_minimo': '3',
            'estado': 'ACTIVO',
        }
        datos.update(cambios)
        return datos


class AutenticacionWebTests(DatosWebTests):
    def test_anonimo_es_enviado_al_login_desde_cada_vista_protegida(self):
        rutas = (
            reverse('bodega:productos'), reverse('bodega:producto_crear'),
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            reverse('bodega:producto_eliminar', args=[self.producto.pk]),
            reverse('bodega:consultas'),
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 302)
                destino = urlsplit(respuesta.url)
                self.assertEqual(destino.path, reverse('bodega:login'))
                self.assertEqual(parse_qs(destino.query).get('next'), [ruta])

    def test_login_incorrecto_no_crea_sesion(self):
        respuesta = self.client.post(reverse('bodega:login'), {
            'username': self.operador.username, 'password': 'incorrecta',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_valido_recupera_destino_interno_y_logout_invalida_sesion(self):
        destino = reverse('bodega:consultas')
        respuesta = self.client.post(reverse('bodega:login'), {
            'username': self.operador.username, 'password': 'Clave-web-prueba-123',
            'next': destino,
        })
        self.assertRedirects(respuesta, destino, fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.operador.pk)
        self.assertEqual(self.client.get(reverse('bodega:logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        respuesta = self.client.post(reverse('bodega:logout'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_rechaza_next_externo(self):
        for destino in ('https://sitio-ajeno.example/', '//sitio-ajeno.example/'):
            with self.subTest(destino=destino):
                self.client.logout()
                respuesta = self.client.post(reverse('bodega:login'), {
                    'username': self.operador.username, 'password': 'Clave-web-prueba-123',
                    'next': destino,
                })
                self.assertRedirects(
                    respuesta, reverse('bodega:inicio'), fetch_redirect_response=False,
                )

    def test_login_y_operaciones_post_exigen_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(cliente.post(reverse('bodega:login'), {
            'username': self.administrador.username, 'password': 'Clave-web-prueba-123',
        }).status_code, 403)
        cliente.force_login(self.administrador)
        for ruta in (
            reverse('bodega:producto_crear'),
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            reverse('bodega:producto_eliminar', args=[self.producto.pk]),
            reverse('bodega:logout'),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(cliente.post(ruta, self.datos_producto()).status_code, 403)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 8)
        self.assertEqual(Producto.objects.count(), 1)

    def test_formulario_html_emite_csrf_y_permite_un_post_valido(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.administrador)
        respuesta = cliente.get(reverse('bodega:producto_crear'))
        self.assertContains(respuesta, 'csrfmiddlewaretoken')
        token = cliente.cookies['csrftoken'].value
        datos = self.datos_producto(csrfmiddlewaretoken=token)
        respuesta = cliente.post(reverse('bodega:producto_crear'), datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Producto.objects.filter(codigo='WEB-NUEVO').exists())


class PermisosWebTests(DatosWebTests):
    def test_autenticado_sin_permisos_recibe_403_incluso_con_post_directo(self):
        self.client.force_login(self.sin_permisos)
        rutas = (
            reverse('bodega:productos'), reverse('bodega:producto_crear'),
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            reverse('bodega:producto_eliminar', args=[self.producto.pk]),
            reverse('bodega:consultas'),
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 403)
                self.assertEqual(self.client.post(ruta, self.datos_producto()).status_code, 403)
        self.assertEqual(Producto.objects.count(), 1)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.codigo, 'WEB-001')

    def test_lector_consulta_pero_no_puede_modificar_productos(self):
        self.client.force_login(self.lector)
        self.assertEqual(self.client.get(reverse('bodega:productos')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('bodega:consultas')), reverse('bodega:panel_consultas'))
        for ruta in (
            reverse('bodega:producto_crear'),
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            reverse('bodega:producto_eliminar', args=[self.producto.pk]),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.post(ruta, self.datos_producto()).status_code, 403)

    def test_permiso_de_accion_sin_view_tampoco_autoriza(self):
        self.sin_permisos.user_permissions.add(Permission.objects.get(
            content_type__app_label='bodega', codename='add_producto',
        ))
        self.client.force_login(self.sin_permisos)
        respuesta = self.client.post(reverse('bodega:producto_crear'), self.datos_producto())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Producto.objects.filter(codigo='WEB-NUEVO').exists())

    def test_operador_no_elimina_y_administrador_si(self):
        ruta = reverse('bodega:producto_eliminar', args=[self.producto.pk])
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(ruta).status_code, 403)
        self.assertEqual(self.client.post(ruta).status_code, 403)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())
        self.client.force_login(self.administrador)
        self.assertEqual(self.client.post(ruta).status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=self.producto.pk).exists())


class CrudProductosWebTests(DatosWebTests):
    def setUp(self):
        self.client.force_login(self.operador)

    def test_crear_y_editar_producto_sin_precio_con_mensajes(self):
        respuesta = self.client.post(
            reverse('bodega:producto_crear'), self.datos_producto(), follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        producto = Producto.objects.get(codigo='WEB-NUEVO')
        self.assertEqual(producto.precio, Decimal('0.00'))
        self.assertEqual(producto.cantidad, 12)
        self.assertTrue(list(respuesta.context['messages']))
        respuesta = self.client.post(
            reverse('bodega:producto_editar', args=[producto.pk]),
            self.datos_producto(cantidad='4', cantidad_original='12', estado='INACTIVO', marca=''),
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        producto.refresh_from_db()
        self.assertEqual(producto.precio, Decimal('0.00'))
        self.assertEqual(producto.cantidad, 4)
        self.assertEqual(producto.estado, 'INACTIVO')
        self.assertIsNone(producto.marca_id)
        self.assertTrue(list(respuesta.context['messages']))

    def test_ajuste_stock_requiere_existencia_original_y_deja_trazabilidad(self):
        url = reverse('bodega:producto_editar', args=[self.producto.pk])
        for cambios in ({}, {'cantidad_original': '7'}):
            respuesta = self.client.post(url, self.datos_producto(
                codigo='WEB-001', cantidad='6', **cambios,
            ))
            self.assertEqual(respuesta.status_code, 200)
            self.producto.refresh_from_db()
            self.assertEqual(self.producto.cantidad, 8)
            self.assertEqual(Movimiento.objects.count(), 0)
        respuesta = self.client.post(url, self.datos_producto(
            codigo='WEB-001', cantidad='6', cantidad_original='8',
        ))
        self.assertEqual(respuesta.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.cantidad, 6)
        movimiento = Movimiento.objects.get(producto=self.producto)
        self.assertEqual((movimiento.tipo, movimiento.cantidad, movimiento.stock_aplicado), ('SALIDA', 2, True))

    def test_campos_invalidos_no_guardan_y_muestran_el_formulario(self):
        casos = (
            {'nombre': ''}, {'nombre': 'x' * 121}, {'codigo': 'WEB-001'},
            {'cantidad': '-1'}, {'cantidad': '1.5'}, {'stock_minimo': '-1'},
            {'categoria': '99999999'}, {'categoria': 'texto'},
            {'marca': '99999999'}, {'estado': 'INVENTADO'},
        )
        for cambios in casos:
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(
                    reverse('bodega:producto_crear'), self.datos_producto(**cambios),
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'csrfmiddlewaretoken')
                self.assertEqual(Producto.objects.count(), 1)

    def test_edicion_invalida_conserva_el_registro_original(self):
        respuesta = self.client.post(
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            self.datos_producto(codigo='WEB-001', cantidad='-2'),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'Guitarra de prueba')
        self.assertEqual(self.producto.cantidad, 8)

    def test_el_crud_no_permite_alterar_un_precio_historico_por_post(self):
        respuesta = self.client.post(
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            self.datos_producto(codigo='WEB-001', cantidad='8', cantidad_original='8', precio='0.01'),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, Decimal('24990.00'))

    def test_get_no_crea_edita_ni_elimina(self):
        self.client.force_login(self.administrador)
        for ruta in (
            reverse('bodega:producto_crear'),
            reverse('bodega:producto_editar', args=[self.producto.pk]),
            reverse('bodega:producto_eliminar', args=[self.producto.pk]),
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta, self.datos_producto()).status_code, 200)
        self.assertEqual(Producto.objects.count(), 1)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.codigo, 'WEB-001')

    def test_no_elimina_producto_referenciado_por_movimientos(self):
        Movimiento.objects.create(
            producto=self.producto, tipo='INGRESO', cantidad=8, motivo='Prueba web',
        )
        self.client.force_login(self.administrador)
        respuesta = self.client.post(
            reverse('bodega:producto_eliminar', args=[self.producto.pk]), follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())
        self.assertEqual(Movimiento.objects.count(), 1)
        self.assertTrue(list(respuesta.context['messages']))

    def test_ids_inexistentes_devuelven_404(self):
        self.client.force_login(self.administrador)
        for nombre in ('producto_editar', 'producto_eliminar'):
            self.assertEqual(self.client.get(reverse(f'bodega:{nombre}', args=[99999999])).status_code, 404)

    def test_filtros_combinan_busqueda_categoria_estado_y_stock_critico(self):
        objetivo = Producto.objects.create(
            codigo='FIL-001', nombre='Guitarra crítica', categoria=self.categoria,
            ubicacion='C1', cantidad=4, stock_minimo=5,
            precio=Decimal('100.00'), estado='ACTIVO',
        )
        Producto.objects.create(
            codigo='FIL-002', nombre='Guitarra inactiva', categoria=self.categoria,
            ubicacion='C1', cantidad=0, stock_minimo=5,
            precio=Decimal('100.00'), estado='INACTIVO',
        )
        Producto.objects.create(
            codigo='FIL-003', nombre='Guitarra otra categoría', categoria=self.otra_categoria,
            ubicacion='C1', cantidad=0, stock_minimo=5,
            precio=Decimal('100.00'), estado='ACTIVO',
        )
        respuesta = self.client.get(reverse('bodega:productos'), {
            'q': 'guitarra', 'categoria': self.categoria.pk, 'estado': 'ACTIVO', 'critico': '1',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([p.pk for p in respuesta.context['pagina']], [objetivo.pk])
        respuesta = self.client.get(reverse('bodega:productos'), {'q': 'WEB-001'})
        self.assertEqual([p.pk for p in respuesta.context['pagina']], [self.producto.pk])

    def test_listado_pagina_veinte_productos_y_ordena_por_codigo(self):
        Producto.objects.bulk_create([
            Producto(
                codigo=f'PAG-{numero:03}', nombre=f'Producto {numero}',
                categoria=self.categoria, ubicacion='D1', precio=Decimal('1.00'), estado='ACTIVO',
            ) for numero in range(22)
        ])
        respuesta = self.client.get(reverse('bodega:productos'))
        self.assertEqual(len(respuesta.context['pagina']), 20)
        codigos = [p.codigo for p in respuesta.context['pagina']]
        self.assertEqual(codigos, sorted(codigos))
        respuesta = self.client.get(reverse('bodega:productos'), {'page': '2'})
        self.assertEqual(len(respuesta.context['pagina']), 3)


class ConsultasProductosWebTests(DatosWebTests):
    def test_busqueda_devuelve_productos_sin_explicaciones_tecnicas(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('bodega:productos'), {'q': 'Guitarra'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([p.pk for p in respuesta.context['pagina']], [self.producto.pk])
        self.assertNotContains(respuesta, '<pre')
        self.assertContains(respuesta, 'Guitarra de prueba')

    def test_busqueda_no_se_interpreta_como_sql_y_html_se_escapa(self):
        self.client.force_login(self.lector)
        consulta = "' OR 1=1 -- <script>alert(1)</script>"
        respuesta = self.client.get(reverse('bodega:productos'), {'q': consulta})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertEqual(list(respuesta.context['pagina']), [])
        self.assertEqual(Producto.objects.count(), 1)


class ConfigurarRolesTests(TestCase):
    def test_comando_idempotente_configura_y_asigna_roles_sin_hacer_staff(self):
        usuario = get_user_model().objects.create_user('usuario-roles')
        for _ in range(2):
            call_command('configurar_roles', stdout=StringIO())
        self.assertEqual(Group.objects.filter(name__in=['Administrador', 'Operador']).count(), 2)
        for nombre, acciones in (
            ('Administrador', ('view', 'add', 'change', 'delete')),
            ('Operador', ('view', 'add', 'change')),
        ):
            grupo = Group.objects.get(name=nombre)
            codigos = set(grupo.permissions.filter(
                content_type__app_label='bodega', content_type__model='producto',
            ).values_list('codename', flat=True))
            self.assertEqual(codigos, {f'{accion}_producto' for accion in acciones})
        call_command(
            'configurar_roles', usuario=usuario.username, rol='Operador', stdout=StringIO(),
        )
        usuario.refresh_from_db()
        self.assertTrue(usuario.groups.filter(name='Operador').exists())
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.has_perm('bodega.change_producto'))
        self.assertFalse(usuario.has_perm('bodega.delete_producto'))
