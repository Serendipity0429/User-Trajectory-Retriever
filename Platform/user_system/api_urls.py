#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

from . import views

urlpatterns = [
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/login/", views.token_login, name="token_login"),
]
