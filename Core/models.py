from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField('descripción', blank=True)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    pais = models.CharField('país', max_length=80, blank=True)

    class Meta:
        verbose_name = 'marca'
        verbose_name_plural = 'marcas'

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    rut = models.CharField('RUT', max_length=12, unique=True)
    email = models.EmailField('correo electrónico', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    direccion = models.CharField('dirección', max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'

    def __str__(self):
        return f'{self.nombre} ({self.rut})'


class Cliente(models.Model):
    nombre = models.CharField(max_length=120)
    rut = models.CharField('RUT', max_length=12, unique=True)
    email = models.EmailField('correo electrónico', blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    direccion = models.CharField('dirección', max_length=200, blank=True)

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'

    def __str__(self):
        return f'{self.nombre} ({self.rut})'


class Producto(models.Model):
    ESTADOS = [('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo')]

    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=120)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, null=True, blank=True)
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, null=True, blank=True, related_name='productos'
    )
    ubicacion = models.CharField(max_length=100)
    cantidad = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    precio = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    estado = models.CharField(max_length=8, choices=ESTADOS, default='ACTIVO')

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(precio__gte=0), name='producto_precio_no_negativo'
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=['ACTIVO', 'INACTIVO']),
                name='producto_estado_valido',
            ),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Compra(models.Model):
    numero = models.CharField('número', max_length=30, unique=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'compra'
        verbose_name_plural = 'compras'

    @property
    def total(self):
        if not self.pk:
            return Decimal('0.00')
        importe = self.detalles.aggregate(
            importe=models.Sum(
                models.F('cantidad') * models.F('costo_unitario'),
                output_field=models.DecimalField(max_digits=20, decimal_places=2),
            )
        )['importe']
        return (importe or Decimal('0.00')).quantize(Decimal('0.01'))

    def __str__(self):
        return f'Compra {self.numero}'


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:
        verbose_name = 'detalle de compra'
        verbose_name_plural = 'detalles de compras'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1), name='detalle_compra_cantidad_positiva'
            ),
            models.CheckConstraint(
                condition=models.Q(costo_unitario__gt=0), name='detalle_compra_costo_positivo'
            ),
            models.UniqueConstraint(
                fields=['compra', 'producto'], name='detalle_compra_producto_unico'
            ),
        ]

    @property
    def subtotal(self):
        if self.cantidad is None or self.costo_unitario is None:
            return Decimal('0.00')
        return self.cantidad * self.costo_unitario

    def clean(self):
        super().clean()
        if not isinstance(self.pk, int):
            return
        movimientos = Movimiento.objects.using(self._state.db or 'default').filter(
            detalle_compra_id=self.pk
        )
        errores = {}
        if isinstance(self.producto_id, int) and movimientos.exclude(
            producto_id=self.producto_id
        ).exists():
            errores['producto'] = 'El producto debe coincidir con los movimientos asociados.'
        if isinstance(self.cantidad, int) and movimientos.filter(
            cantidad__gt=self.cantidad
        ).exists():
            errores['cantidad'] = 'La cantidad no puede ser menor que la de un movimiento asociado.'
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f'{self.compra.numero} - {self.producto.codigo} ({self.cantidad})'


class Venta(models.Model):
    numero = models.CharField('número', max_length=30, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'venta'
        verbose_name_plural = 'ventas'

    @property
    def total(self):
        if not self.pk:
            return Decimal('0.00')
        importe = self.detalles.aggregate(
            importe=models.Sum(
                models.F('cantidad') * models.F('precio_unitario'),
                output_field=models.DecimalField(max_digits=20, decimal_places=2),
            )
        )['importe']
        return (importe or Decimal('0.00')).quantize(Decimal('0.01'))

    def __str__(self):
        return f'Venta {self.numero}'


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:
        verbose_name = 'detalle de venta'
        verbose_name_plural = 'detalles de ventas'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1), name='detalle_venta_cantidad_positiva'
            ),
            models.CheckConstraint(
                condition=models.Q(precio_unitario__gt=0), name='detalle_venta_precio_positivo'
            ),
            models.UniqueConstraint(
                fields=['venta', 'producto'], name='detalle_venta_producto_unico'
            ),
        ]

    @property
    def subtotal(self):
        if self.cantidad is None or self.precio_unitario is None:
            return Decimal('0.00')
        return self.cantidad * self.precio_unitario

    def clean(self):
        super().clean()
        if not isinstance(self.pk, int):
            return
        movimientos = Movimiento.objects.using(self._state.db or 'default').filter(
            detalle_venta_id=self.pk
        )
        errores = {}
        if isinstance(self.producto_id, int) and movimientos.exclude(
            producto_id=self.producto_id
        ).exists():
            errores['producto'] = 'El producto debe coincidir con los movimientos asociados.'
        if isinstance(self.cantidad, int) and movimientos.filter(
            cantidad__gt=self.cantidad
        ).exists():
            errores['cantidad'] = 'La cantidad no puede ser menor que la de un movimiento asociado.'
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f'{self.venta.numero} - {self.producto.codigo} ({self.cantidad})'


class Sucursal(models.Model):
    codigo = models.CharField('código', max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    direccion = models.CharField('dirección', max_length=200, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'sucursal'
        verbose_name_plural = 'sucursales'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Solicitud(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'), ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'), ('DESPACHADA', 'Despachada'),
    ]
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='solicitudes')
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'solicitud'
        verbose_name_plural = 'solicitudes'
        permissions = [
            ('aprobar_solicitud', 'Puede aprobar o rechazar solicitudes'),
            ('despachar_solicitud', 'Puede despachar solicitudes aprobadas'),
        ]
        constraints = [models.CheckConstraint(
            condition=models.Q(estado__in=['PENDIENTE', 'APROBADA', 'RECHAZADA', 'DESPACHADA']),
            name='solicitud_estado_valido',
        )]

    def __str__(self):
        return f'Solicitud {self.pk} - {self.sucursal.nombre}'


class DetalleSolicitud(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_solicitud')
    cantidad_solicitada = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    cantidad_aprobada = models.PositiveIntegerField(default=0)
    cantidad_despachada = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'detalle de solicitud'
        verbose_name_plural = 'detalles de solicitudes'
        constraints = [
            models.UniqueConstraint(fields=['solicitud', 'producto'], name='solicitud_producto_unico'),
            models.CheckConstraint(condition=models.Q(cantidad_solicitada__gte=1), name='solicitud_cantidad_positiva'),
            models.CheckConstraint(condition=models.Q(cantidad_aprobada__lte=models.F('cantidad_solicitada')), name='solicitud_aprobada_valida'),
            models.CheckConstraint(condition=models.Q(cantidad_despachada__lte=models.F('cantidad_aprobada')), name='solicitud_despachada_valida'),
        ]

    def __str__(self):
        return f'Solicitud {self.solicitud_id} - {self.producto.codigo}'


class Movimiento(models.Model):
    TIPOS = [('INGRESO', 'Ingreso'), ('SALIDA', 'Salida')]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=7, choices=TIPOS)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(default=timezone.now)
    motivo = models.CharField(max_length=200)
    detalle_compra = models.ForeignKey(
        DetalleCompra, on_delete=models.PROTECT, null=True, blank=True
    )
    detalle_venta = models.ForeignKey(
        DetalleVenta, on_delete=models.PROTECT, null=True, blank=True
    )
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.PROTECT, null=True, blank=True, related_name='movimientos'
    )
    stock_aplicado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'movimiento'
        verbose_name_plural = 'movimientos'
        indexes = [models.Index(fields=['-fecha', '-id'], name='mov_fecha_id_idx')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1),
                name='movimiento_cantidad_positiva',
            ),
            models.CheckConstraint(
                condition=models.Q(tipo__in=['INGRESO', 'SALIDA']),
                name='movimiento_tipo_valido',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(tipo='INGRESO', detalle_venta__isnull=True)
                    | models.Q(tipo='SALIDA', detalle_compra__isnull=True)
                ),
                name='movimiento_origen_coherente',
            ),
        ]

    def clean(self):
        super().clean()
        errores = {}
        if self.detalle_compra_id and self.tipo != 'INGRESO':
            errores['detalle_compra'] = 'Solo los ingresos pueden vincularse a una compra.'
        if self.detalle_venta_id and self.tipo != 'SALIDA':
            errores['detalle_venta'] = 'Solo las salidas pueden vincularse a una venta.'
        for campo in ('detalle_compra', 'detalle_venta'):
            if not getattr(self, f'{campo}_id'):
                continue
            try:
                detalle = getattr(self, campo)
            except (ObjectDoesNotExist, ValueError, TypeError):
                # La validación del campo informa una referencia inexistente.
                continue
            if self.producto_id and self.producto_id != detalle.producto_id:
                errores['producto'] = 'El producto debe coincidir con el detalle del documento.'
            if isinstance(self.cantidad, int) and self.cantidad > detalle.cantidad:
                errores['cantidad'] = 'La cantidad no puede superar la del detalle del documento.'
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.tipo} - {self.producto} ({self.cantidad})"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, stock_aplicado=True).exists():
            raise ValidationError('Un movimiento aplicado al stock no se puede modificar.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, stock_aplicado=True).exists():
            raise ValidationError('Un movimiento aplicado al stock no se puede eliminar.')
        return super().delete(*args, **kwargs)

