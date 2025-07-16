#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.urls import include, path, re_path
from . import views

urlpatterns = [
    path('home/', views.task_home),
    path('data/', views.data),
    path('annotation/', views.annotation_home),
    path('active_task/', views.active_task),
    path('initialize/', views.initialize),
    path('show_tool_use_page/', views.show_tool_use_page), # Show tool use page
    path('tool_use/', views.tool_use), # Tool use
    path('stop_annotation/', views.stop_annotation_api), # Stop annotation API
    
    re_path(r'^pre_task_annotation/([0-9]+)/$', views.pre_task_annotation), # Preliminary task annotation
    re_path(r'^reflection_annotation/([0-9]+)/([0-9]+)/$', views.reflection_annotation), # Reflection annotation
    re_path(r'^post_task_annotation/([0-9]+)/$', views.post_task_annotation), # Post task annotation
    re_path(r'^show_task/([0-9]+)/$', views.show_task), # Show task
    re_path(r'^view_task_info/([0-9]+)/$', views.view_task_info), # View task info
    re_path(r'^submit_answer/([0-9]+)/([0-9]+)/$', views.submit_answer), # Submit answer
    re_path(r'^cancel_task/([0-9]+)/([0-9]+)/$', views.cancel_task), # Cancel task
    re_path(r'remove_task/([0-9]+)/$', views.remove_task), # Remove task

]
