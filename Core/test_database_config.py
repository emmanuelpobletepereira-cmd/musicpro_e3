import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from musicpro_backend.database_config import configurar_base_datos
from .management.commands.diagnosticar_bd import Command as DiagnosticarConexion


class ConfiguracionBaseDatosTests(SimpleTestCase):
    def setUp(self):
        directorio = TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.base = Path(directorio.name)

    def guardar_conexion(self, **cambios):
        valores = {
            'NAME': 'bodega_prueba', 'USER': 'cuenta_prueba',
            'PASSWORD': 'clave-ficticia-de-prueba', 'HOST': '127.0.0.1', 'PORT': '3306',
        }
        valores.update(cambios)
        archivo = self.base / '.wamp-local' / 'config.json'
        archivo.parent.mkdir(exist_ok=True)
        archivo.write_text(json.dumps(valores), encoding='utf-8')
        return archivo

    @patch.dict(os.environ, {}, clear=True)
    def test_sqlite_es_el_modo_de_desarrollo_sin_conexion_local(self):
        configuracion = configurar_base_datos(self.base)
        self.assertEqual(configuracion['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(configuracion['NAME'], self.base / 'db.sqlite3')

    @patch.dict(os.environ, {}, clear=True)
    def test_conexion_local_tiene_prioridad_sin_cambiar_la_base_por_accidente(self):
        self.guardar_conexion()
        configuracion = configurar_base_datos(self.base)
        self.assertEqual(configuracion['ENGINE'], 'django.db.backends.mysql')
        self.assertEqual(configuracion['NAME'], 'bodega_prueba')
        self.assertEqual(configuracion['PORT'], '3306')
        self.assertIn("default_storage_engine='InnoDB'", configuracion['OPTIONS']['init_command'])

    @patch.dict(os.environ, {'MUSICPRO_DB_ENGINE': 'sqlite'}, clear=True)
    def test_sqlite_explicito_conserva_el_modo_de_desarrollo(self):
        self.guardar_conexion()
        configuracion = configurar_base_datos(self.base)
        self.assertEqual(configuracion['ENGINE'], 'django.db.backends.sqlite3')

    @patch.dict(os.environ, {}, clear=True)
    def test_configuracion_local_invalida_no_se_sustituye_por_sqlite(self):
        archivo = self.guardar_conexion()
        archivo.write_text('{incompleto', encoding='utf-8')
        with self.assertRaisesMessage(ImproperlyConfigured, 'WampServer'):
            configurar_base_datos(self.base)

    @patch.dict(os.environ, {'MUSICPRO_DB_ENGINE': 'wamp'}, clear=True)
    def test_wamp_explicito_exige_archivo_de_conexion(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'WampServer'):
            configurar_base_datos(self.base)

    @patch.dict(os.environ, {}, clear=True)
    def test_campos_nulos_o_puerto_invalido_no_llegan_al_conector(self):
        for cambio in ({'PASSWORD': None}, {'USER': ''}, {'PORT': '65536'}, {'PORT': True}):
            with self.subTest(cambio=cambio):
                self.guardar_conexion(**cambio)
                with self.assertRaises(ImproperlyConfigured):
                    configurar_base_datos(self.base)

    @patch.dict(os.environ, {'MUSICPRO_DB_ENGINE': 'mysql'}, clear=True)
    def test_conexion_externa_incompleta_falla_sin_reemplazarla_por_sqlite(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'MUSICPRO_DB_PASSWORD'):
            configurar_base_datos(self.base)

    def test_conexion_externa_usa_variables_separadas_y_modo_estricto(self):
        variables = {
            'MUSICPRO_DB_ENGINE': 'mysql', 'MUSICPRO_DB_NAME': 'base_prueba',
            'MUSICPRO_DB_USER': 'usuario_prueba', 'MUSICPRO_DB_PASSWORD': 'solo-prueba-no-real',
            'MUSICPRO_DB_HOST': 'servidor.example.test', 'MUSICPRO_DB_PORT': '3306',
        }
        with patch.dict(os.environ, variables, clear=True):
            configuracion = configurar_base_datos(self.base)
        self.assertEqual(configuracion['ENGINE'], 'django.db.backends.mysql')
        self.assertEqual(configuracion['NAME'], 'base_prueba')
        self.assertEqual(configuracion['PORT'], '3306')
        self.assertEqual(configuracion['PASSWORD'], variables['MUSICPRO_DB_PASSWORD'])
        self.assertIn('STRICT_TRANS_TABLES', configuracion['OPTIONS']['init_command'])
        self.assertIn("default_storage_engine='InnoDB'", configuracion['OPTIONS']['init_command'])

    @patch.dict(os.environ, {'MUSICPRO_DB_ENGINE': 'motor-inventado'}, clear=True)
    def test_motor_desconocido_es_un_error_explicito(self):
        with self.assertRaises(ImproperlyConfigured):
            configurar_base_datos(self.base)

    def test_diagnostico_rechaza_tablas_que_no_pueden_revertir_una_transaccion(self):
        with patch('Core.management.commands.diagnosticar_bd.connection') as conexion:
            conexion.vendor = 'mysql'
            cursor = conexion.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            cursor.fetchall.return_value = [('bodega_producto', 'MyISAM')]
            with self.assertRaisesMessage(CommandError, 'bodega_producto'):
                DiagnosticarConexion().handle()
            sentencias = [llamada.args[0].lstrip().upper() for llamada in cursor.execute.call_args_list]
            self.assertTrue(any('INFORMATION_SCHEMA.TABLES' in sentencia for sentencia in sentencias))
            self.assertTrue(all(sentencia.startswith('SELECT') for sentencia in sentencias))
