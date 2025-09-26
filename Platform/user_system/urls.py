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
    path('login/', views.login, name='login'),
    path('token_login/', views.token_login, name='token_login'),
    path('logout/', views.logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('info/', views.info, name='info'),
    path('edit_info/', views.edit_info, name='edit_info'),
    path('edit_password/', views.edit_password, name='edit_password'),
    path('reset_password/<str:token_str>/', views.reset_password, name='reset_password'),
    path('forget_password/', views.forget_password, name='forget_password'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
