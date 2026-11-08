"""Selecciona la conexión de WampServer o el archivo de desarrollo explícito."""

import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def cargar_conexion_wamp(base_dir):
    archivo = Path(base_dir) / '.wamp-local' / 'config.json'
    try:
        datos = json.loads(archivo.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ImproperlyConfigured(
            'No se pudo leer la conexión de WampServer. Consulta README_WAMP.md.'
        ) from None
    nombres = ('NAME', 'USER', 'PASSWORD', 'HOST', 'PORT')
    if not isinstance(datos, dict) or any(nombre not in datos for nombre in nombres):
        raise ImproperlyConfigured('La conexión de WampServer está incompleta. Consulta README_WAMP.md.')
    valores = {}
    for nombre in nombres:
        valor = datos[nombre]
        if nombre == 'PORT' and type(valor) is int:
            valor = str(valor)
        if not isinstance(valor, str) or not valor.strip():
            raise ImproperlyConfigured(f'El campo {nombre} de la conexión de WampServer no es válido.')
        valores[nombre] = valor
    return valores


def configurar_base_datos(base_dir):
    predeterminado = 'wamp' if (Path(base_dir) / '.wamp-local' / 'config.json').exists() else 'sqlite'
    motor = os.environ.get('MUSICPRO_DB_ENGINE', predeterminado).strip().lower()
    if motor == 'sqlite':
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': Path(os.environ.get('MUSICPRO_DB_PATH', Path(base_dir) / 'db.sqlite3')),
            'OPTIONS': {'timeout': 30},
        }
    if motor == 'wamp':
        valores = cargar_conexion_wamp(base_dir)
    elif motor == 'mysql':
        # Compatibilidad con conexiones definidas mediante variables externas.
        nombres = ('NAME', 'USER', 'PASSWORD', 'HOST', 'PORT')
        valores = {nombre: os.environ.get(f'MUSICPRO_DB_{nombre}', '') for nombre in nombres}
        faltantes = [f'MUSICPRO_DB_{nombre}' for nombre, valor in valores.items() if not valor]
        if faltantes:
            raise ImproperlyConfigured('Faltan variables de conexión: ' + ', '.join(faltantes))
    else:
        raise ImproperlyConfigured('MUSICPRO_DB_ENGINE debe seleccionar SQLite o la conexión de WampServer.')
    try:
        puerto = int(valores['PORT'])
    except ValueError as exc:
        raise ImproperlyConfigured('MUSICPRO_DB_PORT debe ser un entero entre 1 y 65535.') from exc
    if not 1 <= puerto <= 65535:
        raise ImproperlyConfigured('MUSICPRO_DB_PORT debe ser un entero entre 1 y 65535.')
    return {
        'ENGINE': 'django.db.backends.mysql',
        **valores,
        'PORT': str(puerto),
        'OPTIONS': {
            'charset': 'utf8mb4',
            # Las migraciones deben crear tablas transaccionales incluso si
            # la instalación local tiene otro almacenamiento predeterminado.
            'init_command': (
                "SET default_storage_engine='InnoDB', "
                "sql_mode='STRICT_TRANS_TABLES,ONLY_FULL_GROUP_BY,NO_ENGINE_SUBSTITUTION'"
            ),
            'connect_timeout': 10,
        },
    }
