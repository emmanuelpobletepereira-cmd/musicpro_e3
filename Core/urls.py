from django.urls import include, path

from . import views, views_catalogos, views_panel, views_reportes

app_name = 'bodega'

urlpatterns = [
    path('', views_panel.panel, name='inicio'),
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('productos/', views.productos, name='productos'),
    path('productos/nuevo/', views.producto_crear, name='producto_crear'),
    path('productos/<int:pk>/editar/', views.producto_editar, name='producto_editar'),
    path('productos/<int:pk>/eliminar/', views.producto_eliminar, name='producto_eliminar'),
    path('consultas/', views.consultas, name='consultas'),
    path('consultas/panel/', views_reportes.panel_consultas, name='panel_consultas'),
    path('catalogos/<slug:tipo>/', views_catalogos.catalogo_lista, name='catalogo_lista'),
    path('catalogos/<slug:tipo>/nuevo/', views_catalogos.catalogo_crear, name='catalogo_crear'),
    path('catalogos/<slug:tipo>/<int:pk>/editar/', views_catalogos.catalogo_editar, name='catalogo_editar'),
    path('catalogos/<slug:tipo>/<int:pk>/eliminar/', views_catalogos.catalogo_eliminar, name='catalogo_eliminar'),
    path('reportes/', include('Core.urls_reportes')),
    path('', include('Core.urls_usuarios')),
    path('', include('Core.urls_operaciones')),
    path('', include('Core.urls_panel')),
]
