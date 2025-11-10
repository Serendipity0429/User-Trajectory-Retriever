from django.urls import path
from . import views

urlpatterns = [
    path('', views.discussion_home, name='discussion_home'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:pk>/delete/', views.delete_post, name='delete_post'),
    path('post/<int:pk>/toggle_hidden/', views.toggle_post_hidden, name='toggle_post_hidden'),
    path('post/new/', views.create_post, name='create_post'),
    path('comment/<int:pk>/delete/', views.delete_comment, name='delete_comment'),
    path('comment/<int:pk>/toggle_hidden/', views.toggle_comment_hidden, name='toggle_comment_hidden'),
    path('bulletin/', views.manage_bulletin, name='manage_bulletin'),
    path('bulletin/<int:pk>/edit/', views.edit_bulletin, name='edit_bulletin'),
    path('bulletin/<int:pk>/delete/', views.delete_bulletin, name='delete_bulletin'),
    path('bulletin/<int:pk>/', views.bulletin_detail, name='bulletin_detail'),
    path('bulletin/<int:pk>/read_status/', views.bulletin_read_status, name='bulletin_read_status'),
    path('labels/autocomplete/', views.label_autocomplete, name='label_autocomplete'),
    path('upload_image/', views.upload_image, name='upload_image'),
]
