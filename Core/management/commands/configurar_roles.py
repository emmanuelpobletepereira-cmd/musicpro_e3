from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

ROLES = ('Administrador', 'Operador')
PERMISOS_OPERADOR = {
    'producto': ('view', 'add', 'change'),
    'categoria': ('view', 'add', 'change'),
    'proveedor': ('view', 'add', 'change'),
    'sucursal': ('view', 'add', 'change'),
    'solicitud': ('view', 'add', 'change'),
    # Los detalles se gestionan dentro del formulario de la solicitud.
    'detallesolicitud': ('view', 'add', 'change'),
    'movimiento': ('view', 'add'),
}


class Command(BaseCommand):
    help = 'Crea permisos de roles E3; opcionalmente asigna un rol a un usuario existente.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', help='Nombre de un usuario existente; no crea contraseñas.')
        parser.add_argument('--rol', choices=ROLES)

    @transaction.atomic
    def handle(self, *args, **options):
        if bool(options['usuario']) != bool(options['rol']):
            raise CommandError('Indica --usuario y --rol juntos, o no indiques ninguno.')
        usuario = None
        if options['usuario']:
            try:
                usuario = get_user_model().objects.get(username=options['usuario'])
            except get_user_model().DoesNotExist as exc:
                raise CommandError('El usuario no existe. Créalo primero desde Django Admin.') from exc
        modelos = list(apps.get_app_config('bodega').get_models())
        esperados = {
            (modelo._meta.model_name, f'{accion}_{modelo._meta.model_name}')
            for modelo in modelos for accion in modelo._meta.default_permissions
        }
        esperados.update(
            (modelo._meta.model_name, codigo)
            for modelo in modelos for codigo, _ in modelo._meta.permissions
        )
        permisos_negocio = Permission.objects.filter(
            content_type__app_label='bodega',
            content_type__model__in=[modelo._meta.model_name for modelo in modelos],
        )
        disponibles = set(permisos_negocio.values_list('content_type__model', 'codename'))
        if not esperados.issubset(disponibles):
            raise CommandError('Faltan permisos de los modelos de bodega. Ejecuta migrate primero.')
        codigos_usuario = ('view_user', 'add_user', 'change_user')
        permisos_usuario = Permission.objects.filter(
            content_type__app_label='auth', content_type__model='user', codename__in=codigos_usuario,
        )
        if permisos_usuario.count() != len(codigos_usuario):
            raise CommandError('Faltan permisos de usuarios. Ejecuta migrate primero.')
        codigos_operador = {
            f'{accion}_{modelo}'
            for modelo, acciones in PERMISOS_OPERADOR.items() for accion in acciones
        }
        permisos_operador = permisos_negocio.filter(codename__in=codigos_operador)
        if permisos_operador.count() != len(codigos_operador):
            raise CommandError('Faltan los modelos/permisos de la evaluación 3. Ejecuta migrate primero.')
        grupos = {}
        for nombre, permisos in (
            ('Administrador', list(permisos_negocio) + list(permisos_usuario)),
            ('Operador', list(permisos_operador)),
        ):
            grupo, _ = Group.objects.get_or_create(name=nombre)
            grupo.permissions.set(permisos)
            grupos[nombre] = grupo
            self.stdout.write(self.style.SUCCESS(f'{nombre}: {len(permisos)} permisos configurados.'))
        if usuario:
            # Cambia entre estos dos roles; conserva cualquier otro grupo del usuario.
            usuario.groups.remove(*grupos.values())
            usuario.groups.add(grupos[options['rol']])
            self.stdout.write(self.style.SUCCESS(f'Rol {options["rol"]} asignado a {usuario.username}.'))
