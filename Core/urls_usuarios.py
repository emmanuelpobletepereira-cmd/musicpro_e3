from django.urls import path

from . import views_usuarios


# Se integran en Core.urls para conservar el namespace bodega de la aplicación.
urlpatterns = [
    path('usuarios/', views_usuarios.usuarios, name='usuarios'),
    path('usuarios/nuevo/', views_usuarios.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views_usuarios.usuario_editar, name='usuario_editar'),
    path('usuarios/<int:pk>/desactivar/', views_usuarios.usuario_desactivar, name='usuario_desactivar'),
]
