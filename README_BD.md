# Base de datos de Bodega

La conexión actual utiliza el servicio local de **WampServer**. La base se llama
**musicpro_e3**, escucha en **127.0.0.1:3306** y se administra desde **HeidiSQL**.
HeidiSQL es el cliente para consultar y administrar los datos; Django se conecta
al servicio de base de datos de WampServer.

Sigue [README_WAMP.md](README_WAMP.md) para abrir la conexión, iniciar la
aplicación y ejecutar los comandos sobre la misma base. Para otra computadora,
usa su apartado **Preparar una copia recién descargada de GitHub**: incluye la
creación de la base y del usuario, la plantilla pública
[`config/conexion.example.json`](config/conexion.example.json), las migraciones
y la creación de una cuenta web nueva. Las contraseñas de este equipo no se publican.

Las dependencias de conexión están en `requirements-bd.txt`; para instalarlas
en el entorno del proyecto utiliza `.\.venv\Scripts\python.exe -m pip install -r requirements-bd.txt`.

```powershell
.\servidor_wamp.bat
.\.venv\Scripts\python.exe wamp.py comprobar
```

El usuario de la aplicación y su contraseña se guardan en
`.wamp-local/config.json`, excluido de Git. Las cuentas para entrar al sitio web
se conservan dentro de la base y son independientes de las credenciales de
administración que introduces en HeidiSQL.

La instancia portátil utilizada antes y SQLite se conservan como antecedentes;
no se sincronizan con la base actual. La instancia portátil permanece detenida,
porque su puerto anterior está ocupado por otro servicio de WampServer. Para
trabajar con los datos actuales utiliza los comandos de `wamp.py`.
