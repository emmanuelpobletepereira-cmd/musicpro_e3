# Consultas implementadas en Bodega

Esta explicación se conserva fuera de la aplicación. Las pantallas muestran filtros, registros y resultados del inventario.

Las consultas reales están implementadas en [Core/reportes.py](../Core/reportes.py). La vista [Core/views_reportes.py](../Core/views_reportes.py) valida los filtros y ejecuta la función correspondiente al reporte seleccionado.

## Productos bajo el stock mínimo

La función `productos_bajo_minimo` utiliza esta condición:

```python
Producto.objects.filter(cantidad__lt=F('stock_minimo'))
```

`cantidad` es el stock actual. `F('stock_minimo')` referencia el mínimo del mismo producto. La consulta obtiene solamente los productos cuya cantidad es menor que su mínimo. Está implementada en el reporte 3; la página muestra sus resultados, sin el código.

## Productos de una categoría

La función `productos_por_categoria` filtra con el identificador validado que llega desde el formulario:

```python
productos.filter(categoria_id=filtros['categoria'])
```

El ORM convierte la condición en una consulta a la base seleccionada. No se concatena el dato del usuario para construir una instrucción SQL.

## Unidades disponibles en el inventario

La función `metricas_inventario` obtiene el total de unidades mediante una agregación como esta:

```python
Producto.objects.aggregate(total_unidades=Sum('cantidad', default=0))
```

`Sum('cantidad')` suma el stock actual de todos los productos y devuelve un valor resumido. `default=0` permite mostrar cero si no hay productos. Esta métrica trabaja con unidades, sin calcular importes.

Estos ejemplos muestran filtros y agregaciones reales del inventario. La aplicación mantiene 17 reportes operativos, incluidos solicitudes por sucursal, sus detalles, fechas, conteos por estado y movimientos de salida. Por petición del usuario se retiraron las consultas económicas 4, 14 y 18 de la pauta original; esta versión no cubre esas tres preguntas y conserva los identificadores de las demás.
