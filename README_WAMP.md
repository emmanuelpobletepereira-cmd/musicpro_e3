# Bodega con WampServer y HeidiSQL

La base preparada en este equipo es **musicpro_e3**, administrada desde HeidiSQL
y alojada en el servicio de WampServer, dirección **127.0.0.1**, puerto **3306**. Django usa el usuario
`musicpro_app`, limitado al esquema del proyecto. Su contraseña aleatoria se
guarda en `.wamp-local/config.json`, excluido de Git.

## Abrir en HeidiSQL

1. Abre Wampserver64 y espera el icono verde.
2. En HeidiSQL, pulsa **Nueva** y nombra la sesión **MusicPro Bodega**.
3. Mantén el tipo de conexión **TCP/IP** para el servidor local.
4. Introduce servidor **127.0.0.1**, usuario **root**, contraseña **vacía** y
   puerto **3306**. Esta conexión local se verificó en esta instalación recién creada.
5. Pulsa **Abrir**. Expande **musicpro_e3** para consultar sus tablas.

La cuenta root es la cuenta local de administración de la base; no es la cuenta
para entrar al sitio web. La aplicación se conecta con su propio usuario
`musicpro_app`. Si cambias la contraseña de root desde HeidiSQL, no necesitas
cambiar la contraseña de la aplicación.

Puedes comprobar los productos en una pestaña de consulta de HeidiSQL:

```sql
USE musicpro_e3;
SELECT codigo, nombre, cantidad AS stock, stock_minimo, estado
FROM bodega_producto
ORDER BY codigo;
```

## Iniciar Django desde VS Code

Detén el servidor anterior con **Ctrl+C** en su terminal. Desde la carpeta del
proyecto ejecuta:

```powershell
.\servidor_wamp.bat
```

También puedes usar `.\servidor.bat`. En este equipo, **F5** tiene una configuración
local que apunta a WampServer; los archivos de VS Code no se publican. Abre
<http://127.0.0.1:8000/> e inicia sesión con la misma cuenta
y contraseña que usabas en SQLite. Es normal tener que iniciar sesión otra vez:
las sesiones abiertas no se transfirieron.

Para comprobar la conexión o ejecutar comandos sobre la misma base:

```powershell
.\.venv\Scripts\python.exe wamp.py comprobar
.\.venv\Scripts\python.exe wamp.py manage verificar_bd
.\.venv\Scripts\python.exe wamp.py manage shell
.\.venv\Scripts\python.exe wamp.py manage createsuperuser
```

`wamp.py` no inicia servicios: WampServer debe estar abierto antes de ejecutar
Django. En este equipo, `manage.py` también selecciona la configuración local
de WampServer. Si esa configuración está dañada, informa el error sin cambiar
de base. `wamp.py manage` fuerza esa misma conexión aunque hayas seleccionado
SQLite en la terminal. SQLite se usa al seleccionarlo explícitamente o en un
equipo sin configuración local.

## Preparar una copia recién descargada de GitHub

El repositorio contiene el código y las migraciones. La base, el entorno virtual,
las cuentas locales y el archivo privado de conexión no se publican. Sigue estos
pasos en un equipo nuevo; no los ejecutes sobre la base ya preparada de este equipo.

1. Instala Python compatible con las dependencias del proyecto (3.12 o superior),
   WampServer y HeidiSQL. Abre WampServer y espera su icono verde. En HeidiSQL,
   conéctate a `127.0.0.1:3306` usando la cuenta de administración y la contraseña
   que configuraste en ese equipo.
2. Desde una pestaña de consulta de HeidiSQL, crea una base nueva y su usuario.
   Sustituye el texto `REEMPLAZAR_CON_TU_CLAVE_LOCAL` por una contraseña propia
   antes de ejecutar el SQL. Usa esa misma contraseña en el archivo del paso 4.
   No copies las credenciales del equipo anterior.

```sql
CREATE DATABASE musicpro_e3 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'musicpro_app'@'127.0.0.1'
  IDENTIFIED BY 'REEMPLAZAR_CON_TU_CLAVE_LOCAL';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
  ON musicpro_e3.* TO 'musicpro_app'@'127.0.0.1';
```

Si ya existe `musicpro_e3` o `musicpro_app`, detente y revisa esa instalación;
estos pasos no borran ni reemplazan una base existente. Los permisos se limitan
al esquema de la aplicación y permiten crear su estructura mediante migraciones.

La aplicación configura almacenamiento transaccional para las tablas nuevas.
El diagnóstico comprueba también las tablas existentes: si informa que alguna
carece de soporte transaccional, respalda la base y corrige su almacenamiento
antes de usar los movimientos o despachos. Esto permite revertir una operación
completa cuando falta stock o falla el guardado.

3. Abre PowerShell en la carpeta del proyecto, donde está `manage.py`, y prepara
   Python. Si `py` no está disponible, usa el ejecutable de Python instalado.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-bd.txt
```

4. Crea la configuración privada a partir de la plantilla pública:

```powershell
if (Test-Path -LiteralPath '.wamp-local\config.json') {
    throw 'La conexión local ya existe. Revísala antes de continuar.'
}
New-Item -ItemType Directory -Path '.wamp-local' -Force | Out-Null
Copy-Item -LiteralPath 'config\conexion.example.json' -Destination '.wamp-local\config.json'
```

Abre `.wamp-local/config.json` en VS Code y cambia `PASSWORD` por la contraseña
del usuario `musicpro_app` creado en el paso 2. Revisa `NAME`, `USER`, `HOST` y
`PORT` si elegiste otros valores. La plantilla tiene un marcador de ejemplo,
no una contraseña válida. `.wamp-local` está excluido de Git.

5. Crea las tablas y los permisos, y registra tu cuenta para entrar al sitio:

```powershell
.\.venv\Scripts\python.exe wamp.py manage migrate
.\.venv\Scripts\python.exe wamp.py manage configurar_roles
.\.venv\Scripts\python.exe wamp.py manage createsuperuser
.\.venv\Scripts\python.exe wamp.py comprobar
.\.venv\Scripts\python.exe wamp.py manage verificar_bd
.\servidor.bat
```

`createsuperuser` solicita los datos de la cuenta web en tu terminal. Después
puedes crear usuarios normales y asignarles Administrador u Operador desde la
pantalla **Usuarios**. Para añadir datos ficticios de práctica, antes de iniciar
el servidor puedes ejecutar:

```powershell
.\.venv\Scripts\python.exe wamp.py manage cargar_demo_bodega
```

La demostración incluye productos, proveedores, sucursales y solicitudes con
distintos estados; no asigna precios. El proyecto ofrece 17 reportes operativos.
Las tres consultas económicas retiradas por petición del usuario se detallan
en [la matriz de alcance](docs/pauta_e3_bodega.md).

## Datos y respaldo de este equipo

Se copiaron desde una instantánea de SQLite los datos de negocio, los usuarios,
los grupos y sus permisos, conservando sus identificadores y hashes de contraseña.
El respaldo y la exportación privada están en `backups/wamp_20261107_211654/`.
No subas esos archivos ni `.wamp-local` a GitHub.

La base SQLite original y la instancia portátil anterior permanecen guardadas;
ya no se sincronizan con WampServer. La instancia portátil anterior
permanece detenida: su puerto anterior 3307 ahora lo usa MariaDB de WampServer.
No inicies la instancia portátil anterior mientras MariaDB ocupe ese puerto.
