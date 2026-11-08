from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Categoria, Producto, Proveedor, Solicitud, Sucursal


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CatalogosWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('configurar_roles', stdout=StringIO())
        cls.admin = get_user_model().objects.create_user('admin-catalogos')
        cls.admin.groups.add(Group.objects.get(name='Administrador'))
        cls.operador = get_user_model().objects.create_user('operador-catalogos')
        cls.operador.groups.add(Group.objects.get(name='Operador'))
        cls.sin_permisos = get_user_model().objects.create_user('sin-permisos-catalogos')
        cls.categoria = Categoria.objects.create(nombre='Categoría existente', descripcion='Original')
        cls.proveedor = Proveedor.objects.create(nombre='Proveedor existente', rut='11111111-1')
        cls.sucursal = Sucursal.objects.create(codigo='SUC-EXISTE', nombre='Sucursal existente')

    def setUp(self):
        self.client.force_login(self.admin)

    def catalogos(self):
        return (
            ('categorias', Categoria, self.categoria),
            ('proveedores', Proveedor, self.proveedor),
            ('sucursales', Sucursal, self.sucursal),
        )

    def datos(self, tipo, **cambios):
        datos = {
            'categorias': {'nombre': 'Categoría nueva', 'descripcion': 'Descripción nueva'},
            'proveedores': {
                'nombre': 'Proveedor nuevo', 'rut': '22222222-2', 'email': 'proveedor@example.test',
                'telefono': '+56912345678', 'direccion': 'Calle de prueba 123', 'activo': '1',
            },
            'sucursales': {
                'codigo': 'SUC-NUEVA', 'nombre': 'Sucursal nueva',
                'direccion': 'Avenida de prueba 321', 'activa': '1',
            },
        }[tipo].copy()
        datos.update(cambios)
        return datos

    def ruta(self, accion, tipo, objeto=None):
        argumentos = [tipo] if objeto is None else [tipo, objeto.pk]
        return reverse(f'bodega:catalogo_{accion}', args=argumentos)

    def test_anonimo_es_redirigido_al_login_en_todos_los_catalogos(self):
        self.client.logout()
        for tipo, _, objeto in self.catalogos():
            for accion in ('lista', 'crear', 'editar', 'eliminar'):
                with self.subTest(tipo=tipo, accion=accion):
                    ruta = self.ruta(accion, tipo, objeto if accion in ('editar', 'eliminar') else None)
                    respuesta = self.client.get(ruta)
                    self.assertEqual(respuesta.status_code, 302)
                    self.assertIn(reverse('bodega:login'), respuesta.url)

    def test_usuario_sin_permisos_no_lee_ni_modifica_por_post_directo(self):
        self.client.force_login(self.sin_permisos)
        for tipo, modelo, objeto in self.catalogos():
            self.assertEqual(self.client.get(self.ruta('lista', tipo)).status_code, 403)
            for accion in ('crear', 'editar', 'eliminar'):
                with self.subTest(tipo=tipo, accion=accion):
                    ruta = self.ruta(accion, tipo, objeto if accion != 'crear' else None)
                    self.assertEqual(self.client.get(ruta).status_code, 403)
                    self.assertEqual(self.client.post(ruta, self.datos(tipo)).status_code, 403)
            self.assertEqual(modelo.objects.count(), 1)
            objeto.refresh_from_db()
            self.assertIn('existente', objeto.nombre)

    def test_permiso_de_accion_tambien_requiere_permiso_de_consulta(self):
        self.sin_permisos.user_permissions.add(Permission.objects.get(
            content_type__app_label='bodega', codename='add_categoria',
        ))
        self.client.force_login(self.sin_permisos)
        respuesta = self.client.post(self.ruta('crear', 'categorias'), self.datos('categorias'))
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Categoria.objects.count(), 1)

    def test_operador_puede_registrar_pero_no_eliminar_catalogos(self):
        self.client.force_login(self.operador)
        for tipo, modelo, objeto in self.catalogos():
            with self.subTest(tipo=tipo):
                self.assertEqual(self.client.get(self.ruta('lista', tipo)).status_code, 200)
                self.assertEqual(self.client.post(self.ruta('crear', tipo), self.datos(tipo)).status_code, 302)
                self.assertEqual(self.client.get(self.ruta('editar', tipo, objeto)).status_code, 200)
                self.assertEqual(self.client.post(self.ruta('eliminar', tipo, objeto)).status_code, 403)
                self.assertEqual(modelo.objects.count(), 2)

    def test_administrador_crea_edita_y_desactiva_proveedor_y_sucursal(self):
        for tipo, modelo, _ in self.catalogos():
            with self.subTest(tipo=tipo):
                respuesta = self.client.post(self.ruta('crear', tipo), self.datos(tipo), follow=True)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(list(respuesta.context['messages']))
                nuevo = modelo.objects.get(nombre=self.datos(tipo)['nombre'])
                datos = self.datos(tipo, nombre='Nombre actualizado')
                if tipo == 'proveedores':
                    self.assertTrue(nuevo.activo)
                    datos.pop('activo')
                if tipo == 'sucursales':
                    self.assertTrue(nuevo.activa)
                    datos.pop('activa')
                respuesta = self.client.post(self.ruta('editar', tipo, nuevo), datos)
                self.assertRedirects(respuesta, self.ruta('lista', tipo))
                nuevo.refresh_from_db()
                self.assertEqual(nuevo.nombre, 'Nombre actualizado')
                if tipo == 'proveedores':
                    self.assertFalse(nuevo.activo)
                if tipo == 'sucursales':
                    self.assertFalse(nuevo.activa)

    def test_campos_invalidos_y_duplicados_no_crean_registros(self):
        casos = (
            ('categorias', {'nombre': ''}),
            ('categorias', {'nombre': 'x' * 81}),
            ('categorias', {'nombre': self.categoria.nombre}),
            ('proveedores', {'rut': self.proveedor.rut}),
            ('proveedores', {'email': 'correo-no-valido'}),
            ('proveedores', {'nombre': ''}),
            ('sucursales', {'codigo': self.sucursal.codigo}),
            ('sucursales', {'codigo': 'x' * 31}),
            ('sucursales', {'nombre': ''}),
        )
        modelos = {tipo: modelo for tipo, modelo, _ in self.catalogos()}
        for tipo, cambios in casos:
            with self.subTest(tipo=tipo, cambios=cambios):
                respuesta = self.client.post(self.ruta('crear', tipo), self.datos(tipo, **cambios))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(modelos[tipo].objects.count(), 1)
                self.assertTrue(list(respuesta.context['messages']))

    def test_edicion_invalida_conserva_el_registro_guardado(self):
        for tipo, _, objeto in self.catalogos():
            with self.subTest(tipo=tipo):
                nombre = objeto.nombre
                respuesta = self.client.post(self.ruta('editar', tipo, objeto), self.datos(tipo, nombre=''))
                self.assertEqual(respuesta.status_code, 200)
                objeto.refresh_from_db()
                self.assertEqual(objeto.nombre, nombre)

    def test_get_de_formularios_no_crea_edita_o_elimina(self):
        for tipo, modelo, objeto in self.catalogos():
            nombre = objeto.nombre
            for accion in ('crear', 'editar', 'eliminar'):
                with self.subTest(tipo=tipo, accion=accion):
                    ruta = self.ruta(accion, tipo, objeto if accion != 'crear' else None)
                    self.assertEqual(self.client.get(ruta, self.datos(tipo)).status_code, 200)
            self.assertEqual(modelo.objects.count(), 1)
            objeto.refresh_from_db()
            self.assertEqual(objeto.nombre, nombre)

    def test_referencias_protegen_categoria_proveedor_y_sucursal_del_borrado(self):
        producto = Producto.objects.create(
            codigo='CAT-PROTEGIDO', nombre='Producto protegido', ubicacion='A1',
            categoria=self.categoria, proveedor=self.proveedor,
        )
        solicitud = Solicitud.objects.create(sucursal=self.sucursal)
        for tipo, modelo, objeto in self.catalogos():
            with self.subTest(tipo=tipo):
                respuesta = self.client.post(self.ruta('eliminar', tipo, objeto))
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())
                self.assertTrue(list(respuesta.context['messages']))
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())
        self.assertTrue(Solicitud.objects.filter(pk=solicitud.pk).exists())

    def test_post_borra_registros_sin_referencias(self):
        for tipo, modelo, objeto in self.catalogos():
            with self.subTest(tipo=tipo):
                respuesta = self.client.post(self.ruta('eliminar', tipo, objeto))
                self.assertRedirects(respuesta, self.ruta('lista', tipo))
                self.assertFalse(modelo.objects.filter(pk=objeto.pk).exists())

    def test_formularios_incluyen_csrf_y_rechazan_post_sin_token(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        for tipo, modelo, objeto in self.catalogos():
            for accion in ('crear', 'editar', 'eliminar'):
                with self.subTest(tipo=tipo, accion=accion):
                    ruta = self.ruta(accion, tipo, objeto if accion != 'crear' else None)
                    self.assertContains(cliente.get(ruta), 'csrfmiddlewaretoken')
                    self.assertEqual(cliente.post(ruta, self.datos(tipo)).status_code, 403)
            self.assertEqual(modelo.objects.count(), 1)

    def test_catalogos_y_registros_desconocidos_devuelven_404(self):
        self.assertEqual(self.client.get(self.ruta('lista', 'usuarios')).status_code, 404)
        for tipo, _, _ in self.catalogos():
            for accion in ('editar', 'eliminar'):
                self.assertEqual(self.client.get(reverse(
                    f'bodega:catalogo_{accion}', args=[tipo, 99999999],
                )).status_code, 404)

    def test_busqueda_y_paginacion_consultan_solo_los_registros_filtrados(self):
        Categoria.objects.bulk_create([
            Categoria(nombre=f'Catálogo paginado {numero:02}') for numero in range(22)
        ])
        ruta = self.ruta('lista', 'categorias')
        respuesta = self.client.get(ruta, {'q': 'Catálogo paginado'})
        self.assertEqual(respuesta.context['pagina'].paginator.count, 22)
        self.assertEqual(len(respuesta.context['pagina']), 20)
        nombres = [objeto.nombre for objeto in respuesta.context['pagina']]
        self.assertEqual(nombres, sorted(nombres))
        respuesta = self.client.get(ruta, {'q': 'Catálogo paginado', 'page': '2'})
        self.assertEqual(len(respuesta.context['pagina']), 2)
