#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path, re_path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


from . import views

urlpatterns = [
    path('check/', views.check),
    path('login/', views.login),
    path('token_login/', views.token_login),
    path('logout/', views.logout),
    path('signup/', views.signup),
    path('info/', views.info),
    path('edit_info/', views.edit_info),
    path('edit_password/', views.edit_password),
    re_path(r'^reset_password/([a-zA-Z0-9]{12})/$', views.reset_password),
    path('forget_password/', views.forget_password),
    path('token_refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

