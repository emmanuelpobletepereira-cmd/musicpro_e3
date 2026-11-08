# El ejemplo del profesor adaptado a Bodega

Referencia revisada: [cafeycodigo/django-examples](https://github.com/cafeycodigo/django-examples/tree/c823251cf9540318c86031ac76ca4e4a7e00b311), commit `c823251cf9540318c86031ac76ca4e4a7e00b311`, del 4 de noviembre de 2026. La adaptación conserva las entidades y datos de Music Pro para el caso Bodega de E3. La versión actual concentra el flujo operativo en existencias y solicitudes, sin precios.

| Recorrido del ejemplo | Equivalente en Bodega |
| --- | --- |
| Panel de Biblioteca con cuatro métricas y préstamos recientes | Panel principal con productos, unidades, sucursales activas, solicitudes pendientes y actividad reciente. |
| Catálogo y ficha de libros | Catálogo y ficha de productos con proveedor, stock, ubicación, movimientos y solicitudes autorizadas. |
| Crear, editar y confirmar eliminación mediante HTML y vistas | Formularios HTML procesados con `request.POST`, validación `full_clean`, mensajes y errores junto al campo. Tras guardar se abre la ficha. |
| Login propio con Django y logout POST | Mismo flujo de cuentas y sesiones; Bodega añade permisos por acción y los perfiles Administrador/Operador. |
| Panel de consultas de RRHH | 17 reportes operativos de Bodega agrupados por área, con filtros específicos y resultados. |

Fuentes del recorrido: [panel de Biblioteca](https://github.com/cafeycodigo/django-examples/blob/c823251cf9540318c86031ac76ca4e4a7e00b311/biblioteca/templates/biblioteca/index.html), [vistas del CRUD](https://github.com/cafeycodigo/django-examples/blob/c823251cf9540318c86031ac76ca4e4a7e00b311/biblioteca/views.py), [panel de consultas RRHH](https://github.com/cafeycodigo/django-examples/blob/c823251cf9540318c86031ac76ca4e4a7e00b311/rrhh/templates/rrhh/consultas_dashboard.html) y [consultas RRHH](https://github.com/cafeycodigo/django-examples/blob/c823251cf9540318c86031ac76ca4e4a7e00b311/rrhh/views.py).

## Probar el recorrido

1. Inicia el servidor y abre `http://127.0.0.1:8000/`. El acceso exige sesión y permiso de consulta de productos.
2. Desde el panel abre el catálogo y pulsa **Ver ficha**. Revisa el producto, su stock y las relaciones que tu cuenta puede consultar.
3. Crea o edita un producto. Las escrituras utilizan POST con CSRF, validan los campos y muestran el resultado guardado en la ficha.
4. Abre **Consultas y reportes** en `/consultas/panel/`. Elige una pregunta y completa sus filtros. La página presenta los registros y totales; la explicación de las consultas está en un documento separado.

Las consultas están separadas en funciones con nombres de negocio dentro de `Core/reportes.py`; `construye_reporte` selecciona la función correspondiente. Se mantienen 17 reportes con su paginación y consultas ejecutadas por el ORM. Las consultas económicas 4, 14 y 18 de la pauta original se retiraron por petición del usuario; esta versión no cubre esos tres reportes. Los identificadores de los demás se conservan.

## Bases de datos y alcance

La [configuración del profesor](https://github.com/cafeycodigo/django-examples/blob/c823251cf9540318c86031ac76ca4e4a7e00b311/sistema/settings.py) usa SQLite. Para E3, esta copia utiliza un servidor local de base de datos alojado en WampServer y administrado desde HeidiSQL:

- `servidor_wamp.bat`: base `musicpro_e3` del servicio local de WampServer, puerto 3306.
- `servidor.bat`: utiliza la conexión local preparada para WampServer.

Las bases son independientes y no se sincronizan automáticamente. Se copiaron los datos actuales de SQLite a WampServer conservando cuentas, permisos e identificadores. La muestra ficticia DEMO-E3 permanece en la instancia portátil anterior, que está detenida; no se añadió a la copia de WampServer. Los registros y migraciones anteriores se conservan. La conexión actual se explica en [README_WAMP.md](../README_WAMP.md).

Los formularios propios siguen sin `ProductoForm` ni `ModelForm`. La interfaz utiliza CSS local con tarjetas y paleta verde lima; no necesita CDN. La adaptación no incorpora los modelos de Biblioteca, RRHH ni los otros negocios del repositorio. Las solicitudes, sus detalles y los movimientos conservan las transacciones y las reglas de stock de Bodega.

La referencia sirve como estructura de aprendizaje; la pauta y la explicación individual determinan la entrega. Los resultados comprobados se registran en [VERIFICACION.md](../VERIFICACION.md).
