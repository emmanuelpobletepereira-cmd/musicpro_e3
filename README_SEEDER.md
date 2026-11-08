# Datos ficticios con Faker

El comando [cargar_datos.py](Core/management/commands/cargar_datos.py) genera productos y comprueba su persistencia. El modo `--completo` conserva el generador histórico de productos, compras, ventas, detalles y movimientos de E2. El esquema actual tiene trece tablas propias; esa modalidad carga los diez modelos anteriores.

Para una muestra pequeña del flujo actual de Bodega, sigue `cargar_demo_bodega` en [README_WAMP.md](README_WAMP.md). Los ensayos de volumen de esta guía utilizan siempre un archivo SQLite nuevo e independiente de la base habitual de WampServer.

## Instalar y comprobar Faker

Con el entorno virtual activado:

```powershell
python -m pip install -r requirements.txt
python -m pip check
python -m pip show Faker
python -c "from faker import Faker; print(Faker('es_CL').name())"
```

Faker se importa con `from faker import Faker`; no se agrega a `INSTALLED_APPS`. Para preparar toda la conexión actual de otro equipo, utiliza las instrucciones y dependencias de [README_WAMP.md](README_WAMP.md).

## Ejecutar una carga en una base de ensayo

Desde PowerShell, en la carpeta que contiene `manage.py`, selecciona la cantidad y la modalidad. El bloque guarda los valores anteriores de las variables, crea una ruta nueva, selecciona SQLite explícitamente y restaura ambas variables incluso si la carga falla:

```powershell
$cantidadEnsayo = 100
$modoCompletoEnsayo = $false
$conMovimientosEnsayo = $false
$motorEnsayoAnterior = $env:MUSICPRO_DB_ENGINE
$rutaEnsayoAnterior = $env:MUSICPRO_DB_PATH
$archivoEnsayo = Join-Path (Get-Location) ('ensayo-' + $cantidadEnsayo + '-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
try {
    if (Test-Path -LiteralPath $archivoEnsayo) { throw 'La ruta de ensayo ya existe.' }
    $env:MUSICPRO_DB_ENGINE = 'sqlite'
    $env:MUSICPRO_DB_PATH = $archivoEnsayo
    python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el esquema de ensayo.' }
    python manage.py verificar_bd
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo comprobar la base de ensayo.' }
    $argumentosEnsayo = @('manage.py', 'cargar_datos', '--cantidad', $cantidadEnsayo, '--lote', 1000, '--semilla', 42)
    if ($modoCompletoEnsayo) { $argumentosEnsayo += '--completo' }
    elseif ($conMovimientosEnsayo) { $argumentosEnsayo += '--con-movimientos' }
    Measure-Command {
        python @argumentosEnsayo
        if ($LASTEXITCODE -ne 0) { throw 'No se completó la carga de ensayo.' }
    }
    python manage.py verificar_bd
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo comprobar el resultado.' }
} finally {
    if ($null -eq $motorEnsayoAnterior) { Remove-Item Env:\MUSICPRO_DB_ENGINE -ErrorAction SilentlyContinue }
    else { $env:MUSICPRO_DB_ENGINE = $motorEnsayoAnterior }
    if ($null -eq $rutaEnsayoAnterior) { Remove-Item Env:\MUSICPRO_DB_PATH -ErrorAction SilentlyContinue }
    else { $env:MUSICPRO_DB_PATH = $rutaEnsayoAnterior }
}
```

El primer diagnóstico debe identificar la ruta de ensayo y mostrar cero productos. El último permite comprobar la cantidad solicitada. El archivo queda guardado en `$archivoEnsayo`; las variables recuperan sus valores previos y la base habitual no recibe estos registros. Seleccionar solo `MUSICPRO_DB_PATH` no basta: si no seleccionas SQLite, el proyecto conserva la conexión de WampServer.

Para consultar la conexión habitual después del ensayo puedes ejecutar `python manage.py verificar_bd`. El diagnóstico mostrará la conexión que tenías seleccionada antes del bloque, normalmente WampServer en esta instalación.

## Modalidades y opciones

| Opción | Comportamiento |
| --- | --- |
| `--cantidad N` | Añade entre 1 y 1.000.000 de productos nuevos |
| `--lote N` | Prepara de 1 a 10.000 productos por grupo, con 1.000 por defecto |
| `--semilla N` | Repite los valores ficticios con la misma configuración y versión |
| `--con-movimientos` | Añade un ingreso inicial por cada producto generado |
| `--completo` | Genera los documentos, detalles, ingreso y salida de cada producto |
| `--database default` | Selecciona el alias de conexión configurado |

Para ensayar movimientos, cambia `$conMovimientosEnsayo` a `$true` en el bloque completo. Para ensayar la carga histórica de documentos, cambia `$modoCompletoEnsayo` a `$true`; ese modo ya incluye los movimientos. Repite siempre el bloque entero para seleccionar y restaurar ambas variables.

Cada ejecución añade registros; una semilla fija no repite los códigos porque el prefijo UUID cambia para evitar duplicados. Las categorías, marcas y contactos se reutilizan cuando corresponde. La generación utiliza datos ficticios.

Con `--completo`, cada producto nuevo tiene una compra y una venta con sus detalles, un ingreso y una salida. El stock generado es la cantidad recibida menos la vendida. Esta carga histórica no reemplaza los servicios de stock de las pantallas propias de E3 y no modifica registros anteriores.

## Demostrar los cuatro volúmenes

Los ensayos históricos solicitaban 100, 1.000, 100.000 y 1.000.000 productos. Repite el bloque completo cambiando `$cantidadEnsayo`; cada ejecución crea un archivo nuevo.

| Cantidad solicitada | Productos iniciales en la base nueva | Productos esperados al terminar |
| ---: | ---: | ---: |
| 100 | 0 | 100 |
| 1.000 | 0 | 1.000 |
| 100.000 | 0 | 100.000 |
| 1.000.000 | 0 | 1.000.000 |

Los tiempos dependen del equipo y de la modalidad elegida. Una medida realizada en el esquema anterior no acredita el rendimiento del esquema actual. Los resultados efectivamente ejecutados están en [VERIFICACION.md](VERIFICACION.md).

## Qué sucede dentro del comando

El flujo es: validar argumentos → generar un lote → guardar dentro de una transacción → verificar los registros creados.

El tamaño del lote limita los objetos preparados en memoria. `bulk_create` guarda ese grupo; la transacción confirma juntos los registros correspondientes a la modalidad. El comando consulta después el rango de códigos de esa ejecución y comprueba su cantidad.

La generación desactiva temporalmente `DEBUG` para evitar acumular el historial SQL. `bulk_create` no ejecuta el `save()` individual ni la validación de formularios; el generador produce valores compatibles con las restricciones de la base.

Si la carga se interrumpe, se conservan los lotes confirmados y se revierte el lote que estaba en su transacción. Otra ejecución añade una carga nueva; no continúa automáticamente la anterior.
