#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path


from . import views

app_name = "user_system"

urlpatterns = [
    path("health_check/", views.health_check, name="health_check"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("signup/", views.signup, name="signup"),
    path("informed_consent/", views.informed_consent, name="informed_consent"),
    path("info/", views.info, name="info"),
    path("edit_info/", views.edit_info, name="edit_info"),
    path("edit_password/", views.edit_password, name="edit_password"),
    path(
        "reset_password/<str:token_str>/", views.reset_password, name="reset_password"
    ),
    path("password_reset_sent/", views.password_reset_sent, name="password_reset_sent"),
    path("forget_password/", views.forget_password, name="forget_password"),
    path("search/", views.UserSearchView.as_view(), name="user_search"),
    path("check_web_session/", views.check_web_session, name="check_web_session"),
]