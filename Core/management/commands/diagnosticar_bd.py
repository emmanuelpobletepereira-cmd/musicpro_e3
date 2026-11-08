from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Comprueba la conexión del servidor y sus migraciones sin escribir datos ni revelar credenciales.'
    requires_system_checks = []

    def handle(self, *args, **options):
        if connection.vendor != 'mysql':
            raise CommandError('La conexión del servidor no está seleccionada. Consulta README_WAMP.md para configurar la base.')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                if cursor.fetchone() != (1,):
                    raise CommandError('El servidor no devolvió el resultado esperado.')
                cursor.execute(
                    'SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES '
                    'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = %s '
                    'AND (ENGINE IS NULL OR ENGINE <> %s) ORDER BY TABLE_NAME',
                    ('BASE TABLE', 'InnoDB'),
                )
                incompatibles = cursor.fetchall()
                if incompatibles:
                    tablas = ', '.join(nombre for nombre, _ in incompatibles)
                    raise CommandError(
                        'Hay tablas sin soporte transaccional: ' + tablas + '. '
                        'Su almacenamiento debe corregirse antes de registrar movimientos o despachos.'
                    )
            ejecutor = MigrationExecutor(connection)
            ejecutor.loader.check_consistent_history(connection)
            pendientes = ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
            version = '.'.join(str(parte) for parte in connection.mysql_version)
        except CommandError:
            raise
        except Exception as exc:
            # Algunos errores del conector incluyen usuario/host: no se imprimen.
            raise CommandError(
                f'No se pudo verificar la conexión ({type(exc).__name__}). Revisa el servidor, la versión y las variables de conexión sin compartir la contraseña.'
            ) from None
        self.stdout.write(self.style.SUCCESS(f'Conexión con la base de datos correcta. Servidor {version}.'))
        self.stdout.write(self.style.SUCCESS('Las tablas existentes tienen soporte transaccional.'))
        if pendientes:
            self.stdout.write(self.style.WARNING(f'Migraciones pendientes: {len(pendientes)}. Ejecuta migrate sobre esta conexión y repite el diagnóstico.'))
            for migracion, _ in pendientes:
                self.stdout.write(f'  {migracion.app_label}.{migracion.name}')
        else:
            self.stdout.write(self.style.SUCCESS('No hay migraciones pendientes.'))
