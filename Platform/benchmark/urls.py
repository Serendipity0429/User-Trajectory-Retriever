from django.urls import path
from . import views

app_name = 'benchmark'

urlpatterns = [
    path("interactive_llm/", views.interactive_llm, name="interactive_llm"),
    path("adhoc_llm/", views.adhoc_llm, name="adhoc_llm"),
    path("api/list_runs/", views.list_runs, name="list_runs"),
    path("api/interactive/create_session_group/", views.create_session_group, name="create_session_group"),
    path("api/interactive/create_session/", views.create_session, name="create_session"),
    path("api/interactive/get_session/<int:session_id>/", views.get_session, name="get_session"),
    path("api/interactive/retry_session/<int:trial_id>/", views.retry_session, name="retry_session"),
    path("api/interactive/run_trial/<int:trial_id>/", views.run_trial, name="run_trial"),
    path("api/load_run/<str:run_tag>/", views.load_run, name="load_run"),
    path("api/get_llm_env_vars/", views.get_llm_env_vars, name="get_llm_env_vars"),
    path("api/save_llm_settings/", views.save_llm_settings, name="save_llm_settings"),
    path("api/test_llm_connection/", views.test_llm_connection, name="test_llm_connection"),
    path("api/save_run/", views.save_run, name="save_run"),
    path("api/delete_run/<str:run_tag>/", views.delete_run, name="delete_run"),
    path("api/interactive/delete_session/<int:session_id>/", views.delete_session, name="delete_session"),
    path('api/interactive/export_session/<int:session_id>/', views.export_session, name='export_session'),
    path('api/interactive/batch_delete_sessions/', views.batch_delete_sessions, name='batch_delete_sessions'),
    path('api/interactive/delete_session_group/<int:group_id>/', views.delete_session_group, name='delete_session_group'),

    # New Ad-hoc pipeline URL
    path('api/run_adhoc_pipeline/', views.run_adhoc_pipeline, name='run_adhoc_pipeline'),

    # LLM Settings
    path('api/save_llm_settings/', views.save_llm_settings, name='save_llm_settings'),

    # Ad-hoc run APIs
    path('api/adhoc/list_runs/', views.list_adhoc_runs, name='list_adhoc_runs'),
    path('api/adhoc/get_run/<int:run_id>/', views.get_adhoc_run, name='get_adhoc_run'),
    path('api/adhoc/delete_run/<int:run_id>/', views.delete_adhoc_run, name='delete_adhoc_run'),
]

