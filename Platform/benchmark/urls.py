from django.urls import path
from . import views

app_name = 'benchmark'

urlpatterns = [
    path("naive/", views.naive_llm, name="naive_llm"),
    path("api/list_runs/", views.list_runs, name="list_runs"),
    path("api/load_run/<str:filename>/", views.load_run, name="load_run"),
    path("api/get_llm_env_vars/", views.get_llm_env_vars, name="get_llm_env_vars"),
    path("api/save_llm_settings/", views.save_llm_settings, name="save_llm_settings"),
    path("api/save_run/", views.save_run, name="save_run"),
    path("api/delete_run/<str:filename>/", views.delete_run, name="delete_run"),
]
