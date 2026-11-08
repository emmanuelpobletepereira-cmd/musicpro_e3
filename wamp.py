"""Ejecuta Django con la conexión local de WampServer."""

import os
from pathlib import Path
import sys


BASE = Path(__file__).resolve().parent
CONFIG = BASE / '.wamp-local' / 'config.json'


def main():
    if not CONFIG.is_file():
        print('Falta la conexión de WampServer. Consulta README_WAMP.md.', file=sys.stderr)
        return 1
    os.environ['MUSICPRO_DB_ENGINE'] = 'wamp'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'musicpro_backend.settings')
    accion = sys.argv[1] if len(sys.argv) > 1 else 'comprobar'
    argumentos = sys.argv[2:]
    if accion == 'servidor':
        enlace = argumentos.pop(0) if argumentos and not argumentos[0].startswith('-') else '127.0.0.1:8000'
        if enlace.isdecimal():
            enlace = '127.0.0.1:' + enlace
        argumentos = ['runserver', enlace, *argumentos]
    elif accion == 'comprobar':
        argumentos = ['diagnosticar_bd']
    elif accion != 'manage' or not argumentos:
        print('Uso: wamp.py comprobar|servidor [puerto]|manage <comando Django>', file=sys.stderr)
        return 1

    from django.core.management import execute_from_command_line
    execute_from_command_line([str(BASE / 'manage.py'), *argumentos])
    return 0


if __name__ == '__main__':
    sys.exit(main())
