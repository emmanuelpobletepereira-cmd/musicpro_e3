# Music Pro · Bodega

Aplicación de gestión de inventario y solicitudes de sucursales para la evaluación 3. Incluye pantallas propias para productos, categorías, proveedores, sucursales, movimientos, solicitudes y usuarios, con formularios HTML, autenticación y permisos en el servidor.

La conexión preparada utiliza la base **musicpro_e3** de WampServer en **127.0.0.1:3306**, administrada desde **HeidiSQL**. La aplicación ofrece **17 reportes ORM operativos**, sin precios en las pantallas de Bodega. Por petición del usuario se retiraron las consultas económicas 4, 14 y 18 de la pauta original; esta versión no cubre esos tres reportes. Consulta el alcance en [Pauta E3 aplicada a Bodega](docs/pauta_e3_bodega.md).

## Iniciar la instalación preparada

Abre WampServer y espera a que su icono esté verde. Desde PowerShell, en la carpeta que contiene `manage.py`, ejecuta:

```powershell
.\servidor.bat
```

Entra a <http://127.0.0.1:8000/> con tu cuenta web y conserva abierta la terminal. Para detener Django pulsa **Ctrl+C**. Si el puerto 8000 está ocupado, utiliza `.\servidor.bat 8001` y abre <http://127.0.0.1:8001/>.

El lanzador usa Python de `.venv` y la configuración privada de WampServer. En este equipo, `manage.py` también selecciona esa conexión local; una configuración dañada produce un error y no cambia a otra base.

## Preparar una copia descargada de GitHub

El repositorio publica código, migraciones y una plantilla de conexión sin contraseñas reales. La base, las cuentas, los respaldos y la configuración privada de este equipo no se incluyen.

Sigue [Preparar una copia recién descargada de GitHub](README_WAMP.md#preparar-una-copia-recién-descargada-de-github) para instalar las dependencias, crear una base nueva, completar `.wamp-local/config.json` a partir de [la plantilla pública](config/conexion.example.json), aplicar las migraciones y crear tu cuenta web. Después podrás iniciar con `servidor.bat`.

## Funciones del sistema

| Pantalla | Funciones |
| --- | --- |
| Inventario | Buscar y filtrar productos; consultar su ficha; crear, editar y eliminar registros sin relaciones protegidas. Stock, mínimo, ubicación, proveedor y estado. |
| Categorías, proveedores y sucursales | Consultar y mantener los catálogos mediante formularios propios. |
| Solicitudes | Crear pedidos con varios productos, revisar cantidades, aprobar, rechazar y despachar. |
| Movimientos | Registrar entradas y salidas, actualizar existencias y conservar su trazabilidad. |
| Usuarios | Crear cuentas normales, modificar datos y rol, cambiar contraseña y desactivar el acceso. |
| Reportes | Ejecutar 17 consultas operativas con filtros, resultados reales y paginación. |

Los perfiles **Administrador** y **Operador** tienen permisos diferenciados. Las vistas comprueban la sesión y los permisos efectivos; la autorización no depende de ocultar botones. Los formularios procesan campos permitidos de `request.POST`, validan las entradas y usan CSRF. No utilizan `ProductoForm` ni `ModelForm` en estas pantallas.

Las operaciones de stock y despacho usan transacciones. El sistema impide salidas mayores a las existencias y evita despachar dos veces una solicitud. Las modificaciones y el cierre de sesión se realizan mediante POST.

El esquema conserva trece tablas propias. Las entidades principales del caso son Producto, Categoria, Proveedor, Sucursal, Solicitud, DetalleSolicitud y Movimiento; las otras tablas corresponden a los antecedentes de la aplicación. Los datos históricos se conservan. La administración de E3 se demuestra desde las pantallas propias; Django Admin permanece como antecedente y no forma parte de su menú.

## Consultas ORM

Las consultas están implementadas en [Core/reportes.py](Core/reportes.py). Por ejemplo, `productos_bajo_minimo` selecciona productos con existencias inferiores a su mínimo mediante `filter(cantidad__lt=F('stock_minimo'))`.

Puedes ver sus resultados en **Reportes → Productos con stock por debajo del mínimo**. La explicación del código está en [explicacion_query_bodega.md](docs/explicacion_query_bodega.md), separada de la interfaz.

## Comprobar la instalación

Con WampServer abierto:

```powershell
.\.venv\Scripts\python.exe wamp.py comprobar
.\.venv\Scripts\python.exe wamp.py manage verificar_bd
.\.venv\Scripts\python.exe wamp.py manage check
.\.venv\Scripts\python.exe wamp.py manage makemigrations --check --dry-run
```

Las pruebas automatizadas utilizan una base temporal. Para ejecutarlas en el modo de desarrollo:

```powershell
$env:MUSICPRO_DB_ENGINE = 'sqlite'
.\.venv\Scripts\python.exe manage.py test Core --noinput
Remove-Item Env:\MUSICPRO_DB_ENGINE
```

Los resultados de las comprobaciones realmente ejecutadas se registran en [VERIFICACION.md](VERIFICACION.md). La selección final de las diez consultas pedidas para la defensa debe confirmarse con el docente; la sección Bodega de la pauta contiene veinte preguntas y tres económicas fueron retiradas por decisión del usuario.

## Documentación de la entrega

| Documento | Contenido |
| --- | --- |
| [README_E3.md](README_E3.md) | Alcance, roles, flujos de Bodega y recorrido para presentar la aplicación |
| [README_WAMP.md](README_WAMP.md) | Conexión con HeidiSQL, arranque y preparación completa de otro equipo |
| [README_BD.md](README_BD.md) | Resumen de la base y sus credenciales locales |
| [Pauta E3 aplicada a Bodega](docs/pauta_e3_bodega.md) | Requisitos, evidencias y diferencias de alcance |
| [Diagrama Bodega E3](docs/diagrama_bodega_e3.md) | Entidades, atributos y relaciones; incluye [imagen PNG](docs/diagrama_bodega_e3.png) y [SVG](docs/diagrama_bodega_e3.svg) |
| [Explicación de las consultas](docs/explicacion_query_bodega.md) | Ejemplos ORM para estudiar y explicar |
| [Adaptación del ejemplo docente](docs/replica_profesor.md) | Equivalencias entre el repositorio de referencia y este caso |
| [VERIFICACION.md](VERIFICACION.md) | Resultados y antecedentes de las comprobaciones |
| [README_GITHUB.md](README_GITHUB.md) | Actualizar el repositorio conservando su historial |

La carpeta `.wamp-local`, los archivos `.env`, el entorno virtual, las bases y los respaldos están excluidos de Git. Utiliza [README_GITHUB.md](README_GITHUB.md) para revisar y publicar el código de la entrega sin incluir esos datos privados.
