from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UsuariosWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('configurar_roles', stdout=StringIO())
        usuarios = get_user_model()
        cls.admin = usuarios.objects.create_user('admin-personas', password='ClavePersonas-983!')
        cls.admin.groups.add(Group.objects.get(name='Administrador'))
        cls.operador = usuarios.objects.create_user('operador-personas', password='ClaveOperador-183!')
        cls.operador.groups.add(Group.objects.get(name='Operador'))
        cls.tecnico = usuarios.objects.create_superuser('tecnico-personas', password=None)
        cls.staff = usuarios.objects.create_user('staff-personas', is_staff=True, password=None)

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **cambios):
        datos = {
            'username': 'persona-nueva', 'first_name': 'Ana', 'last_name': 'Pérez',
            'email': 'ana@example.test', 'password': 'BosqueAzul-983!Lejos',
            'password_confirm': 'BosqueAzul-983!Lejos', 'rol': 'Operador',
        }
        datos.update(cambios)
        return datos

    def test_anonimo_no_accede_y_operador_no_administra_usuarios_por_post_directo(self):
        rutas = (
            reverse('bodega:usuarios'), reverse('bodega:usuario_crear'),
            reverse('bodega:usuario_editar', args=[self.admin.pk]),
            reverse('bodega:usuario_desactivar', args=[self.admin.pk]),
        )
        self.client.logout()
        for ruta in rutas:
            self.assertEqual(self.client.get(ruta).status_code, 302)
        self.client.force_login(self.operador)
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 403)
                self.assertEqual(self.client.post(ruta, self.datos()).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='persona-nueva').exists())

    def test_crea_cuenta_con_hash_y_solo_el_rol_solicitado(self):
        respuesta = self.client.post(reverse('bodega:usuario_crear'), self.datos())
        self.assertRedirects(respuesta, reverse('bodega:usuarios'))
        persona = get_user_model().objects.get(username='persona-nueva')
        self.assertTrue(persona.check_password('BosqueAzul-983!Lejos'))
        self.assertNotEqual(persona.password, 'BosqueAzul-983!Lejos')
        self.assertEqual(list(persona.groups.values_list('name', flat=True)), ['Operador'])
        self.assertFalse(persona.is_staff)
        self.assertFalse(persona.is_superuser)
        self.assertFalse(persona.has_perm('auth.change_user'))

    def test_post_no_puede_conceder_staff_superuser_o_permisos_individuales(self):
        permiso = Permission.objects.get(content_type__app_label='auth', codename='change_user')
        respuesta = self.client.post(reverse('bodega:usuario_crear'), self.datos(
            is_staff='1', is_superuser='1', user_permissions=str(permiso.pk),
        ))
        self.assertEqual(respuesta.status_code, 302)
        persona = get_user_model().objects.get(username='persona-nueva')
        self.assertFalse(persona.is_staff)
        self.assertFalse(persona.is_superuser)
        self.assertFalse(persona.user_permissions.exists())

    def test_validacion_rechaza_password_debil_diferente_usuario_duplicado_y_rol_invalido(self):
        casos = (
            {'password': '123', 'password_confirm': '123'},
            {'password_confirm': 'diferente'},
            {'username': self.operador.username}, {'email': 'correo-invalido'},
            {'username': 'usuario con espacios'}, {'rol': 'Superusuario'},
        )
        cantidad = get_user_model().objects.count()
        for cambios in casos:
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(reverse('bodega:usuario_crear'), self.datos(**cambios))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(get_user_model().objects.count(), cantidad)
                self.assertNotContains(respuesta, 'BosqueAzul-983!Lejos')

    def test_edita_datos_y_rol_sin_cambiar_password_si_se_deja_vacia(self):
        anterior = self.operador.password
        respuesta = self.client.post(
            reverse('bodega:usuario_editar', args=[self.operador.pk]),
            self.datos(username=self.operador.username, rol='Administrador', password='', password_confirm=''),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.first_name, 'Ana')
        self.assertEqual(self.operador.password, anterior)
        self.assertEqual(list(self.operador.groups.values_list('name', flat=True)), ['Administrador'])
        self.assertTrue(self.operador.has_perm('auth.change_user'))

    def test_cambio_de_rol_quita_permisos_individuales_anteriores(self):
        self.operador.user_permissions.add(Permission.objects.get(
            content_type__app_label='auth', codename='change_user',
        ))
        self.client.post(
            reverse('bodega:usuario_editar', args=[self.operador.pk]),
            self.datos(username=self.operador.username, password='', password_confirm=''),
        )
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.user_permissions.exists())
        self.assertFalse(self.operador.has_perm('auth.change_user'))

    def test_password_propia_se_actualiza_sin_perder_la_sesion(self):
        respuesta = self.client.post(
            reverse('bodega:usuario_editar', args=[self.admin.pk]),
            self.datos(username=self.admin.username, rol='Administrador'),
        )
        self.assertRedirects(respuesta, reverse('bodega:productos'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('BosqueAzul-983!Lejos'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)
        self.assertEqual(self.client.get(reverse('bodega:usuarios')).status_code, 200)

    def test_no_puede_editar_o_desactivar_cuentas_tecnicas(self):
        for cuenta in (self.tecnico, self.staff):
            for nombre in ('usuario_editar', 'usuario_desactivar'):
                with self.subTest(cuenta=cuenta.username, accion=nombre):
                    ruta = reverse(f'bodega:{nombre}', args=[cuenta.pk])
                    self.assertEqual(self.client.get(ruta).status_code, 403)
                    self.assertEqual(self.client.post(ruta, self.datos()).status_code, 403)
            cuenta.refresh_from_db()
            self.assertTrue(cuenta.is_active)

    def test_no_puede_desactivar_la_propia_cuenta(self):
        ruta = reverse('bodega:usuario_desactivar', args=[self.admin.pk])
        self.assertEqual(self.client.get(ruta).status_code, 403)
        self.assertEqual(self.client.post(ruta).status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_desactivacion_es_logica_post_y_bloquea_sesiones_existentes(self):
        cliente_operador = Client()
        cliente_operador.force_login(self.operador)
        ruta = reverse('bodega:usuario_desactivar', args=[self.operador.pk])
        self.assertEqual(self.client.get(ruta).status_code, 200)
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)
        self.assertEqual(self.client.post(ruta).status_code, 302)
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)
        self.assertTrue(get_user_model().objects.filter(pk=self.operador.pk).exists())
        self.assertEqual(cliente_operador.get(reverse('bodega:productos')).status_code, 302)

    def test_formularios_post_de_usuarios_exigen_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        for ruta in (
            reverse('bodega:usuario_crear'),
            reverse('bodega:usuario_editar', args=[self.operador.pk]),
            reverse('bodega:usuario_desactivar', args=[self.operador.pk]),
        ):
            with self.subTest(ruta=ruta):
                self.assertContains(cliente.get(ruta), 'csrfmiddlewaretoken')
                self.assertEqual(cliente.post(ruta, self.datos()).status_code, 403)

    def test_lista_filtra_y_no_muestra_hashes_de_password(self):
        respuesta = self.client.get(reverse('bodega:usuarios'), {'q': 'operador-personas'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([u.pk for u in respuesta.context['pagina']], [self.operador.pk])
        self.assertNotContains(respuesta, self.operador.password)
