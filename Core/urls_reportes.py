from django.urls import path

from . import views_reportes


urlpatterns = [path('', views_reportes.reportes, name='reportes')]
