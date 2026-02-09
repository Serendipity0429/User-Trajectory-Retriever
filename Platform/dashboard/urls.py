#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_page, name="index"),
    path("statistics/", views.admin_statistics_api, name="admin_statistics_api"),
    path("delete/<int:user_id>/", views.delete_user, name="delete_user"),
    path("toggle_superuser/<int:user_id>/", views.toggle_superuser, name="toggle_superuser"),
    path("login_as_user/<int:user_id>/", views.login_as_user, name="login_as_user"),
    path("return_to_admin/", views.return_to_admin, name="return_to_admin"),
    path("informed_consent/", views.manage_informed_consent, name="manage_informed_consent"),
    path("informed_consent/view/", views.view_current_consent, name="view_current_consent"),
    path("extension_versions/", views.manage_extension_versions, name="manage_extension_versions"),
    path("extension_versions/revert/", views.revert_latest_extension_version, name="revert_latest_extension_version"),
    path("view_user_info/<int:user_id>/", views.view_user_info, name="view_user_info"),
    # Data Export/Import
    path("export/users/", views.export_users_list, name="export_users_list"),
    path("export/datasets/", views.export_datasets_list, name="export_datasets_list"),
    path("export/preview/", views.export_preview, name="export_preview"),
    path("export/start/", views.start_export, name="start_export"),
    path("export/progress/<str:export_id>/", views.export_progress, name="export_progress"),
    path("export/download/<str:export_id>/", views.download_export, name="download_export"),
    path("import/preview/", views.import_preview, name="import_preview"),
    path("import/execute/", views.import_data, name="import_data"),
    path("import/progress/<str:import_id>/", views.import_progress, name="import_progress"),
]
