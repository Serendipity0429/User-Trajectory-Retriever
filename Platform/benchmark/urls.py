from django.urls import path
from benchmark import views

app_name = 'benchmark'

urlpatterns = [
    # ==========================================
    # 1. Views (HTML Pages)
    # ==========================================
    path("", views.home, name="home"),
    path("vanilla_llm/", views.vanilla_llm, name="vanilla_llm"),
    path("rag/", views.rag, name="rag"),
    path("vanilla_agent/", views.vanilla_agent, name="vanilla_agent"),
    path("browser_agent/", views.browser_agent, name="browser_agent"),

    # ==========================================
    # 2. API - Common / General
    # ==========================================
    path('api/web_search/', views.web_search, name='web_search'),

    # ==========================================
    # 3. API - Global Settings
    # ==========================================
    path("api/get_default_settings/", views.get_default_settings, name="get_default_settings"),
    path("api/settings/save/", views.save_settings, name="save_settings"),
    path("api/test_llm_connection/", views.test_llm_connection, name="test_llm_connection"),

    # ==========================================
    # 3.1. API - Metrics
    # ==========================================
    path("api/metrics/calculate/", views.calculate_metrics, name="calculate_metrics"),
    path("api/metrics/colors/", views.get_metric_colors, name="get_metric_colors"),
    path("api/metrics/schema/", views.get_metric_schema, name="get_metric_schema"),

    # ==========================================
    # 4. API - Datasets
    # ==========================================
    path('api/datasets/list/', views.dataset_list, name='dataset_list'),
    path('api/datasets/<int:dataset_id>/questions/', views.get_dataset_questions, name='get_dataset_questions'),
    path('api/datasets/upload/', views.dataset_upload, name='dataset_upload'),
    path('api/datasets/delete/<int:dataset_id>/', views.dataset_delete, name='dataset_delete'),
    path('api/datasets/sync/', views.sync_datasets, name='sync_datasets'),
    path('api/datasets/activate/<int:dataset_id>/', views.activate_dataset, name='activate_dataset'),

    # ==========================================
    # 5. API - Multi-Turn Sessions
    # ==========================================
    # Session Management
    path("api/sessions/create_session_group/", views.create_session_group, name="create_session_group"),
    path("api/sessions/create_session/", views.create_session, name="create_session"),
    path("api/sessions/get_session/<int:session_id>/", views.get_session, name="get_session"),
    path("api/sessions/delete_session/<int:session_id>/", views.delete_session, name="delete_session"),
    path('api/sessions/batch_delete_sessions/', views.batch_delete_sessions, name='batch_delete_sessions'),
    path('api/sessions/delete_session_group/<int:group_id>/', views.delete_session_group, name='delete_session_group'),
    path('api/sessions/rename_session_group/<int:group_id>/', views.rename_session_group, name='rename_session_group'),
    path('api/sessions/export_session/<int:session_id>/', views.export_session, name='export_session'),
    path('api/sessions/export_run/<int:group_id>/', views.export_run, name='export_run'),
    path('api/sessions/import/', views.import_data, name='import_data'),
    path('api/sessions/validate_import/', views.validate_import, name='validate_import'),
    
    # Trial Execution
    path("api/sessions/run_trial/<int:trial_id>/", views.run_trial, name="run_trial"),
    path("api/sessions/retry_session/<int:trial_id>/", views.retry_session, name="retry_session"),
    path("api/sessions/stop_session/", views.stop_session, name="stop_session"),
    path("api/sessions/get_trial_trace/<int:trial_id>/", views.get_trial_trace, name="get_trial_trace"),
    path("api/sessions/get_trial_prompt/<int:trial_id>/", views.get_trial_prompt, name="get_trial_prompt"),

    # Run Loading
    path('api/sessions/load_vanilla_run/<int:group_id>/', views.load_benchmark_run, {'pipeline_category': 'vanilla_llm'}, name='load_vanilla_llm_run'),
    path('api/sessions/load_rag_run/<int:group_id>/', views.load_benchmark_run, {'pipeline_category': 'rag'}, name='load_rag_run'),
    path('api/sessions/load_agent_run/<int:group_id>/', views.load_benchmark_run, {'pipeline_category': 'agent_multi_turn'}, name='load_agent_multi_turn_run'),

    # ==========================================
    # 6. API - Pipelines (Streaming)
    # ==========================================
    path('api/pipeline/start/<str:pipeline_type>/', views.pipeline_start, name='pipeline_start'),
    path('api/pipeline/stop/<str:pipeline_type>/', views.pipeline_stop, name='pipeline_stop'),
]