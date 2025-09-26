from django.urls import include, path
from django.contrib import admin
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include('user_system.urls')),
    path('task/', include('task_manager.urls')),
    path('', views.index, name='index'),
]
