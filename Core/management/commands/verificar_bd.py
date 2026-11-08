from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections
from django.db.migrations.executor import MigrationExecutor

class Command(BaseCommand):
    help = 'Verifica conexión, tablas, migraciones y cantidades sin modificar registros.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database', default='default', choices=tuple(connections),
            help='Alias de la base de datos configurada (por defecto: default).',
        )

    def handle(self, *args, **options):
        alias = options['database']
        if alias not in connections:
            raise CommandError(f'No existe el alias de base de datos: {alias}.')
        conexion = connections[alias]
        configuracion = conexion.settings_dict
        nombre = str(configuracion['NAME'])
        if conexion.vendor == 'sqlite' and nombre.startswith('file:'):
            uri = urlsplit(nombre)
            es_memoria = uri.path == ':memory:' or parse_qs(uri.query).get('mode') == ['memory']
            if not es_memoria:
                raise CommandError(
                    'Para diagnosticar SQLite use una ruta de archivo normal, '
                    'no un URI file:. Así se evita crear una base durante la verificación.'
                )
        # Abrir SQLite normalmente crearía el archivo si no existe. Este comando
        # de diagnóstico debe limitarse a inspeccionar una base ya existente.
        if (
            conexion.vendor == 'sqlite'
            and nombre != ':memory:'
            and not nombre.startswith('file:')
            and not Path(nombre).is_file()
        ):
            raise CommandError(
                f'No existe la base SQLite: {nombre}. Ejecute python manage.py migrate.'
            )

        try:
            conexion.ensure_connection()
            with conexion.cursor() as cursor:
                cursor.execute('SELECT 1')
                if cursor.fetchone()[0] != 1:
                    raise CommandError('La consulta de verificación no devolvió el valor esperado.')
                tablas = set(conexion.introspection.table_names(cursor))

            self.stdout.write(self.style.SUCCESS('Conexión correcta (SELECT 1).'))
            self.stdout.write(f'Alias: {alias}')
            tipo_conexion = 'archivo de desarrollo SQLite' if conexion.vendor == 'sqlite' else 'servidor de base de datos'
            self.stdout.write(f'Conexión: {tipo_conexion}')
            self.stdout.write(f'Base de datos: {nombre}')
            self.stdout.write(f'Tablas detectadas: {len(tablas)}')

            modelos = tuple(apps.get_app_config('bodega').get_models())
            tablas_negocio = {modelo._meta.db_table for modelo in modelos}
            presentes = len(tablas_negocio & tablas)
            self.stdout.write(
                f'Tablas propias del negocio: {len(modelos)} '
                f'(presentes en la base: {presentes}).'
            )
            faltantes = []
            for modelo in modelos:
                tabla = modelo._meta.db_table
                if tabla in tablas:
                    self.stdout.write(f'{tabla}: {modelo.objects.using(alias).count()} registros')
                else:
                    faltantes.append(tabla)
                    self.stdout.write(self.style.WARNING(f'{tabla}: tabla pendiente de crear'))

            infraestructura = sorted(tablas - tablas_negocio)
            self.stdout.write(
                f'Tablas de infraestructura de Django: {len(infraestructura)} '
                '(no cuentan como tablas propias del negocio).'
            )
            for tabla in infraestructura:
                self.stdout.write(f'  {tabla}')

            ejecutor = MigrationExecutor(conexion)
            pendientes = ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
            self.stdout.write(f'Migraciones pendientes: {len(pendientes)}')
            for migracion, _ in pendientes:
                self.stdout.write(f'  {migracion.app_label}.{migracion.name}')
            if pendientes or faltantes:
                raise CommandError(
                    'La conexión funciona, pero falta aplicar el esquema. '
                    f'Ejecute python manage.py migrate --database {alias}.'
                )
        except DatabaseError as error:
            raise CommandError(f'No se pudo verificar la base de datos: {error}') from error

        self.stdout.write(self.style.SUCCESS('Esquema actualizado y conteos consultados correctamente.'))
