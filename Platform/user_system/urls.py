#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


from . import views

app_name = 'user_system'

urlpatterns = [
    path('health_check/', views.health_check, name='health_check'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('informed_consent/', views.informed_consent, name='informed_consent'),
    path('info/', views.info, name='info'),
    path('admin/view_user_info/<int:user_id>/', views.view_user_info, name='view_user_info'),
    path('edit_info/', views.edit_info, name='edit_info'),
    path('edit_password/', views.edit_password, name='edit_password'),
    path('reset_password/<str:token_str>/', views.reset_password, name='reset_password'),
    path('forget_password/', views.forget_password, name='forget_password'),
    path('admin/', views.admin_page, name='admin_page'),
    path('admin/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin/toggle_superuser/<int:user_id>/', views.toggle_superuser, name='toggle_superuser'),
    path('admin/login_as_user/<int:user_id>/', views.login_as_user, name='login_as_user'),
    path('admin/return_to_admin/', views.return_to_admin, name='return_to_admin'),
    path('admin/informed_consent/', views.manage_informed_consent, name='manage_informed_consent'),
    path('admin/informed_consent/view/', views.view_current_consent, name='view_current_consent'),
    path('admin/extension_versions/', views.manage_extension_versions, name='manage_extension_versions'),
    path('admin/extension_versions/revert/', views.revert_latest_extension_version, name='revert_latest_extension_version'),
    path('search/', views.UserSearchView.as_view(), name='user_search'),
]
