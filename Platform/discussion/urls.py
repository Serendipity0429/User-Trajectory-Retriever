from django.urls import path
from . import views

urlpatterns = [
    path('', views.discussion_home, name='discussion_home'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:pk>/delete/', views.delete_post, name='delete_post'),
    path('post/new/', views.create_post, name='create_post'),
    path('bulletin/', views.manage_bulletin, name='manage_bulletin'),
    path('bulletin/<int:pk>/edit/', views.edit_bulletin, name='edit_bulletin'),
    path('bulletin/<int:pk>/delete/', views.delete_bulletin, name='delete_bulletin'),
    path('bulletin/<int:pk>/', views.bulletin_detail, name='bulletin_detail'),
    path('labels/autocomplete/', views.label_autocomplete, name='label_autocomplete'),
    path('upload_image/', views.upload_image, name='upload_image'),
]
