
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('', RedirectView.as_view(url='/task/home/', permanent=True)),
    path('admin/', admin.site.urls),
    path('user/', include('user_system.urls')),
    path('task/', include('task_manager.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# This will serve static files in production
urlpatterns += staticfiles_urlpatterns()

handler404 = 'annotation_platform.views.custom_error_view'
