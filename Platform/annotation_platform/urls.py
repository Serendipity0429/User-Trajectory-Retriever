
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('', RedirectView.as_view(url='/task/home/', permanent=True), name='home'),
    path('admin/', admin.site.urls),
    path('task/', include('task_manager.urls')),
    path('user/', include('user_system.urls')),
    path('api/user/', include(('user_system.api_urls', 'user_system'), namespace='user_system_api')),
    path('discussion/', include('discussion.urls')),
    path('message/', include('msg_system.urls')),
    path('captcha/', include('captcha.urls')),
]

# This will serve static files in production
urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'annotation_platform.views.custom_error_view'
handler403 = 'annotation_platform.views.custom_permission_denied_view'
handler400 = 'annotation_platform.views.custom_bad_request_view'
handler500 = 'annotation_platform.views.custom_server_error_view'
