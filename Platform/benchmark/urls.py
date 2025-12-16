from django.urls import path
from benchmark import views

app_name = 'benchmark'

urlpatterns = [
    path("", views.home, name="home"),
    path("vanilla_llm_multi_turn/", views.vanilla_llm_multi_turn, name="vanilla_llm_multi_turn"),
    path("vanilla_llm_adhoc/", views.vanilla_llm_adhoc, name="vanilla_llm_adhoc"),
    path("rag_adhoc/", views.rag_adhoc, name="rag_adhoc"),
    path("rag_multi_turn/", views.rag_multi_turn, name="rag_multi_turn"),
    path("vanilla_agent/", views.vanilla_agent, name="vanilla_agent"),
    path("browser_agent/", views.browser_agent, name="browser_agent"), # New view
    path("api/list_runs/", views.list_runs, name="list_runs"),
    path("api/multi_turn/create_session_group/", views.create_session_group, name="create_session_group"),
    path("api/multi_turn/create_session/", views.create_session, name="create_session"),
    path("api/multi_turn/get_session/<int:session_id>/", views.get_session, name="get_session"),
    path("api/multi_turn/retry_session/<int:trial_id>/", views.retry_session, name="retry_session"),
    path("api/multi_turn/run_trial/<int:trial_id>/", views.run_trial, name="run_trial"),
    path("api/multi_turn/get_trial_trace/<int:trial_id>/", views.get_trial_trace, name="get_trial_trace"),
    path("api/load_run/<str:run_tag>/", views.load_run, name="load_run"),
    path("api/get_default_settings/", views.get_default_settings, name="get_default_settings"),
    path("api/save_llm_settings/", views.save_llm_settings, name="save_llm_settings"),
    path("api/test_llm_connection/", views.test_llm_connection, name="test_llm_connection"),
    path("api/save_run/", views.save_run, name="save_run"),
    path("api/delete_run/<str:run_tag>/", views.delete_run, name="delete_run"),
    path("api/multi_turn/delete_session/<int:session_id>/", views.delete_session, name="delete_session"),
    path("api/multi_turn/stop_session/", views.stop_session, name="stop_session"),
    path('api/multi_turn/export_session/<int:session_id>/', views.export_session, name='export_session'),
    path('api/multi_turn/batch_delete_sessions/', views.batch_delete_sessions, name='batch_delete_sessions'),
    path('api/multi_turn/delete_session_group/<int:group_id>/', views.delete_session_group, name='delete_session_group'),
    path('api/multi_turn/load_run/<int:group_id>/', views.load_vanilla_llm_multi_turn_run, name='load_vanilla_llm_multi_turn_run'),
    path('api/multi_turn/load_rag_run/<int:group_id>/', views.load_rag_multi_turn_run, name='load_rag_multi_turn_run'),
    path('api/multi_turn/load_agent_run/<int:group_id>/', views.load_agent_multi_turn_run, name='load_agent_multi_turn_run'),

    # Vanilla LLM Multi-turn Pipeline APIs
    path('api/run_vanilla_llm_multi_turn_pipeline/', views.run_vanilla_llm_multi_turn_pipeline, name='run_vanilla_llm_multi_turn_pipeline'),
    path('api/stop_vanilla_llm_multi_turn_pipeline/', views.stop_vanilla_llm_multi_turn_pipeline, name='stop_vanilla_llm_multi_turn_pipeline'),
    
    # RAG Multi-turn Pipeline APIs
    path('api/run_rag_multi_turn_pipeline/', views.run_rag_multi_turn_pipeline, name='run_rag_multi_turn_pipeline'),
    path('api/stop_rag_multi_turn_pipeline/', views.stop_rag_multi_turn_pipeline, name='stop_rag_multi_turn_pipeline'),

    # Vanilla Agent Pipeline APIs
    path('api/run_vanilla_agent_pipeline/', views.run_vanilla_agent_pipeline, name='run_vanilla_agent_pipeline'),
    path('api/stop_vanilla_agent_pipeline/', views.stop_vanilla_agent_pipeline, name='stop_vanilla_agent_pipeline'),

    # Browser Agent Pipeline APIs
    path('api/run_browser_agent_pipeline/', views.run_browser_agent_pipeline, name='run_browser_agent_pipeline'),
    path('api/stop_browser_agent_pipeline/', views.stop_browser_agent_pipeline, name='stop_browser_agent_pipeline'),



    # Vanilla LLM Ad-hoc pipeline URL
    path('api/run_vanilla_llm_adhoc_pipeline/', views.run_vanilla_llm_adhoc_pipeline, name='run_vanilla_llm_adhoc_pipeline'),
    path('api/stop_vanilla_llm_adhoc_pipeline/', views.stop_vanilla_llm_adhoc_pipeline, name='stop_vanilla_llm_adhoc_pipeline'),
    
    # RAG Ad-hoc pipeline URL
    path('api/run_rag_adhoc_pipeline/', views.run_rag_adhoc_pipeline, name='run_rag_adhoc_pipeline'),
    path('api/stop_rag_adhoc_pipeline/', views.stop_rag_adhoc_pipeline, name='stop_rag_adhoc_pipeline'),


    # LLM Settings
    # path('api/save_llm_settings/', views.save_llm_settings, name='save_llm_settings'), # Removed duplicate

    # Ad-hoc run APIs
    path('api/vanilla_llm_adhoc/list_runs/', views.list_vanilla_llm_adhoc_runs, name='list_vanilla_llm_adhoc_runs'),
    path('api/vanilla_llm_adhoc/get_run/<int:run_id>/', views.get_vanilla_llm_adhoc_run, name='get_vanilla_llm_adhoc_run'),
    path('api/vanilla_llm_adhoc/delete_run/<int:run_id>/', views.delete_vanilla_llm_adhoc_run, name='delete_vanilla_llm_adhoc_run'),
    path('api/vanilla_llm_adhoc/batch_delete_runs/', views.batch_delete_vanilla_llm_adhoc_runs, name='batch_delete_vanilla_llm_adhoc_runs'),
    path('api/web_search/', views.web_search, name='web_search'),

    # RAG APIs
    path('api/save_rag_settings/', views.save_rag_settings, name='save_rag_settings'),
    path('api/save_search_settings/', views.save_search_settings, name='save_search_settings'),

    path('api/rag_adhoc/list_runs/', views.list_rag_adhoc_runs, name='list_rag_adhoc_runs'),
    path('api/rag_adhoc/get_run/<int:run_id>/', views.get_rag_adhoc_run, name='get_rag_adhoc_run'),
    path('api/rag_adhoc/delete_run/<int:run_id>/', views.delete_rag_adhoc_run, name='delete_rag_adhoc_run'),
    path('api/rag_adhoc/batch_delete_runs/', views.batch_delete_rag_adhoc_runs, name='batch_delete_rag_adhoc_runs'),
    path('api/rag_adhoc/get_default_prompt/', views.get_default_rag_prompt, name='get_default_rag_prompt'),

    # Dataset APIs
    path('api/datasets/list/', views.dataset_list, name='dataset_list'),
    path('api/datasets/<int:dataset_id>/questions/', views.get_dataset_questions, name='get_dataset_questions'),
    path('api/datasets/upload/', views.dataset_upload, name='dataset_upload'),
    path('api/datasets/delete/<int:dataset_id>/', views.dataset_delete, name='dataset_delete'),
    path('api/datasets/sync/', views.sync_datasets, name='sync_datasets'),
    path('api/datasets/activate/<int:dataset_id>/', views.activate_dataset, name='activate_dataset'),
]

