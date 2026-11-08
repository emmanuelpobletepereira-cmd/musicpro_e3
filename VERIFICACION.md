# Revisión final y tema verde lima — 8 de noviembre de 2026

- **145 pruebas aprobadas en el servidor local de WampServer**, 17,767 segundos, usando una base temporal independiente que se retiró al terminar.
- **145 pruebas aprobadas en SQLite**, 12,681 segundos en la ejecución final aislada.
- Diecisiete consultas y veinticuatro respuestas HTML comprobadas mediante lecturas sobre la base habitual; diagnóstico y `check` correctos, sin migraciones ni cambios de modelos pendientes.
- Tema verde lima revisado en 1440 y 390 píxeles: inicio de sesión, panel, inventario y reportes sin desbordamiento horizontal. Se inspeccionaron las capturas de escritorio y móvil. Contraste de los pares principales entre 5,85:1 y 10,96:1.

La suite sobre el servidor detectó que las tablas existentes utilizaban almacenamiento sin transacciones: cinco pruebas de reversión fallaron y cuatro listados del administrador histórico fallaron por ausencia de definiciones de zona horaria. Se corrigieron ambas causas antes de publicar.

La conexión ahora fuerza **InnoDB** para las tablas nuevas. En esta instalación se respaldó el esquema completo y se convirtieron las **23 tablas**; se recuperaron **25 claves foráneas** y se verificaron huellas de todas las filas antes y después, sin cambios de datos. El respaldo privado está en `backups/revision_almacenamiento_20261108/`. El diagnóstico rechaza tablas que no tengan soporte transaccional. El administrador conserva filtros de fecha y omite únicamente la navegación por años/meses cuando el servidor carece de zonas horarias.

Se revisaron autenticación, CSRF, métodos POST, permisos de servidor, usuarios y transacciones de stock. Las guías incluyen la preparación de otra instalación con una plantilla pública sin secretos. Los ensayos de las guías históricas seleccionan una base SQLite independiente y restauran las variables de la terminal. Se conservaron las eliminaciones de documentos antiguos realizadas en GitHub y se corrigieron sus enlaces.

**Alcance frente a la pauta:** permanecen excluidas las consultas económicas 4, 14 y 18 por petición del usuario. Falta confirmar cuáles diez consultas asignó el docente; no se afirma cobertura completa de las veinte preguntas originales. La matriz de requisitos está en [Pauta E3 aplicada a Bodega](docs/pauta_e3_bodega.md).

---

# Interfaz de Bodega sin precios — 7 de noviembre de 2026

Se retiró el precio del listado, formulario, ficha y administración del producto. El CRUD ya no solicita ni modifica ese dato; los valores históricos permanecen guardados. El panel de reportes muestra unidades en bodega en lugar de importes. La muestra de Bodega tampoco asigna precios nuevos.

Se retiraron los reportes económicos 4, 14 y 18; sus direcciones responden 404. Quedan **17 reportes activos**, conservando los identificadores originales. Esta decisión solicitada por el usuario deja fuera esas tres preguntas económicas de la pauta original de E3.

Validación: **142 pruebas aprobadas** en una base temporal SQLite, 24,971 segundos. En la conexión real de WampServer se ejecutaron los 17 reportes y se comprobaron 23 respuestas HTML mediante lecturas, sin campos ni símbolos monetarios. No se requieren migraciones; no se borraron datos ni se modificaron contraseñas o conexiones.

---

# Conexión de WampServer y HeidiSQL — 7 de noviembre de 2026

Revisión completa de conexiones y textos: **140 pruebas aprobadas en una base temporal SQLite**, 23,362 segundos. Se comprobó por separado que `manage.py` selecciona la base `musicpro_e3` de WampServer en el puerto 3306 y que sus veinte consultas funcionan mediante lecturas. El diagnóstico, la comprobación del esquema y `check` finalizaron correctamente; no hay migraciones pendientes ni cambios de modelos por generar.

El arranque habitual utiliza exclusivamente la conexión de WampServer. Se retiró la selección automática de la instancia portátil anterior y se unificaron las instrucciones y los mensajes de conexión. Los nombres actuales son `servidor_bd.bat`, `requirements-bd.txt` y `diagnosticar_bd`. La configuración local inválida produce un error y no cambia a otra base. SQLite se conserva para desarrollo explícito y pruebas.

La conexión actual del proyecto utiliza la base **musicpro_e3** del servicio local de WampServer en **127.0.0.1:3306**. HeidiSQL administra esa misma base; Django utiliza el usuario de aplicación configurado en el archivo privado de conexión. Las instrucciones vigentes están en [README_WAMP.md](README_WAMP.md).

Al preparar esta conexión se verificaron **23 tablas**, de las cuales **13 son de negocio**, y cero migraciones pendientes. Se copiaron **468 objetos**, incluidos los **221 productos**, **142 movimientos** y **tres cuentas** de la instantánea de SQLite. La comparación de la exportación de origen y destino confirmó que los campos, identificadores, hashes de contraseña y permisos se conservaron.

Se ejecutaron los **veinte reportes**, se renderizaron **siete pantallas** y se comprobó el bloqueo del acceso anónimo al inventario, mediante operaciones de lectura. La comprobación de Django no detectó errores y no había cambios de modelos pendientes. Estas comprobaciones de transferencia no se presentan como una nueva ejecución de las suites completas históricas.

Se conserva el respaldo privado en `backups/wamp_20261107_211654/`. La instancia portátil anterior está detenida y no es la conexión activa; las bases conservadas no se sincronizan automáticamente.

---

# Historial de comprobaciones

Las entradas siguientes registran etapas anteriores del proyecto. Sus cifras, versiones y pruebas corresponden a la preparación descrita en cada una; no son instrucciones para iniciar la conexión actual.

# Corrección de la interfaz de Bodega — 7 de noviembre de 2026

Se retiraron las guías y explicaciones técnicas añadidas a las pantallas: menú Guía CRUD, página «Del modelo al CRUD seguro», demostración QUERY, ejemplos ORM/SQL y explicaciones dentro de las fichas y reportes. La dirección antigua `/consultas/` lleva al panel de reportes; `/guia-crud/` dejó de publicarse.

Los veinte reportes mantienen sus consultas funcionales, filtros, paginación, permisos y resultados. La explicación se conserva fuera de la aplicación en [docs/explicacion_query_bodega.md](docs/explicacion_query_bodega.md). Se retiró además la captura de SQL de las vistas, que ya no era necesaria para el uso del sistema.

Los tres lanzadores muestran «Iniciando servidor...». Se eliminaron referencias académicas del historial de movimientos y el indicador técnico del motor de base de datos del pie de página. No se modificaron registros de negocio, modelos, sesiones ni contraseñas.

Comprobación ejecutada: **135 pruebas aprobadas en SQLite**, 26,166 segundos; `manage.py check` sin errores. Se mantienen las pruebas funcionales de los veinte reportes y de seguridad; las siete pruebas de la guía retirada fueron sustituidas por tres pruebas de la interfaz del negocio, rutas retiradas y consultas reales sin contenido didáctico.

Esta entrada describió la corrección de la interfaz y sustituyó las indicaciones anteriores sobre mostrar SQL o guías dentro de la página. La conexión vigente está documentada al inicio de este archivo.

---

# Adaptación comprobada del ejemplo GitHub — 7 de noviembre de 2026

Referencia del profesor: `cafeycodigo/django-examples`, commit `c823251cf9540318c86031ac76ca4e4a7e00b311`. Se adaptaron el recorrido de Biblioteca y la presentación de consultas de RRHH al caso Bodega. La correspondencia está en [docs/replica_profesor.md](docs/replica_profesor.md).

- Panel principal protegido con cuatro métricas reales y diez solicitudes recientes, según permisos.
- Ficha de producto con datos completos, movimientos y solicitudes relacionadas autorizadas; acceso «Ver ficha» desde el inventario.
- Formularios HTML con errores junto a los campos y regreso a la ficha después de guardar.
- Panel de veinte preguntas por nivel, ejemplos ORM y filtros específicos; resultados paginados y explicación desplegable del QUERY con SQL real y parámetros separados.
- Guía CRUD propia de seis pasos y práctica de defensa dentro de la aplicación.
- Se conserva Bodega, su historial, las reglas de stock, las sesiones y los permisos. Esta adaptación no cambia modelos, migraciones ni registros de negocio.
- En esa etapa se disponía de un lanzador explícito SQLite, retirado posteriormente, además del servidor local preparado en ese momento.

Comprobación final tras integrar todos los archivos:

| Comprobación | Resultado |
| --- | --- |
| `manage.py check` | Sin errores |
| `makemigrations --check --dry-run` | Sin cambios pendientes |
| Suite completa SQLite | **139 pruebas aprobadas**, 43,615 segundos |
| Suite completa del servidor portátil 8.4.13 (histórica) | **139 pruebas aprobadas**, 29,720 segundos |

Las pruebas nuevas verifican autenticación, métricas, ficha, guía, los veinte enlaces de consulta, filtros por nombre/ID manual, paginación y ausencia de escrituras en consultas. También comprueban que un usuario sin permiso de sucursal no vea sus nombres ni provoque consultas a esa tabla a través de las sugerencias de solicitudes.

Las pruebas usan bases temporales. En esa comprobación, la aplicación se reinició con la configuración del servidor portátil para mostrar las pantallas nuevas. No se ha publicado una nueva versión en GitHub como parte de esta verificación. La inspección funcional de HTML no se presenta como revisión visual completa en navegador.

---

# Verificación oficial del caso Bodega E3 — 7 de noviembre de 2026

Se aplicaron los requisitos comunes de E3 y la sección **BODEGA: GESTIÓN DE INVENTARIO Y SOLICITUDES DE SUCURSALES** del Word proporcionado. La matriz está en [docs/pauta_e3_bodega.md](docs/pauta_e3_bodega.md), y el recorrido de defensa en [README_E3.md](README_E3.md). Esta entrada sustituye el alcance preliminar registrado más abajo; las entradas anteriores se conservan como historia.

## Resultado comprobado

- **115 pruebas aprobadas con el servidor portátil 8.4.13**, 25,031 segundos, usando su lanzador de comandos Django sobre una base temporal. Configuración sin errores.
- **115 pruebas aprobadas con SQLite**, 25,206 segundos, usando `python manage.py test Core --noinput --verbosity 1`. Las pruebas usan bases temporales independientes.
- `makemigrations --check --dry-run`: sin cambios pendientes. Migraciones `0001`–`0007` aplicadas en ambas bases.
- Diagnóstico de conexión: correcto y cero migraciones pendientes. Conector instalado en ese momento: versión 2.3.0.
- El servidor utilizaba `utf8mb4` y modo `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION`; los reportes no necesitan desactivar agrupaciones estrictas.
- Los veinte reportes Bodega se ejecutan con ORM y muestran sus resultados y SQL real. Las pruebas cubren filtros, importes, agrupaciones, promedio de totales, permisos, fechas inclusivas de Chile, paginación, parámetros y contenido HTML escapado.
- Se probaron cuentas, contraseñas, sesiones, cierre POST, desactivación y accesos directos sin permisos. También CSRF real en formularios, validaciones, referencias protegidas y ausencia de escritura en GET.
- Servicios de solicitudes y stock probados con aprobación parcial, estados, stock insuficiente, rollback del despacho completo, doble despacho denegado y movimientos que conservan trazabilidad. Los ajustes de la ficha requieren el stock original si cambia la cantidad.

## Conservación de datos y muestra

Se creó `backups/db_antes_pauta_bodega_e3_20261107.sqlite3` antes de la migración `0007`. La exportación privada de transferencia E3 se generó con UTF-8, usando serializadores Django y sin sesiones ni logs administrativos. Se importaron 460 objetos (456 de negocio más cuentas/grupos) en la base `musicpro_e3` de la instancia portátil anterior.

Después de agregar la muestra se compararon **todos los campos de los 456 registros originales de negocio** contra la exportación: cero cambios. [El informe JSON](docs/verificacion_bodega_e3.json) registra conteos, preservación, motor, versión y modo SQL sin credenciales.

La muestra ficticia `DEMO-E3` se cargó solo en la instancia portátil anterior: dos categorías, dos proveedores, cuatro productos, tres sucursales, cuatro solicitudes, siete detalles y seis movimientos aplicados. Los stocks finales de los cuatro productos son 17, 12, 25 y 8. Hay una solicitud en cada estado: PENDIENTE, APROBADA, RECHAZADA y DESPACHADA. El comando es idempotente y no reescribe datos ajenos. No se falsificaron fechas para poblar el reporte del mes anterior.

En esa verificación, la instancia portátil contenía 225 productos y trece tablas propias. SQLite conservaba sus 221 productos, con el esquema ampliado y sin la nueva muestra. Las bases son independientes: los cambios posteriores hechos en una no se replican a la otra.

## Preparación local y fechas

Se verificó la suma oficial del paquete del servidor portátil 8.4.13 antes de extraerlo. Esa instancia utilizaba un directorio privado del proyecto, escuchaba en loopback 127.0.0.1:3307 y usaba credenciales aleatorias excluidas de Git. Durante esa preparación no se instaló un servicio Windows ni se modificó una instalación ajena. La instancia portátil permanece detenida; el arranque actual se realiza con WampServer, como se indica al inicio de este documento.

Las fechas de las pantallas antiguas de E2 requirieron cargar UTC y America/Santiago en las tablas internas del servidor portátil y reiniciar esa instancia. Se generaron las transiciones 1970–2100 desde `tzdata` del proyecto, acotadas para respetar el límite de rangos inversos del motor. Se comprobaron conversiones de invierno y verano de 2026. Los reportes propios de E3 utilizan límites aware calculados en Python y no dependen de esas tablas de conversión.

La revisión de las nuevas plantillas se realizó mediante compilación, peticiones/renderizado y pruebas de flujos. El diagrama Bodega E3 fue renderizado y revisado visualmente. No se presenta como realizada una revisión visual completa de todas las pantallas en un navegador.

## Qué corresponde demostrar personalmente

La pauta habla de diez consultas asignadas, pero lista veinte para Bodega. Los veinte reportes están preparados; el profesor debe confirmar cuáles diez presentará el estudiante. La defensa exige comprender el código y demostrar la autenticación, protección de URL, mantención y persistencia. Las pruebas y esta matriz no constituyen una calificación del docente.

---

# Verificación E3 — 7 de noviembre de 2026

Ampliación comprobada según el material de CRUD y seguridad compartido en el chat. La pauta oficial de E3 no está disponible en el proyecto; esta verificación acredita funcionamiento, no una calificación ni cobertura de indicadores desconocidos.

- `manage.py check`: sin errores.
- `manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `manage.py test Core --noinput`: **61 pruebas aprobadas**, 40,665 segundos. Incluye las 40 anteriores y 21 nuevas para CRUD web, login/logout y sesiones, `next` seguro, permisos efectivos, POST, CSRF real, validaciones, filtros/paginación y SQL parametrizado.
- Migración `0006_producto_precio_estado` aplicada a la base habitual; `verificar_bd`: diez tablas propias, diez internas, cero migraciones pendientes.
- Comando `configurar_roles` ejecutado: Administrador consulta/crea/edita/elimina; Operador consulta/crea/edita. No se crearon cuentas ni se asignaron roles a usuarios existentes.
- Respaldo previo: `backups/db_antes_e3_20261107.sqlite3`, generado con la API de respaldo de SQLite.
- Comparación `EXCEPT` de todas las columnas originales en las diez tablas de negocio: **cero filas originales ausentes o alteradas**. Se conservan los 221 productos; precio inicial 0,00 pendiente de definir y estado ACTIVO.
- `PRAGMA foreign_key_check`: sin violaciones.
- Las ocho plantillas nuevas compilan; se comprobaron también mediante peticiones en las pruebas. La inspección visual en navegador quedó pendiente: el control del equipo se detuvo porque no pudo verificar con suficiente certeza la URL actual del navegador Windows. No se completó la lectura de la evaluación abierta en ese navegador.

Guía de funcionamiento, alcance y defensa de QUERY: [README_E3.md](README_E3.md). La verificación histórica siguiente corresponde a la versión E2 anterior a esta ampliación.

# Verificación de base de datos — 13 de octubre de 2026 (histórica E2)

Entorno comprobado: Python 3.12.14, Django 6.1.1, Faker 40.40.0 y SQLite. Las cinco dependencias de `requirements.txt` coinciden con las del proyecto de apoyo y las versiones instaladas: asgiref 3.12.1, Django 6.1.1, Faker 40.40.0, sqlparse 0.6.0 y tzdata 2026.5. `python -m pip check` no detectó incompatibilidades.

## Diez tablas propias y migraciones

El profesor exige diez tablas propias del negocio, según confirmación del estudiante. Están implementadas como Categoria, Marca, Proveedor, Cliente, Producto, Compra, DetalleCompra, Venta, DetalleVenta y Movimiento. Todas están registradas en Django Admin.

- `python manage.py check`: sin errores.
- `python manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `python manage.py showmigrations bodega`: `0001` a `0005` aplicadas.
- `python manage.py verificar_bd`: conexión correcta, 20 tablas (10 propias y 10 internas de Django), 0 migraciones pendientes.
- `PRAGMA foreign_key_check`: ninguna violación de claves foráneas.

La migración `0005_diez_tablas_bodega` incorpora siete entidades y relaciones opcionales para conservar los registros anteriores. La carpeta de la aplicación es `Core`; mantiene la etiqueta `bodega` y el historial de migraciones.

| Tabla del negocio | Registros en la base habitual |
| --- | ---: |
| `bodega_categoria` | 3 |
| `bodega_marca` | 3 |
| `bodega_proveedor` | 3 |
| `bodega_cliente` | 5 |
| `bodega_producto` | 221 |
| `bodega_compra` | 20 |
| `bodega_detallecompra` | 20 |
| `bodega_venta` | 20 |
| `bodega_detalleventa` | 20 |
| `bodega_movimiento` | 141 |

En esa etapa, `docs/tablas_bd.md` indicaba la función y ruta del Admin de cada entidad. Ese documento histórico se retiró posteriormente del repositorio.

## Conservación y muestra completa

Antes de ampliar el esquema se creó `backups/db_antes_diez_tablas.sqlite3`: contenía 3 categorías, 201 productos y 101 movimientos. Después se compararon todas las columnas originales de esas tablas mediante `EXCEPT`, del respaldo hacia la base actual. No faltan filas ni cambió ningún valor original; se añadieron columnas y registros nuevos.

Se ejecutó una vez sobre la base habitual:

```powershell
python manage.py cargar_datos --cantidad 20 --lote 7 --semilla 42 --completo
```

La muestra añadió 20 productos, 20 compras, 20 ventas, sus respectivos detalles y 40 movimientos. Se comprobó para cada producto nuevo que el stock equivale a lo comprado menos lo vendido, que tiene un ingreso y una salida, y que ambos apuntan al documento correcto. Los registros nuevos superaron `full_clean()` y la comprobación de claves foráneas. En esa etapa, `docs/verificacion_diez_tablas.json` registró los conteos y resultados de la auditoría; el archivo histórico se retiró posteriormente del repositorio.

La carga completa calcula el stock inicial neto de los productos nuevos. La edición posterior de documentos o movimientos desde Admin requiere mantener el stock manualmente, como explica el README.

## Motivos de movimientos

La migración anterior `0004_normalizar_motivos_movimientos` sustituyó el texto de Faker por **Recepción de mercadería** en los ingresos de muestra y **Por venta** en la salida existente. Antes se creó `backups/db_antes_motivos.sqlite3`; solo cambiaron los motivos, conservando identificadores, productos, tipos, cantidades y fechas.

La nueva muestra completa mantiene esos motivos: hay 120 ingresos con motivo **Recepción de mercadería** y 21 salidas con motivo **Por venta**. El historial permite filtrar por tipo y muestra el documento vinculado cuando existe. Los movimientos antiguos pueden conservar el origen vacío.

## Pruebas automáticas y revisión visual

```powershell
python manage.py test Core --noinput --verbosity 1
```

**40 pruebas aprobadas** en 25,093 segundos con Django 6.1.1, después de retirar la interfaz web propia, sin errores del comprobador de Django. Cubren CRUD, filtros y paginación en Admin, registro y renderizado de los diez modelos, totales decimales, restricciones y relaciones protegidas, coherencia del origen de movimientos, edición de detalles vinculados, cargas completas por lotes, conservación de datos y rollback del lote fallido. También comprueban que solo se publica `/admin/` y que las antiguas rutas propias devuelven 404.

La aplicación utiliza exclusivamente Django Admin. Se retiraron `Core/views.py`, `Core/forms.py`, `Core/urls.py`, las plantillas propias, el CSS del inventario y las pruebas exclusivas del CRUD web. La configuración carga las plantillas incorporadas de Django. La arquitectura se actualizó, renderizó y revisó visualmente; el diagrama de base de datos conserva los diez modelos, 53 campos y 11 relaciones de clave foránea.

Tras retirar las vistas, `verificar_bd` confirmó los mismos conteos de las diez tablas y cero migraciones pendientes. No fue necesario cambiar modelos, generar migraciones ni modificar datos. La verificación `makemigrations --check --dry-run` informó que no hay cambios de estructura.

La imagen preparada para aquella etapa fue `docs/diagrama_bd.png`. La matriz `docs/rubrica_e2.md` y `docs/correspondencia_referencia.md` explicaban su evidencia; esos documentos históricos se retiraron posteriormente del repositorio. En esa revisión seguían pendientes GitHub público, subida a la plataforma y defensa individual; estas verificaciones no constituyen una calificación docente.

## Antecedente: pruebas de volumen del esquema anterior

Estos tiempos se midieron **antes de la ampliación a diez tablas**, con la modalidad básica de productos, lote de 1.000 y semilla 2026. Se usó un archivo SQLite temporal independiente y cargas consecutivas aditivas. La base habitual no recibió estos productos. No son mediciones de `--completo` ni una nueva ejecución sobre el esquema ampliado.

| Productos solicitados | Antes | Después | Diferencia comprobada | Tiempo observado |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 0 | 100 | 100 | 1,38 s |
| 1.000 | 100 | 1.100 | 1.000 | 0,08 s |
| 100.000 | 1.100 | 101.100 | 100.000 | 9,50 s |
| 1.000.000 | 101.100 | 1.101.100 | 1.000.000 | 73,92 s |

Se verificó cada diferencia de conteo de forma independiente y una muestra con `full_clean()`. Después se probaron 12 productos con ingresos mediante `--con-movimientos`, sin violaciones de claves foráneas. El detalle se registró en `docs/resultados_cargas.json`, archivo histórico retirado posteriormente del repositorio. Los tiempos dependen del equipo, el disco y la inicialización de Faker. [README_SEEDER.md](README_SEEDER.md) explica cómo repetir los cuatro volúmenes sobre el esquema actual en una base separada.
