from django.db import models
from django.views.decorators.http import require_POST, require_http_methods
from asgiref.sync import async_to_sync, sync_to_async
import re
import csv
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
import openai
from decouple import config
import os
import json
from user_system.decorators import admin_required
from django.db import OperationalError
from core.utils import print_debug, print_json_debug, redis_client

import httpx
from task_manager.utils import check_answer_rule, check_answer_llm
from .search_utils import get_search_engine
from .utils import count_questions_in_file, handle_api_error, handle_async_api_error, print_debug
from .models import (
    LLMSettings,
    SearchSettings,
    MultiTurnRun,
    MultiTurnSession,
    MultiTurnTrial,
    AdhocRun,
    AdhocResult,
    BenchmarkDataset,
    AgentSettings,
)
from .forms import BenchmarkDatasetForm

from datetime import datetime

# Import from the new pipelines module
from .pipelines.base import (
    BaseMultiTurnPipeline,
    serialize_events,
    serialize_events_async,
)
from .pipelines.vanilla import (
    VanillaLLMAdhocPipeline,
    VanillaLLMMultiTurnPipeline,
)
from .pipelines.rag import (
    RagAdhocPipeline,
    RagMultiTurnPipeline,
)
from .pipelines.agent import (
    VanillaAgentPipeline,
    BrowserAgentPipeline,
)
from .pipeline_manager import PipelineManager
from .services import TrialService
from benchmark.prompts import PROMPTS

PIPELINE_CLASS_MAP = {
    'vanilla': VanillaLLMMultiTurnPipeline,
    'rag': RagMultiTurnPipeline,
    'vanilla_agent': VanillaAgentPipeline,
    'browser_agent': BrowserAgentPipeline,
}

# Helper functions removed - use Model.get_effective_settings() instead.


def get_trial_trace(request, trial_id):
    """
    Retrieve the real-time execution trace.
    Delegates logic to TrialService.
    """
    try:
        cursor = int(request.GET.get('cursor', 0))
        response_data = TrialService.get_trace_data(trial_id, cursor)
        return JsonResponse(response_data)
    except Exception as e:
        print_debug(f"View Error in get_trial_trace: {e}")
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@admin_required
def home(request):
    settings = LLMSettings.get_effective_settings()
    search_settings = SearchSettings.get_effective_settings()
    agent_settings = AgentSettings.get_effective_settings()
    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "llm_settings": settings,
        "search_settings": search_settings,
        "agent_settings": agent_settings,
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }
    return render(request, "home.html", context)


@admin_required
def dataset_list(request):
    datasets = BenchmarkDataset.objects.all().order_by("-created_at")
    return JsonResponse(
        {
            "datasets": list(
                datasets.values("id", "name", "description", "created_at", "is_active")
            )
        }
    )


@admin_required
def get_dataset_questions(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)

        if not dataset.file:
            return JsonResponse({"questions": []})

        questions = []
        with dataset.file.open("r") as f:
            for line in f:
                if line.strip():
                    questions.append(json.loads(line))

        return JsonResponse({"questions": questions})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_POST
def activate_dataset(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)
        dataset.is_active = True
        dataset.save()
        return JsonResponse({"status": "ok", "active_dataset_id": dataset.id})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_POST
def dataset_upload(request):
    form = BenchmarkDatasetForm(request.POST, request.FILES)
    if form.is_valid():
        dataset = form.save(commit=False)
        try:
            # Count questions from the uploaded file
            file = request.FILES['file']
            # Save the file temporarily to count lines
            temp_path = os.path.join('/tmp', file.name)
            with open(temp_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            dataset.question_count = count_questions_in_file(temp_path)
            os.remove(temp_path) # Clean up temp file
            
            # Reset file pointer for saving
            file.seek(0) 
        except Exception as e:
            print_debug(f"Error counting questions: {e}")
            dataset.question_count = 0
        
        dataset.save()
        return JsonResponse(
            {"status": "ok", "dataset_id": dataset.id, "name": dataset.name}
        )
    else:
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)


@admin_required
@require_http_methods(["DELETE"])
def dataset_delete(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)
        dataset.delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


from django.core.files.base import ContentFile


@admin_required
@require_POST
def sync_datasets(request):
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        if not os.path.exists(data_dir):
            return JsonResponse(
                {"status": "error", "message": "Data directory not found."}, status=404
            )

        added_count = 0
        for filename in os.listdir(data_dir):
            if filename.endswith(".jsonl"):
                # Check if dataset with this name already exists
                if not BenchmarkDataset.objects.filter(name=filename).exists():
                    file_path = os.path.join(data_dir, filename)
                    with open(file_path, "r") as f:
                        content = f.read()

                    # Set hard_questions_refined.jsonl as active by default
                    is_active = filename == "hard_questions_refined.jsonl"

                    dataset = BenchmarkDataset(
                        name=filename,
                        description=f"Auto-detected from {filename}",
                        is_active=is_active,
                    )
                    # Count questions
                    dataset.question_count = count_questions_in_file(file_path)

                    # Save the file content to the FileField
                    dataset.file.save(filename, ContentFile(content))
                    dataset.save()
                    added_count += 1

        # Fallback: If hard_questions_refined.jsonl exists and no dataset is active, make it active
        if not BenchmarkDataset.objects.filter(is_active=True).exists():
            try:
                default_ds = BenchmarkDataset.objects.get(
                    name="hard_questions_refined.jsonl"
                )
                default_ds.is_active = True
                default_ds.save()
            except BenchmarkDataset.DoesNotExist:
                pass

        return JsonResponse({"status": "ok", "added": added_count})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
def vanilla_llm_adhoc(request):
    # GET request logic
    runs = AdhocRun.objects.filter(run_type='vanilla')
    selected_run = None
    run_results = []
    run_id = request.GET.get("run_id")

    if run_id:
        try:
            selected_run = get_object_or_404(AdhocRun, pk=run_id, run_type='vanilla')
            # Serialize the results to pass as JSON to the template
            run_results = list(
                selected_run.results.values(
                    "question",
                    "answer",
                    "ground_truths",
                    "is_correct_rule",
                    "is_correct_llm",
                    "full_response",
                )
            )
        except (ValueError, TypeError):
            pass  # Ignore invalid run_id

    settings_obj = LLMSettings.get_effective_settings()

    # Load questions from the file
    questions = []
    # Default fallback if no dataset is selected or found
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                data = json.loads(line)
                # Normalize ground truths
                if "answer" in data and "ground_truths" not in data:
                    data["ground_truths"] = data["answer"]
                questions.append(data)
    except FileNotFoundError:
        pass

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "runs": runs,
        "selected_run": selected_run,
        "run_results_json": json.dumps(run_results),
        "llm_settings": settings_obj,
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "questions": questions,
        "total_questions": len(questions),
        "datasets": datasets,
    }
    return render(request, "vanilla_llm_adhoc.html", context)








@admin_required
def get_default_settings(request):
    try:
        # LLM Defaults
        llm_settings = LLMSettings.get_effective_settings()
        
        # Search Defaults
        search_settings = SearchSettings.get_effective_settings()

        # Agent Defaults
        agent_settings = AgentSettings.get_effective_settings()

        config_data = {
            # LLM
            "llm_base_url": config("LLM_BASE_URL", default=llm_settings.llm_base_url),
            "llm_api_key": config("LLM_API_KEY", default=llm_settings.llm_api_key),
            "llm_model": config("LLM_MODEL", default=llm_settings.llm_model),
            
            # Search
            "search_provider": SearchSettings._meta.get_field("search_provider").get_default(),
            "serper_api_key": config("SERPER_API_KEY", default=search_settings.serper_api_key),
            "search_limit": SearchSettings._meta.get_field("search_limit").get_default(),
            "serper_fetch_full_content": SearchSettings._meta.get_field("fetch_full_content").get_default(),

            # Agent
            "agent_memory_type": agent_settings.memory_type,
        }
        return JsonResponse(config_data)
    except OperationalError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Database not migrated. Please run migrations for the 'benchmark' app.",
            },
            status=500,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
def batch_delete_sessions(request):
    try:
        data = json.loads(request.body)
        session_ids = data.get("session_ids", [])
        if not session_ids:
            return JsonResponse(
                {"status": "error", "message": "No session IDs provided."}, status=400
            )

        try:
            session_ids = [int(sid) for sid in session_ids]
        except (ValueError, TypeError):
            return JsonResponse(
                {"status": "error", "message": "Invalid session ID format."}, status=400
            )

        sessions = MultiTurnSession.objects.filter(id__in=session_ids)

        deleted_ids = list(sessions.values_list("id", flat=True))
        deleted_count = sessions.count()

        sessions.delete()

        return JsonResponse(
            {
                "status": "ok",
                "message": f"{deleted_count} sessions deleted.",
                "deleted_ids": deleted_ids,
            }
        )
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_POST
def save_llm_settings(request):
    try:
        data = json.loads(request.body)
        settings_obj = LLMSettings.load()
        settings_obj.llm_base_url = data.get("llm_base_url", "")
        settings_obj.llm_model = data.get("llm_model", "")
        settings_obj.llm_api_key = data.get("llm_api_key", "")
        settings_obj.max_retries = data.get("max_retries", 3)
        settings_obj.allow_reasoning = data.get("allow_reasoning", False)
        
        # Advanced params
        settings_obj.temperature = float(data.get("temperature", 0.0))
        settings_obj.top_p = float(data.get("top_p", 1.0))
        max_tokens_val = data.get("max_tokens")
        if max_tokens_val is not None and max_tokens_val != "":
            settings_obj.max_tokens = int(max_tokens_val)
        else:
            settings_obj.max_tokens = None
            
        settings_obj.save()
        return JsonResponse({"status": "ok"})
    except OperationalError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Database not migrated. Please run migrations for the 'benchmark' app to save settings.",
            },
            status=400,
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@admin_required
@require_POST
def test_llm_connection(request):
    try:
        data = json.loads(request.body)
        base_url = data.get("llm_base_url")
        api_key = data.get("llm_api_key")

        if not base_url or not api_key:
            return JsonResponse(
                {"status": "error", "message": "Base URL and API Key are required."}, 
                status=400,
            )

        timeout = httpx.Timeout(10.0, connect=10.0)
        client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

        # Test the connection by listing models
        models = client.models.list() # type: ignore
        
        model_list = [model.id for model in models.data]

        return JsonResponse(
            {
                "status": "ok",
                "message": f"Connection successful! Found {len(models.data)} models.",
                "models": model_list
            }
        )
    except openai.APIConnectionError as e:
        return JsonResponse(
            {"status": "error", "message": f"Connection failed: {e.__cause__}"},
            status=400,
        )
    except openai.AuthenticationError as e:
        return JsonResponse(
            {
                "status": "error",
                "message": "Authentication failed. Please check your API Key.",
            },
            status=400,
        )
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"An unexpected error occurred: {e}"},
            status=400,
        )


@admin_required
def vanilla_llm_multi_turn(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        pass

    # Load sessions and group them
    groups = (
        MultiTurnRun.objects.filter(sessions__pipeline_type='vanilla')
        .exclude(name__startswith="Ad-hoc Session")
        .prefetch_related(
            models.Prefetch(
                "sessions",
                queryset=MultiTurnSession.objects.filter(pipeline_type='vanilla').order_by("-created_at"),
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    individual_sessions = MultiTurnSession.objects.filter(
        run__name__startswith="Ad-hoc Session",
        pipeline_type='vanilla'
    ).order_by("-created_at")

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "questions": questions,
        "groups": groups,
        "individual_sessions": individual_sessions,
        "llm_settings": LLMSettings.get_effective_settings(),
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }
    return render(request, "vanilla_llm_multi_turn.html", context)


@admin_required
def rag_multi_turn(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        pass

    # Load sessions and group them
    groups = (
        MultiTurnRun.objects.filter(sessions__pipeline_type='rag')
        .exclude(name__startswith="Ad-hoc Session")
        .prefetch_related(
            models.Prefetch(
                "sessions",
                queryset=MultiTurnSession.objects.filter(pipeline_type='rag').order_by("-created_at"),
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    individual_sessions = MultiTurnSession.objects.filter(
        run__name__startswith="Ad-hoc Session",
        pipeline_type='rag'
    ).order_by("-created_at")

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "questions": questions,
        "groups": groups,
        "individual_sessions": individual_sessions,
        "llm_settings": LLMSettings.get_effective_settings(),
        "search_settings": SearchSettings.get_effective_settings(),
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }
    return render(request, "rag_multi_turn.html", context)


@admin_required
def vanilla_agent(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        pass

    # Load sessions and group them
    groups = (
        MultiTurnRun.objects.filter(sessions__pipeline_type='vanilla_agent')
        .exclude(name__startswith="Ad-hoc Session")
        .prefetch_related(
            models.Prefetch(
                "sessions",
                queryset=MultiTurnSession.objects.filter(pipeline_type='vanilla_agent').order_by("-created_at"),
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    individual_sessions = MultiTurnSession.objects.filter(
        run__name__startswith="Ad-hoc Session",
        pipeline_type='vanilla_agent'
    ).order_by("-created_at")

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "questions": questions,
        "groups": groups,
        "individual_sessions": individual_sessions,
        "llm_settings": LLMSettings.get_effective_settings(),
        "search_settings": SearchSettings.get_effective_settings(),
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }
    return render(request, "vanilla_agent.html", context)


@admin_required
def rag_adhoc(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                data = json.loads(line)
                if "answer" in data and "ground_truths" not in data:
                    data["ground_truths"] = data["answer"]
                questions.append(data)
    except FileNotFoundError:
        pass
    datasets = BenchmarkDataset.objects.all().order_by("-created_at")
    context = {
        "questions": questions,
        "total_questions": len(questions),
        "llm_settings": LLMSettings.get_effective_settings(),
        "search_settings": SearchSettings.get_effective_settings(),
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }

    return render(request, "rag_adhoc.html", context)




@admin_required
@require_POST
def save_search_settings(request):
    try:
        data = json.loads(request.body)
        settings = SearchSettings.load()
        settings.search_provider = data.get("search_provider", settings.search_provider)
        settings.serper_api_key = data.get("serper_api_key", settings.serper_api_key)
        settings.search_limit = int(data.get("search_limit", settings.search_limit))
        settings.fetch_full_content = data.get(
            "serper_fetch_full_content", settings.fetch_full_content
        )
        settings.save()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@admin_required
@require_POST
def save_agent_settings(request):
    try:
        data = json.loads(request.body)
        settings = AgentSettings.load()
        settings.memory_type = data.get("memory_type", settings.memory_type)
        settings.save()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@admin_required
def list_rag_adhoc_runs(request):
    try:
        runs = AdhocRun.objects.filter(run_type='rag').values(
            "id", "name", "created_at", "accuracy"
        ).order_by("-created_at")
        return JsonResponse({"runs": list(runs)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
def get_rag_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id, run_type='rag')
        results = list(
            run.results.values(
                "question",
                "answer",
                "full_response",
                "ground_truths",
                "is_correct_rule",
                "is_correct_llm",
                "num_docs_used",
                "search_results",
            )
        )

        # Prefer snapshot settings, fallback to empty dict
        settings_data = {}
        if run.settings_snapshot:
            settings_data = run.settings_snapshot
        run_data = {
            "id": run.id,
            "name": run.name,
            "created_at": run.created_at,
            "accuracy": run.accuracy,
            "total_questions": run.total_questions,
            "correct_answers": run.correct_answers,
            "settings": settings_data,
            "results": results,
        }

        return JsonResponse(run_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
@require_http_methods(["DELETE"])
def delete_rag_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id, run_type='rag')
        run.delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_POST
def batch_delete_rag_adhoc_runs(request):
    try:
        data = json.loads(request.body)
        run_ids = data.get("run_ids", [])
        if not run_ids:
            return JsonResponse(
                {"status": "error", "message": "No run IDs provided."}, status=400
            )

        runs = AdhocRun.objects.filter(id__in=run_ids, run_type='rag')
        deleted_count = runs.count()
        runs.delete()

        return JsonResponse(
            {"status": "ok", "message": f"{deleted_count} runs deleted."}
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_POST
def batch_delete_vanilla_llm_adhoc_runs(request):
    try:
        data = json.loads(request.body)
        run_ids = data.get("run_ids", [])
        if not run_ids:
            return JsonResponse(
                {"status": "error", "message": "No run IDs provided."}, status=400
            )

        runs = AdhocRun.objects.filter(id__in=run_ids, run_type='vanilla')
        deleted_count = runs.count()
        runs.delete()

        return JsonResponse(
            {"status": "ok", "message": f"{deleted_count} runs deleted."}
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@require_POST
def create_session_group(request):
    try:
        data = json.loads(request.body)
        name = data.get(
            "name", f"Pipeline Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        group = MultiTurnRun.objects.create(name=name)
        return JsonResponse({"group_id": group.id, "group_name": group.name})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_POST
@handle_api_error
def create_session(request):
    data = json.loads(request.body)
    question_text = data.get("question")
    ground_truths = data.get("ground_truths")
    group_id = data.get("group_id")
    raw_pipeline_type = data.get("pipeline_type", "vanilla_llm_multi_turn")

    if not question_text or not ground_truths:
        return JsonResponse(
            {"error": "Question and ground truths are required."}, status=400
        )

    # Normalize pipeline type string
    pipeline_type = 'vanilla'
    if "rag" in raw_pipeline_type and "agent" not in raw_pipeline_type:
        pipeline_type = 'rag'
    elif "browser_agent" in raw_pipeline_type:
        pipeline_type = 'browser_agent'
    elif "vanilla_agent" in raw_pipeline_type:
        pipeline_type = 'vanilla_agent'
    
    # Determine settings for snapshot
    llm_settings = LLMSettings.get_effective_settings()
    snapshot = {
        "llm_settings": {
            "llm_base_url": llm_settings.llm_base_url,
            "llm_model": llm_settings.llm_model,
            "max_retries": llm_settings.max_retries,
        }
    }

    if pipeline_type != 'vanilla':
         search_settings = SearchSettings.get_effective_settings()
         snapshot["search_settings"] = {
            "search_provider": search_settings.search_provider,
            "search_limit": search_settings.search_limit,
            "serper_fetch_full_content": search_settings.fetch_full_content,
         }

    # Ensure Group exists
    if group_id:
        group = get_object_or_404(MultiTurnRun, pk=group_id)
    else:
        # Create a new ad-hoc group for this single session
        group_name = (
            f"Ad-hoc Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        group = MultiTurnRun.objects.create(
            name=group_name, settings_snapshot=snapshot
        )

    session = MultiTurnSession.objects.create(
        question=question_text,
        ground_truths=ground_truths,
        run=group,
        pipeline_type=pipeline_type
    )

    trial = MultiTurnTrial.objects.create(
        session=session, trial_number=1, status="processing"
    )

    return JsonResponse({"session_id": session.id, "trial_id": trial.id})


@admin_required
def get_session(request, session_id):
    try:
        session = MultiTurnSession.objects.select_related("run").get(
            pk=session_id
        )
    except MultiTurnSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)
    
    if session.pipeline_type == 'vanilla':
        pipeline_type = "vanilla_llm_multi_turn"
    elif session.pipeline_type == 'vanilla_agent':
        pipeline_type = "vanilla_agent"
    elif session.pipeline_type == 'browser_agent': # New pipeline type
        pipeline_type = "browser_agent"
    else:
        pipeline_type = "rag_multi_turn"

    # Resolve settings snapshot from run
    snapshot = session.run.settings_snapshot if session.run else {}

    max_retries = 3  # Default
    if snapshot and "llm_settings" in snapshot:
        max_retries = snapshot["llm_settings"].get("max_retries", 3)

    if session.pipeline_type == 'rag':
        trials = list(
            session.trials.values(
                "id",
                "trial_number",
                "answer",
                "feedback",
                "is_correct",
                "created_at",
                "status",
                "search_query",
                "search_results",
                "full_response",
            )
        )

    else:
        trials = list(
            session.trials.values(
                "id",
                "trial_number",
                "answer",
                "feedback",
                "is_correct",
                "created_at",
                "status",
                "full_response",
            )
        )

    return JsonResponse(
        {
            "session": {
                "id": session.id,
                "question": session.question,
                "ground_truths": session.ground_truths,
                "is_completed": session.is_completed,
                "created_at": session.created_at,
                "max_retries": max_retries,
                "group_id": session.run_id, # Run ID
                "pipeline_type": pipeline_type,
                "settings": snapshot,
            },
            "trials": trials,
        }
    )


@admin_required
@require_POST
def retry_session(request, trial_id):
    try:
        data = json.loads(request.body)
        feedback = data.get("feedback")
        is_correct = data.get("is_correct")
        try:
            original_trial = MultiTurnTrial.objects.select_related(
                "session", "session__run"
            ).get(pk=trial_id)
        except MultiTurnTrial.DoesNotExist:
             return JsonResponse({"error": "Trial not found"}, status=404)

        original_trial.feedback = feedback

        original_trial.is_correct = is_correct

        original_trial.save()

        session = original_trial.session

        # Resolve snapshot from run
        snapshot = session.run.settings_snapshot if session.run else {}

        max_retries = 3
        if snapshot and "llm_settings" in snapshot:
            max_retries = snapshot["llm_settings"].get("max_retries", 3)

        if is_correct:
            session.is_completed = True
            session.save()
            return JsonResponse({"status": "completed", "session_id": session.id})

        if session.trials.count() >= max_retries:
            session.is_completed = True
            session.save()
            return JsonResponse(
                {"status": "max_retries_reached", "session_id": session.id}
            )

        new_trial = MultiTurnTrial.objects.create(
            session=session,
            trial_number=original_trial.trial_number + 1,
            status="processing",
        )

        return JsonResponse({"status": "retrying", "new_trial_id": new_trial.id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
@handle_api_error
def run_trial(request, trial_id):
    trial = get_object_or_404(MultiTurnTrial.objects.select_related("session", "session__run"), pk=trial_id)
    session = trial.session
    snapshot = session.run.settings_snapshot if session.run else {}

    # Resolve LLM Settings
    llm_s = snapshot.get("llm_settings", {})
    base_url = llm_s.get("llm_base_url")
    model = llm_s.get("llm_model")
    api_key = config("LLM_API_KEY", default=None)

    # Fallback to DB defaults if missing
    if not api_key or not model:
        db_settings = LLMSettings.get_effective_settings()
        if not api_key:
            api_key = config("LLM_API_KEY", default=db_settings.llm_api_key)
        if not base_url:
            base_url = config("LLM_BASE_URL", default=db_settings.llm_base_url)
        if not model:
            model = db_settings.llm_model or config("LLM_MODEL", default="gpt-4o")

    common_kwargs = {
        "base_url": base_url, 
        "api_key": api_key, 
        "model": model, 
        "max_retries": 1
    }

    pipeline_type = session.pipeline_type
    
    if pipeline_type == 'browser_agent':
         # Browser Agent uses PipelineManager (Async)
        factory_kwargs = {
            **common_kwargs,
            "pipeline_id": session.run_tag,
        }
        answer, is_correct, search_results, error_msg = PipelineManager.get_instance().run_trial(
            session.id, trial.id, factory_kwargs
        )
        if error_msg:
            raise Exception(error_msg)
    
    else:
        # Synchronous Pipelines
        PipelineClass = PIPELINE_CLASS_MAP.get(pipeline_type, VanillaLLMMultiTurnPipeline)
        pipeline = PipelineClass(**common_kwargs)
        
        answer, is_correct, search_results = pipeline.run_single_turn(session, trial)

    if is_correct:
        session.is_completed = True
        session.save()

    num_docs_used = len(search_results) if search_results else 0

    return JsonResponse(
        {
            "answer": answer,
            "trial_id": trial.id,
            "is_correct": is_correct,
            "num_docs_used": num_docs_used,
        }
    )


@admin_required
@require_POST
def stop_session(request):
    try:
        data = json.loads(request.body)
        session_id = data.get("session_id")
        if not session_id:
             return JsonResponse({"status": "error", "message": "Session ID required"}, status=400)
             
        session = get_object_or_404(MultiTurnSession, pk=session_id)
        
        # Find processing trials
        processing_trials = session.trials.filter(status='processing')
        
        # Clear Redis cache for these trials
        for trial in processing_trials:
            redis_client.delete(f"trial_status:{trial.id}")
            redis_client.delete(f"trial_trace:{trial.id}")
        
        # Mark processing trials as error (stopped)
        processing_trials.update(status='error', feedback='Session stopped by user.')
        
        # Close pipeline resources
        PipelineManager.get_instance().close_session(session_id)
        
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_http_methods(["DELETE"])
def delete_session(request, session_id):
    try:
        try:
            session = MultiTurnSession.objects.get(pk=session_id)
            session.delete()
        except MultiTurnSession.DoesNotExist:
             pass  # Session already deleted

        # Ensure any persistent browser session is closed
        PipelineManager.get_instance().close_session(session_id)

        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@admin_required
@require_http_methods(["DELETE"])
def delete_session_group(request, group_id):
    try:
        group = get_object_or_404(MultiTurnRun, pk=group_id)
        group.delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def _get_common_llm_settings(request):
    """
    Helper to extract LLM settings from request or DB defaults.
    """
    db_settings = LLMSettings.get_effective_settings()
    base_url = request.POST.get("llm_base_url") or db_settings.llm_base_url
    api_key = request.POST.get("llm_api_key") or db_settings.llm_api_key
    model = request.POST.get("llm_model") or db_settings.llm_model or "gpt-3.5-turbo"
    max_retries = int(request.POST.get("max_retries", 3))
    return base_url, api_key, model, max_retries


@handle_api_error
def _run_pipeline_generic(request, pipeline_class, redis_prefix_template, **kwargs):
    """
    Generic handler for running synchronous pipelines.
    """
    base_url, api_key, model, max_retries = _get_common_llm_settings(request)
    
    pipeline_id = request.POST.get("pipeline_id")
    dataset_id = request.POST.get("dataset_id")

    if not api_key:
        return JsonResponse(
            {"error": "An API Key is required to run the benchmark."}, status=400
        )

    # Construct Redis key
    redis_key = None
    if pipeline_id:
        try:
            # Attempt to format with kwargs
            prefix = redis_prefix_template.format(**kwargs)
        except KeyError:
            # Fallback if format fails or no placeholders
            prefix = redis_prefix_template
            
        redis_key = f"{prefix}:{pipeline_id}"
        redis_client.set(redis_key, "1", ex=3600)

    # Prepare Constructor Arguments
    constructor_args = {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "pipeline_id": pipeline_id,
        "dataset_id": dataset_id,
    }
    
    if issubclass(pipeline_class, (BaseMultiTurnPipeline, VanillaAgentPipeline)):
            constructor_args["max_retries"] = max_retries
            
    # Add specific kwargs
    constructor_args.update(kwargs)

    pipeline = pipeline_class(**constructor_args)

    return StreamingHttpResponse(
        serialize_events(pipeline.run()), content_type="application/json"
    )


@handle_api_error
def _stop_pipeline_generic(request, redis_prefix_template):
    """
    Generic handler for stopping pipelines.
    """
    data = json.loads(request.body)
    pipeline_id = data.get("pipeline_id")
    
    kwargs = {}
        
    if pipeline_id:
        prefix = redis_prefix_template.format(**kwargs)
        redis_client.delete(f"{prefix}:{pipeline_id}")
        
    return JsonResponse({"status": "ok"})


@admin_required
@require_POST
def run_vanilla_llm_multi_turn_pipeline(request):
    return _run_pipeline_generic(
        request, 
        VanillaLLMMultiTurnPipeline, 
        "vanilla_llm_multi_turn_pipeline_active"
    )


@admin_required
@require_POST
def stop_vanilla_llm_multi_turn_pipeline(request):
    return _stop_pipeline_generic(request, "vanilla_llm_multi_turn_pipeline_active")


@admin_required
@require_POST
def run_vanilla_llm_adhoc_pipeline(request):
    return _run_pipeline_generic(
        request, 
        VanillaLLMAdhocPipeline, 
        "vanilla_llm_adhoc_pipeline_active"
    )


@admin_required
@require_POST
def stop_vanilla_llm_adhoc_pipeline(request):
    return _stop_pipeline_generic(request, "vanilla_llm_adhoc_pipeline_active")


@admin_required
@require_POST
def run_rag_adhoc_pipeline(request):
    return _run_pipeline_generic(
        request, 
        RagAdhocPipeline, 
        "rag_adhoc_pipeline_active"
    )


@admin_required
@require_POST
def stop_rag_adhoc_pipeline(request):
    return _stop_pipeline_generic(request, "rag_adhoc_pipeline_active")


@admin_required
@require_POST
def run_rag_multi_turn_pipeline(request):
    return _run_pipeline_generic(
        request, 
        RagMultiTurnPipeline, 
        "rag_multi_turn_pipeline_active",
    )


@admin_required
@require_POST
def stop_rag_multi_turn_pipeline(request):
    return _stop_pipeline_generic(
        request, 
        "rag_multi_turn_pipeline_active"
    )


@admin_required
@require_POST
def run_vanilla_agent_pipeline(request):
    return _run_pipeline_generic(
        request, 
        VanillaAgentPipeline, 
        "vanilla_agent_pipeline_active"
    )


@admin_required
@require_POST
def stop_vanilla_agent_pipeline(request):
    return _stop_pipeline_generic(request, "vanilla_agent_pipeline_active")


@admin_required
@require_POST
def stop_browser_agent_pipeline(request):
    return _stop_pipeline_generic(request, "browser_agent_pipeline_active")


@admin_required
def export_session(request, session_id):
    try:
        session = MultiTurnSession.objects.select_related("run").get(
            pk=session_id
        )
    except MultiTurnSession.DoesNotExist:
        return HttpResponse("Session not found", status=404)
    
    if session.pipeline_type == 'vanilla':
        pipeline_type = "vanilla_llm_multi_turn"
    elif session.pipeline_type == 'vanilla_agent':
        pipeline_type = "vanilla_agent"
    elif session.pipeline_type == 'browser_agent':
        pipeline_type = "browser_agent"
    else:
        pipeline_type = "rag_multi_turn"

    snapshot = session.run.settings_snapshot if session.run else {}

    max_retries = 3
    if snapshot and "llm_settings" in snapshot:
        max_retries = snapshot["llm_settings"].get("max_retries", 3)

    if session.pipeline_type == 'rag':
        trials = list(
            session.trials.values(
                "trial_number",
                "answer",
                "feedback",
                "is_correct",
                "created_at",
                "search_query",
                "search_results",
            )
        )
    elif session.pipeline_type == 'vanilla_agent' or session.pipeline_type == 'browser_agent':
         trials = list(
            session.trials.values(
                "trial_number", "answer", "feedback", "is_correct", "created_at", "full_response"
            )
        )
    else:
        trials = list(
            session.trials.values(
                "trial_number", "answer", "feedback", "is_correct", "created_at"
            )
        )

    # Fix datetime serialization
    for trial in trials:
        if trial.get("created_at"):
            trial["created_at"] = trial["created_at"].isoformat()

    export_format = request.GET.get("format", "json")

    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="benchmark_session_{session_id}.csv"'
        )

        writer = csv.writer(response)
        # Define headers
        headers = [
            "Session ID",
            "Question",
            "Ground Truths",
            "Pipeline Type",
            "Session Created At",
            "Trial Number",
            "Answer",
            "Feedback",
            "Is Correct",
            "Trial Created At",
        ]
        if session.pipeline_type == 'rag':
            headers.extend(["Search Query", "Search Results"])

        writer.writerow(headers)

        for trial in trials:
            row = [
                session.id,
                session.question,
                session.ground_truths,
                pipeline_type,
                session.created_at.isoformat(),
                trial.get("trial_number"),
                trial.get("answer"),
                trial.get("feedback"),
                trial.get("is_correct"),
                trial.get("created_at"),  # Already converted to string
            ]
            if session.pipeline_type == 'rag':
                row.extend([trial.get("search_query"), trial.get("search_results")])

            writer.writerow(row)

        return response

    else:
        export_data = {
            "session_id": session.id,
            "question": session.question,
            "ground_truths": session.ground_truths,
            "is_completed": session.is_completed,
            "pipeline_type": pipeline_type,
            "created_at": session.created_at.isoformat(),
            "max_retries": max_retries,
            "settings": snapshot,
            "trials": trials,
        }
        response = HttpResponse(
            json.dumps(export_data, indent=2), content_type="application/json"
        )

        response["Content-Disposition"] = (
            f'attachment; filename="benchmark_session_{session_id}.json"'
        )

        return response





from difflib import SequenceMatcher

@admin_required
def load_vanilla_llm_multi_turn_run(request, group_id):
    group = get_object_or_404(MultiTurnRun, pk=group_id)
    # Filter sessions by type
    sessions = group.sessions.filter(pipeline_type='vanilla').prefetch_related("trials")
    results = []
    snapshot = group.settings_snapshot
    max_retries = 3
    if snapshot and "llm_settings" in snapshot:
        max_retries = snapshot["llm_settings"].get("max_retries", 3)

    for session in sessions:
        trials = session.trials.all().order_by('trial_number')
        last_trial = trials.last()
        first_trial = trials.first()
        
        if last_trial:
            results.append({
                "question": session.question,
                "correct": last_trial.is_correct,
                "trials": session.trials.count(),
                "session_id": session.id,
                "final_answer": last_trial.answer,
                "ground_truths": session.ground_truths,
                "max_retries": max_retries,
                "initial_correct": first_trial.is_correct if first_trial else None
            })

    return JsonResponse(
        {"results": results, "group_name": group.name, "settings": snapshot}
    )

@admin_required
def load_rag_multi_turn_run(request, group_id):
    group = get_object_or_404(MultiTurnRun, pk=group_id)
    # Filter sessions by type
    sessions = group.sessions.filter(pipeline_type='rag').prefetch_related("trials")
    results = []
    snapshot = group.settings_snapshot
    max_retries = 3
    if snapshot and "llm_settings" in snapshot:
        max_retries = snapshot["llm_settings"].get("max_retries", 3)
        
    for session in sessions:
        trials = session.trials.all().order_by('trial_number')
        last_trial = trials.last()
        first_trial = trials.first()
        
        # Calculate Query Shift
        query_shift = 0.0
        if trials.count() > 1:
            total_shift = 0.0
            count = 0
            trial_list = list(trials)
            for i in range(len(trial_list) - 1):
                q1 = trial_list[i].search_query or ""
                q2 = trial_list[i+1].search_query or ""
                similarity = SequenceMatcher(None, q1, q2).ratio()
                total_shift += (1.0 - similarity)
                count += 1
            if count > 0:
                query_shift = total_shift / count

        if last_trial:
            results.append(
                {
                    "question": session.question,
                    "correct": last_trial.is_correct,
                    "trials": session.trials.count(),
                    "session_id": session.id,
                    "final_answer": last_trial.answer,
                    "ground_truths": session.ground_truths,
                    "max_retries": max_retries,
                    "initial_correct": first_trial.is_correct if first_trial else None,
                    "query_shift": query_shift
                }
            )
    return JsonResponse(
        {"results": results, "group_name": group.name, "settings": snapshot}
    )


@admin_required
def load_agent_multi_turn_run(request, group_id):
    group = get_object_or_404(MultiTurnRun, pk=group_id)
    # Filter sessions by type 'vanilla_agent' or 'browser_agent'
    sessions = group.sessions.filter(pipeline_type__in=['vanilla_agent', 'browser_agent']).prefetch_related("trials")
    results = []
    snapshot = group.settings_snapshot
    max_retries = 3 # Default or from settings

    for session in sessions:
        trials = session.trials.all().order_by('trial_number')
        last_trial = trials.last()
        first_trial = trials.first()
        
        if last_trial:
            results.append({
                "question": session.question,
                "correct": last_trial.is_correct,
                "trials": session.trials.count(),
                "session_id": session.id,
                "final_answer": last_trial.answer,
                "ground_truths": session.ground_truths,
                "max_retries": max_retries,
                "initial_correct": first_trial.is_correct if first_trial else None,
                "pipeline_type": session.pipeline_type # Add pipeline_type to results
            })

    return JsonResponse(
        {"results": results, "group_name": group.name, "settings": snapshot}
    )


@admin_required
def list_vanilla_llm_adhoc_runs(request):
    try:
        runs = AdhocRun.objects.filter(run_type='vanilla').values(
            "id", "name", "created_at", "accuracy"
        ).order_by("-created_at")
        return JsonResponse({"runs": list(runs)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
def get_vanilla_llm_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id, run_type='vanilla')
        results = list(run.results.values("question", "answer", "full_response", "ground_truths", "is_correct_rule", "is_correct_llm"))
        
        settings_data = {}
        if run.settings_snapshot:
            settings_data = run.settings_snapshot
            
        run_data = {
            "id": run.id,
            "name": run.name,
            "created_at": run.created_at,
            "accuracy": run.accuracy,
            "total_questions": run.total_questions,
            "correct_answers": run.correct_answers,
            "settings": settings_data,
            "results": results,
        }

        return JsonResponse(run_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
def browser_agent(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        with open(file_path, "r") as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        pass

    # Load sessions and group them
    groups = (
        MultiTurnRun.objects.filter(sessions__pipeline_type='browser_agent')
        .exclude(name__startswith="Ad-hoc Session")
        .prefetch_related(
            models.Prefetch(
                "sessions",
                queryset=MultiTurnSession.objects.filter(pipeline_type='browser_agent').order_by("-created_at"),
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    individual_sessions = MultiTurnSession.objects.filter(
        models.Q(run__name__startswith="Ad-hoc Session") | models.Q(run__isnull=True),
        pipeline_type='browser_agent'
    ).order_by("-created_at")

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "questions": questions,
        "groups": groups,
        "individual_sessions": individual_sessions,
        "llm_settings": LLMSettings.get_effective_settings(),
        "agent_settings": AgentSettings.get_effective_settings(),
        "agent_memory_choices": AgentSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": SearchSettings.PROVIDER_CHOICES,
        "datasets": datasets,
    }
    return render(request, "agent_browser.html", context)


@handle_async_api_error
async def _run_pipeline_generic_async(request, pipeline_class, redis_prefix_template, **kwargs):
    """
    Generic handler for running asynchronous pipelines (like Browser Agent).
    """
    # Async-safe settings retrieval
    db_settings = await sync_to_async(LLMSettings.get_effective_settings)()
    
    base_url = request.POST.get("llm_base_url") or db_settings.llm_base_url
    api_key = request.POST.get("llm_api_key") or db_settings.llm_api_key
    model = request.POST.get("llm_model") or db_settings.llm_model or "gpt-3.5-turbo"
    max_retries = int(request.POST.get("max_retries", 3))

    pipeline_id = request.POST.get("pipeline_id")
    dataset_id = request.POST.get("dataset_id")
    
    if not api_key:
            return JsonResponse(
            {"error": "An API Key is required to run the benchmark."}, status=400
        )

    if pipeline_id:
            redis_key = f"{redis_prefix_template}:{pipeline_id}"
            await sync_to_async(redis_client.set)(redis_key, "1", ex=3600)

    # Factory creation is async for BrowserAgent
    pipeline = await pipeline_class.create(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_retries=max_retries,
        pipeline_id=pipeline_id,
        dataset_id=dataset_id,
        **kwargs
    )

    return StreamingHttpResponse(serialize_events_async(pipeline.run()), content_type="application/json")


@admin_required
@require_POST
@handle_async_api_error
async def run_browser_agent_pipeline(request):
    return await _run_pipeline_generic_async(
        request, 
        BrowserAgentPipeline, 
        "browser_agent_pipeline_active"
    )


@require_POST
def web_search(request):
    try:
        data = json.loads(request.body)
        query = data.get("query")
        if not query:
            return JsonResponse({"error": "Query is required."}, status=400)
        search_engine = get_search_engine()
        results = search_engine.search(query)
        return JsonResponse({"results": results})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@admin_required
@require_http_methods(["DELETE"])
def delete_vanilla_llm_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id, run_type='vanilla')
        run.delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


