from django.urls import path

from . import views_panel


urlpatterns = [
    path('productos/<int:pk>/', views_panel.producto_detalle, name='producto_detalle'),
]
