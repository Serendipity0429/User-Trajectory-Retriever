#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.urls import path
from . import views

app_name = 'task_manager'

urlpatterns = [
    path('home/', views.task_home, name='home'),
    path('data/', views.data, name='data'),
    path('annotation/', views.annotation_home, name='annotation_home'),
    path('active_task/', views.active_task, name='active_task'),
    path('get_task_info/', views.get_task_info, name='get_task_info'),
    path('initialize/', views.initialize, name='initialize'),
    path('show_tool_use_page/', views.show_tool_use_page, name='show_tool_use_page'), # Show tool use page
    path('tool_use/', views.tool_use, name='tool_use'), # Tool use
    path('stop_annotation/', views.stop_annotation_api, name='stop_annotation'), # Stop annotation API
    path('auth_redirect/', views.auth_redirect, name='auth_redirect'), # Auth redirect  
    
    path('pre_task_annotation/<int:timestamp>/', views.pre_task_annotation, name='pre_task_annotation'), # Preliminary task annotation
    path(
        "reflection_annotation/<int:task_trial_id>/",
        views.reflection_annotation,
        name="reflection_annotation",
    ),
    path('post_task_annotation/<int:task_id>/', views.post_task_annotation, name='post_task_annotation'), # Post task annotation
    path('show_task/<int:task_id>/', views.show_task, name='show_task'), # Show task
    path('view_task_info/<int:task_id>/', views.view_task_info, name='view_task_info'), # View task info
    path('submit_answer/<int:task_id>/<int:timestamp>/', views.submit_answer, name='submit_answer'), # Submit answer
    path('cancel_annotation/<int:task_id>/<int:end_timestamp>/', views.cancel_annotation, name='cancel_annotation'), # Cancel annotation
    path('remove_task/<int:task_id>/', views.remove_task, name='remove_task'), # Remove task

]
