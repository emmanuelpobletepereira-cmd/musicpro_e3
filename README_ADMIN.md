# Administrar la bodega con Django Admin

Esta guía conserva el recorrido de Django Admin de la evaluación 2. Para la entrega actual de E3 se utilizan las pantallas propias descritas en [README_E3.md](README_E3.md). Los ejemplos siguientes preparan una base SQLite de ensayo independiente; la conexión habitual de este equipo apunta a WampServer.

## Iniciar y acceder

Con el entorno virtual activado y dentro de la carpeta de `manage.py`:

```powershell
$motorAdminAnterior = $env:MUSICPRO_DB_ENGINE
$rutaAdminAnterior = $env:MUSICPRO_DB_PATH
$archivoEnsayoAdmin = Join-Path (Get-Location) ('admin-ensayo-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
try {
    $env:MUSICPRO_DB_ENGINE = 'sqlite'
    $env:MUSICPRO_DB_PATH = $archivoEnsayoAdmin
    python manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la base de ensayo.' }
    python manage.py cargar_datos --cantidad 100 --semilla 42 --completo
    if ($LASTEXITCODE -ne 0) { throw 'No se completó la carga ficticia.' }
    python manage.py createsuperuser
    if ($LASTEXITCODE -ne 0) { throw 'No se creó la cuenta de ensayo.' }
    python manage.py runserver
} finally {
    if ($null -eq $motorAdminAnterior) { Remove-Item Env:\MUSICPRO_DB_ENGINE -ErrorAction SilentlyContinue }
    else { $env:MUSICPRO_DB_ENGINE = $motorAdminAnterior }
    if ($null -eq $rutaAdminAnterior) { Remove-Item Env:\MUSICPRO_DB_PATH -ErrorAction SilentlyContinue }
    else { $env:MUSICPRO_DB_PATH = $rutaAdminAnterior }
}
```

- `migrate` crea o actualiza las tablas, incluidos usuarios y permisos.
- `createsuperuser` crea una cuenta administradora; no muestra los caracteres de la contraseña al escribirla.
- `runserver` inicia el servidor. Abre [el administrador](http://127.0.0.1:8000/admin/) e inicia sesión. `Ctrl+C` detiene el servidor.

Las credenciales pertenecen al archivo de ensayo seleccionado dentro del bloque, no a la base habitual. Al detener el servidor con Ctrl+C, `finally` restaura los valores anteriores de ambas variables. El archivo de ensayo se conserva para consultarlo después.

## Cómo se configura

Los registros `@admin.register(...)` y las clases `ModelAdmin` de [Core/admin.py](Core/admin.py) controlan estas pantallas. No se necesitan paquetes adicionales.

| Configuración | Resultado en Music Pro |
| --- | --- |
| `list_display` | Columnas de las diez entidades de bodega |
| `list_filter` | Productos por categoría y stock; movimientos por tipo y fecha |
| `search_fields` | Búsquedas por nombre, código, ubicación o motivo, según el modelo |
| `fieldsets` | Formularios divididos en secciones para identificar los datos y existencias |
| `readonly_fields` | Identificador visible sin edición manual |
| `autocomplete_fields` | Selección de productos y demás relaciones por búsqueda |
| `inlines` | Detalles de compras y ventas dentro de su documento; también tienen listado propio |
| `list_select_related` | Obtención de las relaciones al consultar el listado |
| `list_per_page` | Listados de productos y movimientos con 50 registros por página |
| `date_hierarchy` | Navegación por fecha en movimientos |
| `site_header`, `site_title`, `index_title` | Nombre y encabezados propios de la bodega |

La columna calculada **Stock crítico** y el filtro con ese nombre comparan `cantidad <= stock_minimo`. No añaden una columna a SQLite. Las búsquedas del movimiento usan campos de su producto mediante `producto__codigo` y `producto__nombre`.

## Recorrido para la defensa

Realiza esta secuencia con registros de demostración. Si el código `DEMO-001` ya existe, utiliza otro código libre.

1. En **Categorías**, crea `Prueba docente`. Abre su ficha y muestra el identificador asignado por Django.
2. En **Productos**, crea `DEMO-001`, nombre `Guitarra de prueba`, categoría `Prueba docente`, ubicación `Pasillo 1`, cantidad `10` y stock mínimo `5`. Explica que la categoría es una clave foránea.
3. Consulta el producto por el buscador con `DEMO-001`, filtra por categoría y muestra sus datos guardados.
4. Edita la ubicación a `Pasillo 2` y la cantidad a `3`. Guarda y elige el filtro **Crítico**: ahora el producto cumple `3 <= 5`.
5. En **Movimientos**, crea un `INGRESO` para ese producto, cantidad `3` y motivo `Demostración`. Filtra por tipo y fecha; busca el código del producto.
6. Intenta guardar un movimiento con cantidad `0`. El formulario debe rechazarlo. Intenta eliminar el producto con el movimiento asociado: Django debe mostrar que está protegido.
7. Elimina primero el movimiento de demostración, luego el producto y finalmente la categoría. Confirma los borrados y consulta otra vez el código.

**El stock se administra manualmente.** El movimiento del paso 5 registra un ingreso, pero no ejecuta una actualización automática de `Producto.cantidad`. Editar o eliminar movimientos tampoco recalcula las existencias.

Para verificar desde otra terminal, activada sobre la misma base:

```powershell
python manage.py shell -c "from Core.models import Producto; print(list(Producto.objects.filter(codigo='DEMO-001').values('codigo', 'ubicacion', 'cantidad', 'categoria__nombre')))"
```

Antes de borrar, la consulta debe mostrar los valores guardados; después debe devolver `[]`. `shell -c` ejecuta esa consulta ORM con la configuración del proyecto. Usa también `python manage.py verificar_bd` antes y después para comparar conteos globales.

## Ubicar los diez modelos y seguir una venta

En la página inicial de Admin, la sección **Bodega** muestra **Categorías, Marcas, Proveedores, Clientes, Productos, Compras, Detalles de compras, Ventas, Detalles de ventas y Movimientos**. Son diez tablas propias. Usuarios y Grupos pertenecen a la autenticación de Django.

Para disponer de ejemplos relacionados en todas las tablas:

La preparación del bloque inicial carga 100 productos mediante `cargar_datos --cantidad 100 --semilla 42 --completo`, exclusivamente en su archivo nuevo de ensayo. Para revisar esa base con `verificar_bd`, selecciona tanto `MUSICPRO_DB_ENGINE=sqlite` como su `MUSICPRO_DB_PATH`; la ruta por sí sola no cambia la conexión de WampServer.

La carga añade registros ficticios sin eliminar los anteriores. En **Ventas**, abre un documento, observa su cliente y sus detalles. En **Detalles de ventas**, busca el mismo número; cada fila señala un producto, cantidad y precio. En **Movimientos**, busca ese número para encontrar la salida vinculada y el motivo **Por venta**. El recorrido equivalente de **Compras** termina en un ingreso **Recepción de mercadería**.

Compras y ventas muestran sus detalles dentro del formulario y tienen total calculado; cada detalle muestra su subtotal. Estos importes no son columnas nuevas. Para crear un documento manual, completa su número y contraparte y añade los detalles. El movimiento se registra por separado, seleccionando el detalle correspondiente. Las referencias deben concordar con tipo, producto y cantidad. El stock se mantiene manualmente cuando editas datos desde Admin; esta carga completa calcula un stock inicial coherente para sus productos nuevos.

Las cantidades de detalles y movimientos deben ser al menos 1; costos y precios deben ser positivos. No puedes repetir el mismo producto dentro del mismo documento. `PROTECT` conserva las referencias: para borrar ejemplos relacionados, elimina primero movimientos, después detalles, documentos y productos, y finalmente los catálogos que ya no estén utilizados.

## Usuarios, grupos y permisos

Un superusuario puede administrar todos los modelos. Para demostrar acceso limitado, crea desde **Usuarios** una cuenta distinta, marca **Es staff** y asigna mediante **Grupos** o permisos individuales las acciones permitidas de la aplicación **Bodega**:

| Permiso del producto | Acción |
| --- | --- |
| `bodega.view_producto` | Consultar productos en Admin |
| `bodega.add_producto` | Crear productos |
| `bodega.change_producto` | Editar productos |
| `bodega.delete_producto` | Eliminar productos |

Los diez modelos tienen permisos equivalentes para sus propias acciones. Para usar el autocompletado de una relación, concede permiso de consulta o modificación sobre el modelo relacionado; por ejemplo, consulta de categorías al editor de productos. Prueba la cuenta limitada cerrando la sesión del superusuario e iniciando la de prueba.

Los formularios HTML de productos también comprueban los permisos de creación, edición y eliminación. Las pantallas propias de inventario y movimientos requieren sesión y sus permisos correspondientes. Para las cuentas que acceden por el login del Admin se necesita además `is_staff=True`; ese requisito no se aplica al login propio de E3.

Para explicar el resultado al docente, relaciona cada acción con su efecto: crear inserta una fila, consultar lee la información, modificar actualiza campos y eliminar borra la fila cuando las relaciones protegidas lo permiten. Para el alcance de la entrega actual consulta [la matriz de E3](docs/pauta_e3_bodega.md).
