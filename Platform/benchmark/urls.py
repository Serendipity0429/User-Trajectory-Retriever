from django.urls import path
from . import views

app_name = 'benchmark'

urlpatterns = [
    path("multi_turn_llm/", views.multi_turn_llm, name="multi_turn_llm"),
    path("naive_llm_ad_hoc/", views.naive_llm_ad_hoc, name="naive_llm_ad_hoc"),
    path("api/list_runs/", views.list_runs, name="list_runs"),
    path("api/multi_turn/create_session/", views.create_session, name="create_session"),
    path("api/multi_turn/get_session/<int:session_id>/", views.get_session, name="get_session"),
    path("api/multi_turn/retry_session/<int:trial_id>/", views.retry_session, name="retry_session"),
    path("api/multi_turn/run_trial/<int:trial_id>/", views.run_trial, name="run_trial"),
    path("api/load_run/<str:run_tag>/", views.load_run, name="load_run"),
    path("api/get_llm_env_vars/", views.get_llm_env_vars, name="get_llm_env_vars"),
    path("api/save_llm_settings/", views.save_llm_settings, name="save_llm_settings"),
    path("api/test_llm_connection/", views.test_llm_connection, name="test_llm_connection"),
    path("api/save_run/", views.save_run, name="save_run"),
    path("api/delete_run/<str:run_tag>/", views.delete_run, name="delete_run"),
    path("api/multi_turn/delete_session/<int:session_id>/", views.delete_session, name="delete_session"),
    path('api/multi_turn/export_session/<int:session_id>/', views.export_session, name='export_session'),
    path('api/multi_turn/batch_delete_sessions/', views.batch_delete_sessions, name='batch_delete_sessions'),

    # LLM Settings
    path('api/save_llm_settings/', views.save_llm_settings, name='save_llm_settings'),
]

