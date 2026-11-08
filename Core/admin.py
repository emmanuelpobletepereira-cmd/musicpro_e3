from django.contrib import admin
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.db.models import F
from .models import (
    Categoria, Cliente, Compra, DetalleCompra, DetalleVenta, Marca,
    Movimiento, Producto, Proveedor, Venta,
)

admin.site.site_header = 'Music Pro - Bodega'
admin.site.site_title = 'Music Pro'
admin.site.index_title = 'Administración de inventario'


class AdminConFechasCompatibles(admin.ModelAdmin):
    def get_changelist_instance(self, request):
        listado = super().get_changelist_instance(request)
        conexion = connections[listado.queryset.db]
        # La navegación por años/meses requiere zonas en el servidor. Los
        # filtros laterales usan límites de fecha y siguen disponibles.
        if settings.USE_TZ and not conexion.features.has_zoneinfo_database:
            listado.date_hierarchy = None
        return listado


class StockCriticoFilter(admin.SimpleListFilter):
    title = 'estado del stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [('critico', 'Crítico'), ('normal', 'Sobre el mínimo')]

    def queryset(self, request, queryset):
        if self.value() == 'critico':
            return queryset.filter(cantidad__lte=F('stock_minimo'))
        if self.value() == 'normal':
            return queryset.filter(cantidad__gt=F('stock_minimo'))
        return queryset


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    ordering = ('nombre',)
    readonly_fields = ('id',)
    fields = ('id', 'nombre')


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'pais')
    list_filter = ('pais',)
    search_fields = ('nombre', 'pais')
    ordering = ('nombre',)
    readonly_fields = ('id',)
    fieldsets = (('Identificación de marca', {'fields': ('id', 'nombre', 'pais')}),)


@admin.register(Proveedor, Cliente)
class ContactoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'rut', 'email', 'telefono')
    search_fields = ('nombre', 'rut', 'email', 'telefono', 'direccion')
    ordering = ('nombre',)
    list_per_page = 50
    readonly_fields = ('id',)
    fieldsets = (
        ('Identificación', {'fields': ('id', 'nombre', 'rut')}),
        ('Contacto', {'fields': ('email', 'telefono', 'direccion')}),
    )


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'marca', 'estado', 'ubicacion', 'cantidad', 'stock_minimo', 'stock_critico')
    list_filter = ('estado', 'categoria', 'marca', StockCriticoFilter)
    search_fields = ('codigo', 'nombre', 'ubicacion')
    autocomplete_fields = ('categoria', 'marca')
    list_select_related = ('categoria', 'marca')
    ordering = ('id',)
    show_full_result_count = False
    show_facets = admin.ShowFacets.NEVER
    list_per_page = 50
    readonly_fields = ('id',)
    fieldsets = (
        ('Identificación', {'fields': ('id', 'codigo', 'nombre', 'categoria', 'marca')}),
        ('Estado del producto', {'fields': ('estado',)}),
        ('Almacenamiento', {'fields': ('ubicacion',)}),
        ('Control de stock', {
            'fields': ('cantidad', 'stock_minimo'),
            'description': 'El stock se administra manualmente. Los movimientos registran el historial.',
        }),
    )

    @admin.display(boolean=True, description='Stock crítico')
    def stock_critico(self, obj):
        return obj.cantidad <= obj.stock_minimo


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    autocomplete_fields = ('producto',)
    fields = ('producto', 'cantidad', 'costo_unitario', 'subtotal')
    readonly_fields = ('subtotal',)
    extra = 0
    show_change_link = True

    @admin.display(description='Subtotal')
    def subtotal(self, obj):
        if obj.cantidad is None or obj.costo_unitario is None:
            return '-'
        return obj.subtotal


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    autocomplete_fields = ('producto',)
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')
    readonly_fields = ('subtotal',)
    extra = 0
    show_change_link = True

    @admin.display(description='Subtotal')
    def subtotal(self, obj):
        if obj.cantidad is None or obj.precio_unitario is None:
            return '-'
        return obj.subtotal


@admin.register(Compra)
class CompraAdmin(AdminConFechasCompatibles):
    list_display = ('id', 'numero', 'proveedor', 'fecha')
    list_filter = ('fecha', 'proveedor')
    search_fields = ('numero', 'proveedor__nombre', 'proveedor__rut', 'observaciones')
    autocomplete_fields = ('proveedor',)
    list_select_related = ('proveedor',)
    ordering = ('-fecha', '-id')
    date_hierarchy = 'fecha'
    list_per_page = 50
    readonly_fields = ('id', 'total')
    fieldsets = (
        ('Documento de compra', {'fields': ('id', 'numero', 'proveedor', 'fecha')}),
        ('Resumen', {'fields': ('observaciones', 'total')}),
    )
    inlines = (DetalleCompraInline,)


@admin.register(Venta)
class VentaAdmin(AdminConFechasCompatibles):
    list_display = ('id', 'numero', 'cliente', 'fecha')
    list_filter = ('fecha', 'cliente')
    search_fields = ('numero', 'cliente__nombre', 'cliente__rut', 'observaciones')
    autocomplete_fields = ('cliente',)
    list_select_related = ('cliente',)
    ordering = ('-fecha', '-id')
    date_hierarchy = 'fecha'
    list_per_page = 50
    readonly_fields = ('id', 'total')
    fieldsets = (
        ('Documento de venta', {'fields': ('id', 'numero', 'cliente', 'fecha')}),
        ('Resumen', {'fields': ('observaciones', 'total')}),
    )
    inlines = (DetalleVentaInline,)


@admin.register(DetalleCompra)
class DetalleCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra', 'producto', 'cantidad', 'costo_unitario', 'subtotal')
    list_filter = ('compra__fecha',)
    search_fields = ('compra__numero', 'producto__codigo', 'producto__nombre')
    autocomplete_fields = ('compra', 'producto')
    list_select_related = ('compra', 'producto')
    ordering = ('-id',)
    list_per_page = 50
    readonly_fields = ('id', 'subtotal')
    fieldsets = (
        ('Documento y producto', {'fields': ('id', 'compra', 'producto')}),
        ('Importes', {'fields': ('cantidad', 'costo_unitario', 'subtotal')}),
    )


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'venta', 'producto', 'cantidad', 'precio_unitario', 'subtotal')
    list_filter = ('venta__fecha',)
    search_fields = ('venta__numero', 'producto__codigo', 'producto__nombre')
    autocomplete_fields = ('venta', 'producto')
    list_select_related = ('venta', 'producto')
    ordering = ('-id',)
    list_per_page = 50
    readonly_fields = ('id', 'subtotal')
    fieldsets = (
        ('Documento y producto', {'fields': ('id', 'venta', 'producto')}),
        ('Importes', {'fields': ('cantidad', 'precio_unitario', 'subtotal')}),
    )


@admin.register(Movimiento)
class MovimientoAdmin(AdminConFechasCompatibles):
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.stock_aplicado)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.stock_aplicado)

    def delete_queryset(self, request, queryset):
        if queryset.filter(stock_aplicado=True).exists():
            raise PermissionDenied('Los movimientos aplicados al stock conservan la trazabilidad y no se eliminan.')
        return super().delete_queryset(request, queryset)

    list_display = ('producto', 'tipo', 'cantidad', 'fecha', 'motivo')
    list_filter = ('tipo', 'fecha')
    search_fields = (
        'producto__codigo', 'producto__nombre', 'motivo',
        'detalle_compra__compra__numero', 'detalle_venta__venta__numero',
    )
    autocomplete_fields = ('producto', 'detalle_compra', 'detalle_venta')
    list_select_related = (
        'producto', 'detalle_compra__compra', 'detalle_venta__venta',
    )
    ordering = ('-fecha', '-id')
    show_full_result_count = False
    show_facets = admin.ShowFacets.NEVER
    date_hierarchy = 'fecha'
    list_per_page = 50
    readonly_fields = ('id',)
    fieldsets = (
        ('Producto y operación', {'fields': ('id', 'producto', 'tipo', 'cantidad')}),
        ('Trazabilidad', {'fields': ('fecha', 'motivo')}),
        ('Documento de origen', {
            'fields': ('detalle_compra', 'detalle_venta'),
            'description': (
                'Vincula ingresos con detalles de compra y salidas con detalles de venta. '
                'Los movimientos anteriores pueden conservarse sin documento. '
                'Registrar documentos y movimientos no modifica el stock automáticamente.'
            ),
        }),
    )
