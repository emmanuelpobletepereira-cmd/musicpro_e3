from django.urls import path

from . import views_operaciones as views

urlpatterns = [
    path('solicitudes/', views.solicitudes, name='solicitudes'),
    path('solicitudes/nueva/', views.solicitud_crear, name='solicitud_crear'),
    path('solicitudes/<int:pk>/', views.solicitud_detalle, name='solicitud_detalle'),
    path('solicitudes/<int:pk>/editar/', views.solicitud_editar, name='solicitud_editar'),
    path('solicitudes/<int:pk>/eliminar/', views.solicitud_eliminar, name='solicitud_eliminar'),
    path('solicitudes/<int:pk>/aprobar/', views.solicitud_aprobar, name='solicitud_aprobar'),
    path('solicitudes/<int:pk>/rechazar/', views.solicitud_rechazar, name='solicitud_rechazar'),
    path('solicitudes/<int:pk>/despachar/', views.solicitud_despachar, name='solicitud_despachar'),
    path('movimientos/', views.movimientos, name='movimientos'),
    path('movimientos/nuevo/', views.movimiento_crear, name='movimiento_crear'),
]
