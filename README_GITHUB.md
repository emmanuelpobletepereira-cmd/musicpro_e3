# Actualizar Music Pro en GitHub

El repositorio existente es [emmanuelpobletepereira-cmd/musicpro_e3](https://github.com/emmanuelpobletepereira-cmd/musicpro_e3). La entrega actual contiene las pantallas propias de Bodega, formularios HTML, autenticación, permisos, stock, solicitudes y 17 reportes operativos. La matriz [Pauta E3 aplicada a Bodega](docs/pauta_e3_bodega.md) explica las tres consultas económicas retiradas por petición del usuario.

## Revisar la copia local

Desde PowerShell, en la carpeta que contiene `manage.py`:

```powershell
git status --short
git remote -v
git branch --show-current
git diff --stat
```

`origin` debe apuntar al repositorio indicado. Conserva el historial que ya existe: no vuelvas a ejecutar `preparar_git.py`, no reinicialices Git y no reemplaces los commits anteriores. Una actualización añade commits nuevos; su cantidad no tiene que volver a ser quince.

Antes de preparar archivos, revisa que `.gitignore` excluya el entorno virtual, las bases locales, los respaldos, los registros y los archivos privados de conexión. La plantilla pública `config/conexion.example.json` contiene únicamente valores de ejemplo. La contraseña real se guarda en `.wamp-local/config.json`, que no se publica.

## Probar antes de subir

Abre WampServer y ejecuta las comprobaciones sobre la conexión preparada:

```powershell
.\.venv\Scripts\python.exe wamp.py comprobar
.\.venv\Scripts\python.exe wamp.py manage check
.\.venv\Scripts\python.exe wamp.py manage makemigrations --check --dry-run
```

La suite automatizada usa una base temporal de desarrollo. Selecciona ese modo explícitamente para las pruebas y retira la selección al terminar:

```powershell
$env:MUSICPRO_DB_ENGINE = 'sqlite'
.\.venv\Scripts\python.exe manage.py test Core --noinput
Remove-Item Env:\MUSICPRO_DB_ENGINE
```

Los resultados efectivamente ejecutados se registran en [VERIFICACION.md](VERIFICACION.md). Las pruebas no sustituyen la revisión de los requisitos de la pauta.

## Guardar y publicar la actualización

Primero consulta el remoto y sus cambios, sin sobrescribir su contenido:

```powershell
git fetch origin
git log --oneline --left-right HEAD...origin/main
```

Si aparecen commits remotos que no tienes, revisa e incorpora esos cambios antes de subir. No uses `push --force` para resolver un rechazo.

Selecciona los archivos del proyecto que revisaste. Puedes añadir código, plantillas y documentación por sus rutas; evita incluir archivos ajenos al proyecto. Después inspecciona todo lo preparado:

```powershell
git add --all
git diff --cached --stat
git diff --cached --name-only
git diff --cached
```

`git add --all` prepara los cambios no excluidos de esta copia; si en `git status`
hay archivos ajenos, resuélvelos antes de ejecutarlo o selecciona únicamente las
rutas revisadas con `git add -- RUTA`. Confirma que no aparecen `.wamp-local`,
respaldos, bases de datos ni contraseñas. Crea el commit con un mensaje que
describa la actualización:

```powershell
git commit -m "Actualizar aplicacion de Bodega para E3"
git push origin main
```

Estos comandos presuponen que revisaste la rama `main`, que es la rama de esta copia. Si trabajas en otra rama, publica esa rama y revisa sus cambios antes de integrarlos a `main`. Completa el inicio de sesión de GitHub si Git lo solicita; no pegues contraseñas ni tokens en el chat o en el código.

Cuando termine, comprueba el resultado:

```powershell
git status --short
git log -1 --oneline
git ls-remote origin refs/heads/main
```

Abre el repositorio en GitHub y revisa que el último commit corresponda a la actualización. El código publicado debe incluir `Core/templates`, `Core/static`, las migraciones, `wamp.py`, los lanzadores vigentes y las guías; no incluye los datos privados de este computador.

## Ejecutar lo publicado en otro equipo

Clona el repositorio con Git o descarga su ZIP. Sigue [README_WAMP.md](README_WAMP.md), apartado **Preparar una copia recién descargada de GitHub**, para instalar dependencias, crear una base nueva, completar el archivo privado de conexión y ejecutar las migraciones.

Después inicia la aplicación con:

```powershell
.\servidor.bat
```

Abre <http://127.0.0.1:8000/> y utiliza la cuenta web que creaste en ese equipo. El repositorio no transporta cuentas ni contraseñas de la instalación anterior. Las migraciones y la muestra ficticia permiten reconstruir el esquema y practicar sin publicar bases o respaldos.
