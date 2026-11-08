# Evaluación 3 Bodega y consultas ORM

Esta versión sigue el recorrido del [ejemplo del profesor en GitHub](https://github.com/cafeycodigo/django-examples/tree/c823251cf9540318c86031ac76ca4e4a7e00b311): **panel → catálogo → ficha → formularios → consultas**. Abre el [panel principal](http://127.0.0.1:8000/), [Consultas y reportes](http://127.0.0.1:8000/consultas/panel/). La [comparación con el ejemplo](docs/replica_profesor.md) explica las equivalencias de Bodega. Las explicaciones de código se conservan fuera de la aplicación, en [este documento](docs/explicacion_query_bodega.md).

Para iniciar la aplicación usa `.\servidor_wamp.bat`, conectado a la base que administras desde HeidiSQL.

Implementación guiada por **E3 Evaluacion_inv_Caso_Semestral_Music_pro_U2 Backend.docx**, apartados «Parte 1. Sistema web administrativo», «Parte 2. Desarrollo de consultas utilizando Django ORM» y «BODEGA: GESTIÓN DE INVENTARIO Y SOLICITUDES DE SUCURSALES». La aplicación administra productos, proveedores, categorías, sucursales, solicitudes, stock y usuarios mediante pantallas propias.

La pauta menciona un informe de **10 consultas asignadas por el docente**, pero su sección Bodega enumera **20 reportes**. La versión actual mantiene **17 reportes operativos**: por petición del usuario se retiraron el 4 (mayores precios), el 14 (valor del inventario) y el 18 (categoría de mayor valor). Se conservan los números originales de los restantes. Esta versión no cubre esas tres consultas económicas; queda confirmar cuáles diez se pedirán en la defensa. La matriz de requisitos está en [docs/pauta_e3_bodega.md](docs/pauta_e3_bodega.md). No se atribuye una nota: la tabla de indicadores al final del Word está vacía.

## Iniciar esta copia

Haz doble clic en [servidor.bat](servidor.bat) o ejecuta:

```powershell
.\servidor.bat
```

Primero abre WampServer y espera su icono verde. El lanzador utiliza la base **musicpro_e3** del servicio de WampServer, en el puerto **3306**, que puedes administrar desde HeidiSQL, y después inicia Django. [servidor_wamp.bat](servidor_wamp.bat) permite elegir explícitamente ese modo. Para otro puerto web usa `.\servidor_wamp.bat 8001`.

Abre [Inventario](http://127.0.0.1:8000/productos/), [Solicitudes](http://127.0.0.1:8000/solicitudes/), [Reportes](http://127.0.0.1:8000/reportes/). Inicia sesión con tu cuenta existente: se copiaron las cuentas de SQLite conservando sus contraseñas cifradas.

La conexión local con HeidiSQL y los comandos actuales están explicados en [README_WAMP.md](README_WAMP.md). Las claves de la aplicación se generan localmente y se guardan fuera de Git; no hay contraseñas predeterminadas en el código. `manage.py` selecciona la conexión local preparada para WampServer; si esa configuración existe pero es inválida, informa el error sin sustituir la base. Usa `wamp.py manage` para elegir esta conexión explícitamente. SQLite requiere seleccionarlo de forma explícita o trabajar en un equipo sin configuración local.

## Recorrido del sistema propio

| Pantalla | Operaciones |
| --- | --- |
| Inventario | Consultar, buscar, filtrar, crear, editar y eliminar productos sin relaciones. Proveedor, estado, ubicación y stock, sin precios. |
| Categorías | Consultar, crear, editar y eliminar categorías sin productos vinculados. |
| Proveedores | Consultar, crear, editar, desactivar y eliminar proveedores sin relaciones. |
| Sucursales | Consultar, crear, editar, desactivar y eliminar sucursales sin solicitudes. |
| Solicitudes | Crear con varios productos, consultar detalles, editar o eliminar pendientes, aprobar cantidades, rechazar y despachar. |
| Movimientos | Consultar e ingresar entradas/salidas que actualizan el stock. Los movimientos aplicados conservan su historial. |
| Usuarios | Consultar, crear, editar datos/rol/contraseña y desactivar cuentas normales. |
| Reportes | Seleccionar y ejecutar cualquiera de los 17 reportes operativos de Bodega, con filtros y resultados. |

Los formularios son HTML con `{% csrf_token %}`; las vistas procesan una lista de campos permitidos desde `request.POST`, validan y guardan con el ORM. No se utiliza `ProductoForm` ni `ModelForm` en estas pantallas. GET muestra o consulta; las modificaciones, el cierre de sesión y las transiciones utilizan POST.

Las páginas de E3 no dependen de Django Admin. `/admin/` se conserva únicamente como antecedente de E2 y no aparece en el menú de E3. La cuenta técnica inicial puede crearse con `createsuperuser`; después se demuestra la mantención de cuentas normales en **Usuarios**. Las cuentas técnicas staff/superuser no se editan desde la mantención de usuarios de la aplicación.

## Perfiles y control de acceso

| Perfil | Permisos de la aplicación |
| --- | --- |
| Administrador | Gestión de bodega, aprobación/rechazo y despacho, eliminaciones permitidas y mantención de usuarios normales. |
| Operador | Consulta y reportes; crear/editar productos, catálogos y solicitudes pendientes; registrar movimientos. Sin eliminar, aprobar, rechazar, despachar ni gestionar usuarios. |
| Sin permisos | No accede a las funciones administrativas aunque tenga sesión. |

`login_required` comprueba la sesión y el decorador reutilizable `permiso_requerido` comprueba los permisos efectivos en el servidor. Los catálogos resuelven permisos en una función común con modelos y campos permitidos. Una petición sin sesión redirige al acceso; una petición autenticada sin autorización recibe 403. Ocultar botones no reemplaza esta comprobación.

En **Usuarios**, asigna un solo rol a las cuentas de prueba. `configurar_roles` sincroniza los grupos de forma repetible. Los grupos se suman con permisos directos en Django: para demostrar las restricciones usa cuentas normales sin privilegios adicionales, no el superusuario. No puedes desactivar tu propia cuenta. Desactivar una cuenta impide el acceso con ella.

## Reglas del inventario y solicitudes

`PENDIENTE → APROBADA → DESPACHADA` o `PENDIENTE → RECHAZADA`.

- Solo se editan o eliminan solicitudes pendientes. Una solicitud contiene entre uno y cien productos distintos de sucursales y productos activos.
- Se puede aprobar una parte de las unidades solicitadas, sin superar la cantidad pedida. La aprobación no reserva stock.
- El despacho comprueba todas las existencias y descuenta las cantidades aprobadas dentro de una transacción. Si falla una línea, se revierte todo el despacho. No puede ejecutarse dos veces.
- Los movimientos nuevos de E3 actualizan las existencias y no permiten salidas mayores al stock. Los ajustes hechos desde la ficha del producto también registran un movimiento. La ficha incluye el stock original para detectar cambios concurrentes.
- Los movimientos aplicados no se editan ni eliminan; una corrección se registra mediante otro movimiento. Los históricos E2 conservan `stock_aplicado=False` porque entonces registraban información sin actualizar existencias. No se vuelven a aplicar al migrar.

Se conservan los diez modelos anteriores y se añaden Sucursal, Solicitud y DetalleSolicitud: **trece tablas propias** en total. El caso Bodega usa siete entidades; las otras seis son antecedentes de E2. No se implementaron los casos Tienda, Transporte o Tarjetas de la pauta. El modelo y equivalencias están en [docs/diagrama_bodega_e3.md](docs/diagrama_bodega_e3.md), con [imagen para presentar](docs/diagrama_bodega_e3.png).

Los nombres existentes se conservan: `codigo` equivale a SKU, `cantidad` a stock actual, `Proveedor.nombre` a razón social y `Movimiento` a MovimientoStock. Los productos antiguos pueden tener proveedor sin asignar; al editarlos debes elegir uno activo. El campo `Producto.precio` permanece únicamente como dato interno legado, sin mostrarse ni procesarse en el CRUD de Bodega. Se conservaron los valores históricos y no se creó una migración para borrarlos. Las compras, ventas e importes de E2 también permanecen guardados.

## Reportes de Bodega

En **Reportes**, elige una consulta y completa los filtros requeridos. Las tablas muestran los resultados reales y permiten cambiar de página. Los totales se calculan sobre todos los registros que corresponden al reporte.

| N.º | Reporte |
| --- | --- |
| 1, 2, 3, 5 | Todos los productos; categoría; stock menor al mínimo; cantidad por categoría. |
| 6–10 | Productos por proveedor; solicitudes por sucursal; detalle de solicitud; conteo por estado; solicitudes en rango de fechas. |
| 11, 12, 13, 15 | Cinco sucursales con más unidades solicitadas; productos más solicitados; proveedor con más productos distintos; productos nunca solicitados. |
| 16, 17, 19, 20 | Salidas del mes calendario anterior; sucursales con pendientes; promedio de unidades por solicitud; cinco productos más solicitados en un período. |

La interfaz no contiene guías del curso, bloques de código, SQL ni explicaciones de QUERY. El funcionamiento de las consultas está documentado por separado en [explicacion_query_bodega.md](docs/explicacion_query_bodega.md). Las funciones continúan implementadas con el ORM en `Core/reportes.py`.

Los rangos incluyen ambos días en la zona de Chile; el reporte 16 usa el mes calendario anterior. El stock bajo mínimo utiliza estrictamente `cantidad < stock_minimo`.

## Muestra y defensa

La muestra ficticia **DEMO-E3** permanece en la instancia portátil anterior y no se agregó al copiar los datos actuales de SQLite a WampServer. Si necesitas añadirla para practicar, el comando es repetible sin duplicar ni reescribir datos existentes:

```powershell
.\.venv\Scripts\python.exe wamp.py manage cargar_demo_bodega
```

No se falsifican fechas: el reporte del mes anterior puede devolver cero salidas si no hay movimientos de ese período.

Recorrido sugerido: entrar sin sesión a una URL protegida; iniciar sesión; crear una cuenta Operador desde Usuarios; consultar un reporte; crear una solicitud con Operador; intentar abrir aprobación sin permisos y mostrar 403; entrar con Administrador, aprobar y despachar; comparar stock y movimiento; cerrar sesión y comprobar pérdida del acceso. Para demostrar eliminación, usa un registro de prueba sin relaciones. Los productos con historial quedan protegidos.

Comprueba la conexión y la configuración:

```powershell
.\.venv\Scripts\python.exe wamp.py comprobar
.\.venv\Scripts\python.exe wamp.py manage check
```

Para ejecutar las pruebas en una base temporal SQLite, selecciona ese modo
en la terminal de pruebas y retira la selección al terminar:

```powershell
$env:MUSICPRO_DB_ENGINE = 'sqlite'
.\.venv\Scripts\python.exe manage.py test Core --noinput
Remove-Item Env:MUSICPRO_DB_ENGINE
```

El usuario de Wamp está limitado a `musicpro_e3`; no tiene permisos para crear
una base adicional de pruebas.

Los resultados ejecutados están en [VERIFICACION.md](VERIFICACION.md). La comprensión individual del código y la selección final de las diez consultas se deben preparar con el docente; no se reemplazan con pruebas automáticas.
