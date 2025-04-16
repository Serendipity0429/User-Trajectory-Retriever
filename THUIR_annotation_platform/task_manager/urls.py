#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.urls import include, path, re_path
from . import views

urlpatterns = [
    path('home/', views.task_home),
    path('data/', views.data),
    path('partition/', views.task_partition),
    path('annotation/', views.annotation_home),
    re_path(r'^task_annotation1/([0-9]+)/$', views.task_annotation1),
    re_path(r'^pre_query_annotation/([0-9]+)/$', views.pre_query_annotation),
    re_path(r'^query_annotation/([0-9]+)/$', views.query_annotation),
    re_path(r'^task_annotation2/([0-9]+)/$', views.task_annotation2),
    re_path(r'^show_page/([0-9]+)/$', views.show_page),
    re_path(r'^page_annotation/([0-9]+)/$', views.page_annotation),
    re_path(r'^page_annotation_submit/([0-9]+)/$', views.page_annotation_submit),
    re_path(r'^show_me_serp/([0-9]+)/$', views.show_me_serp),

    re_path(r'^pre_task_annotation/([0-9]+)/$', views.pre_task_annotation), # Preliminary task annotation
    re_path(r'^post_task_annotation/([0-9]+)/$', views.post_task_annotation), # Post task annotation
    re_path(r'^show_task_info/([0-9]+)/$', views.show_task_info), # Show task information
    path('show_tool_use_page', views.show_tool_use_page), # Show tool use page
    re_path(r'^tool_use/([0-9]+)/$', views.tool_use), # Tool use
    re_path(r'^submit_answer/([0-9]+)/$', views.submit_answer), # Submit answer
    path('cancel_task/', views.cancel_task), # Cancel task
    path('active_task/', views.active_task),
    path('initialize/', views.initialize),
]
