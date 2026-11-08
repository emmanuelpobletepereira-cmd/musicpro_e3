# Pauta E3 aplicada al caso Bodega

Fuente: **E3 Evaluacion_inv_Caso_Semestral_Music_pro_U2 Backend.docx**, proporcionado por el estudiante el 7 de noviembre de 2026. Se revisaron los requisitos comunes de E3 y la sección Bodega completa, incluidas sus entidades, diagrama y veinte preguntas de reportes. No se usaron los casos Tienda, Transporte ni Tarjetas para ampliar el alcance.

| Requisito de la pauta | Evidencia en el proyecto |
| --- | --- |
| Sistema administrativo propio sin utilizar Django Admin | Vistas, formularios HTML y menú de E3. Usuarios, catálogos, inventario, solicitudes, movimientos y reportes. Admin solo queda como antecedente E2. |
| Conexión con un servidor local de base de datos | `wamp.py`, `database_config.py`, conector, migraciones y comprobación real; arranque con `servidor_wamp.bat`. La base se administra desde HeidiSQL. |
| Inicio y cierre de sesión mediante Django | `authenticate`, `login`, `logout`, destino validado, logout POST y pérdida del acceso después del cierre. |
| Decoradores y protección de URL administrativas | `login_required`, `permiso_requerido` y autorizaciones comunes de catálogos; pruebas de GET y POST directos sin sesión/permisos. |
| Mantención de usuarios propia | Crear, consultar, modificar datos/rol/contraseña y desactivar cuentas normales en `/usuarios/`. |
| Mantención de entidades principales Bodega | Producto, Categoria, Proveedor, Sucursal, Solicitud, DetalleSolicitud y Movimiento, con formularios propios. |
| Solicitudes de sucursales con revisión/aprobación/rechazo | Estados pendiente, aprobada, rechazada y despachada; detalle con cantidades solicitadas, aprobadas y despachadas. |
| Control de entradas y salidas | Servicios transaccionales, trazabilidad de cada ajuste, stock no negativo y prevención de doble despacho. |
| Uso del ORM y persistencia desde la interfaz | QuerySets, `save`, `delete`, `update`, `F`, `Count`, `Sum`, `Avg`, `Exists`; sin SQL libre ni raw para reportes/CRUD. |
| Página de reportes y evidencia de consultas | 17 reportes operativos con filtros y resultados reales. Las consultas económicas 4, 14 y 18 se retiraron por petición del usuario; el alcance actual no cubre esas tres preguntas originales. Las funciones ORM están implementadas en `Core/reportes.py`; su explicación se mantiene fuera de la interfaz. |
| Defensa individual y comprensión del código | Guion y recorrido de demostración en `README_E3.md`; la preparación y defensa corresponden al estudiante. |

## Interpretaciones y equivalencias

La parte común menciona diez consultas entregadas por el profesor; la sección Bodega enumera veinte. La versión actual mantiene 17, conservando sus identificadores originales. Por petición del usuario se excluyeron las consultas 4 (mayores precios), 14 (valor del inventario) y 18 (categoría de mayor valor), junto con los precios del flujo operativo de Bodega. Por ello no se afirma cobertura completa de los veinte reportes de la pauta. El docente debe confirmar cuáles diez se exigirán en la defensa. Los indicadores numéricos de la tabla de escala de apreciación están vacíos: no se inventaron criterios ni puntajes.

`Producto.precio` permanece como campo interno legado para conservar los datos existentes, sin mostrarse ni procesarse desde el CRUD operativo. No se creó una migración para borrarlo. Las compras, ventas e importes históricos de E2 siguen guardados.

Se conserva la nomenclatura y los datos de E2. `Producto.codigo` equivale a SKU; `cantidad`, a stock actual; `estado`, a la condición activo/inactivo; `Proveedor.nombre`, a razón social; `Movimiento`, a MovimientoStock. Se añadieron las relaciones y entidades faltantes. El diagrama [Bodega E3](diagrama_bodega_e3.md) explica todos los campos y el legado adicional.

Stock «por debajo del mínimo» utiliza `<`, sin incluir la igualdad. «Último mes» se define como mes calendario anterior según America/Santiago. El promedio del reporte 19 calcula primero las unidades totales de cada solicitud y luego el promedio de esos totales. Los reportes incluyen las solicitudes registradas de todos los estados, salvo que la pregunta solicite un estado particular; no se confunden unidades solicitadas con unidades despachadas.

Las referencias SQL en diagnóstico/bootstrap corresponden a metadatos del servidor o tablas internas de zona horaria, no a consultas directas del negocio. Las consultas y operaciones de Bodega se ejecutan con Django ORM.
