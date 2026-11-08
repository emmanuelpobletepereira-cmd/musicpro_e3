# Migraciones del inventario Music Pro

Un cambio en `Core/models.py` describe cómo quieres que sea un modelo; no modifica por sí solo la base existente. Las migraciones conservan esas decisiones en archivos y permiten aplicar la misma estructura en otra instalación.

La carpeta física de la aplicación es `Core`, pero su etiqueta Django es **`bodega`**. Por eso se usa `makemigrations bodega` y las tablas del negocio mantienen el prefijo `bodega_`. Consulta [el modelo actual de Bodega](docs/diagrama_bodega_e3.md). No cambies esa etiqueta para renombrar la carpeta: forma parte del historial existente.

## Primera instalación

Con las dependencias de [requirements.txt](requirements.txt) instaladas:

```powershell
python manage.py check
python manage.py migrate
python manage.py showmigrations bodega
python manage.py verificar_bd
```

| Comando | Para qué sirve |
| --- | --- |
| `check` | Revisar la configuración antes de modificar la base |
| `migrate` | Aplicar las migraciones incluidas y las de las aplicaciones internas |
| `showmigrations bodega` | Mostrar el estado del historial del inventario; `[X]` significa aplicado |
| `verificar_bd` | Abrir la conexión real y revisar tablas, conteos y migraciones pendientes |

Una instalación nueva utiliza las migraciones guardadas. No necesita generar otra copia con `makemigrations`.

## Historial que debes poder explicar

| Archivo en `Core/migrations/` | Cambio registrado |
| --- | --- |
| `0001_initial.py` | Creación de Categoría, Producto y Movimiento con sus relaciones |
| `0002_producto_stock_minimo.py` | Incorporación de `stock_minimo` a Producto con valor por defecto `5` |
| `0003_integridad_movimientos.py` | Restricciones de cantidad y tipo del movimiento, índice por fecha/identificador y nombres legibles |
| `0004_normalizar_motivos_movimientos.py` | Migración de datos: reemplaza la mención a Faker por «Recepción de mercadería» en ingresos y normaliza «venta» como «Por venta» en salidas |
| `0005_diez_tablas_bodega.py` | Añade Marca, Proveedor, Cliente, Compra, DetalleCompra, Venta y DetalleVenta; agrega marca opcional al producto y referencias opcionales de origen a movimientos, con restricciones |
| `0006_producto_precio_estado.py` | E3: añade precio decimal no negativo y estado ACTIVO/INACTIVO a Producto; conserva las filas y sus campos anteriores. Precio inicial 0,00 pendiente de definir y estado inicial ACTIVO. |
| `0007_bodega_solicitudes_stock.py` | Pauta Bodega E3: Sucursal, Solicitud y DetalleSolicitud, proveedor opcional en productos anteriores, descripción de categoría, proveedor activo y trazabilidad de stock/solicitud en Movimiento. Conserva los diez modelos previos. |

La segunda migración es una modificación real posterior al modelo inicial: permite distinguir las existencias actuales de su umbral mínimo. La tercera refuerza la integridad para que también se respeten las reglas cuando se guardan datos fuera de un formulario.

La cuarta utiliza `RunPython` para corregir motivos ya almacenados. Conserva los identificadores, productos, tipos, cantidades y fechas; no crea tablas ni campos. La ampliación del diagrama ocurre después, con `0005_diez_tablas_bodega`. No incluye una reversión automática de los textos corregidos; el respaldo previo permite consultar sus valores anteriores.

La quinta migración conserva las tres tablas originales y sus datos. Los campos nuevos de marca y origen permiten `NULL` para que los productos y movimientos previos sigan siendo válidos. Incorpora siete tablas del negocio para alcanzar las diez solicitadas por el profesor.

En la defensa, abre `0002_producto_stock_minimo.py`, identifica su dependencia de `0001_initial` y explica `AddField`. Luego revisa su SQL y el estado actual sin deshacer cambios:

```powershell
python manage.py sqlmigrate bodega 0002
python manage.py showmigrations bodega
python manage.py shell -c "from Core.models import Producto; campo=Producto._meta.get_field('stock_minimo'); print(campo.get_internal_type(), campo.default)"
```

`sqlmigrate` muestra el SQL del cambio sin ejecutarlo. `showmigrations` confirma si se aplicó. La consulta final inspecciona el tipo y el valor por defecto del campo en el modelo actual.

## Flujo cuando modificas un modelo

Después de realizar un cambio necesario en `Core/models.py`, ejecuta:

```powershell
python manage.py makemigrations bodega
python manage.py migrate --plan
python manage.py migrate
python manage.py showmigrations bodega
python manage.py verificar_bd
```

1. `makemigrations` compara el modelo con el historial y genera el siguiente archivo. Revisa sus operaciones antes de aplicarlo.
2. `migrate --plan` muestra las operaciones pendientes.
3. `migrate` actualiza la estructura y registra lo aplicado en `django_migrations`.
4. `showmigrations` muestra el nuevo archivo marcado con `[X]`.
5. `verificar_bd` confirma conexión, tablas y estado de migraciones.

Si no cambiaste ningún modelo, `makemigrations` debe informar que no hay cambios. No crees migraciones vacías solo para aumentar el historial.

Como ejemplo futuro, añadir una descripción opcional a Producto requeriría definir el campo, generar otra migración y actualizar el diagrama. Si el nuevo campo fuera obligatorio y ya existieran productos, habría que decidir un valor inicial válido o hacer el cambio por etapas. Ese campo es un ejemplo; no pertenece al modelo actual.

## Comprobación y conservación

```powershell
python manage.py makemigrations --check --dry-run
$motorPruebasAnterior = $env:MUSICPRO_DB_ENGINE
try {
    $env:MUSICPRO_DB_ENGINE = 'sqlite'
    python manage.py test Core
    if ($LASTEXITCODE -ne 0) { throw 'Las pruebas no finalizaron correctamente.' }
} finally {
    if ($null -eq $motorPruebasAnterior) { Remove-Item Env:\MUSICPRO_DB_ENGINE -ErrorAction SilentlyContinue }
    else { $env:MUSICPRO_DB_ENGINE = $motorPruebasAnterior }
}
```

La comprobación detecta cambios de modelos que todavía no tengan migración, sin crear archivos. La selección explícita de SQLite ejecuta las pruebas en una base temporal de Django. `finally` restaura después la selección anterior, incluso si las pruebas fallan.

Conserva las migraciones en Git junto con los modelos y [el diagrama actual](docs/diagrama_bodega_e3.md). No borres el historial ni edites una migración ya aplicada para simular otro esquema. Una migración puede alterar o eliminar información; revisa sus operaciones y realiza cualquier ensayo sobre un archivo independiente, seleccionando `MUSICPRO_DB_ENGINE=sqlite` y una ruta nueva en `MUSICPRO_DB_PATH`.

Migrar prepara la estructura; [cargar datos con Faker](README_SEEDER.md) añade registros. Son operaciones diferentes y se ejecutan en ese orden.
