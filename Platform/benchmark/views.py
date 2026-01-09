from django.db import models
from django.views.decorators.http import require_POST, require_http_methods
from asgiref.sync import sync_to_async
import csv
import asyncio
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
import openai
from decouple import config
import os
import json
import tempfile
from user_system.decorators import admin_required
from django.db import OperationalError
from core.utils import print_debug, redis_client

import httpx
from task_manager.utils import check_answer_rule, check_answer_llm
from .utils import (
    get_search_engine, count_questions_in_file,
    handle_api_error, handle_async_api_error,
    print_debug, RedisKeys, PipelinePrefix, clear_trial_cache,
    TraceFormatter, SimpleMsg,
    apply_trial_metadata, is_rag_pipeline,
)
from .models import (
    BenchmarkSettings,
    MultiTurnRun,
    MultiTurnSession,
    MultiTurnTrial,
    BenchmarkDataset,
)
from .forms import BenchmarkDatasetForm

from datetime import datetime
from difflib import SequenceMatcher
from django.core.files.base import ContentFile

# Import from the new pipelines module
from .pipelines.base import (
    BaseMultiTurnPipeline,
    serialize_events,
    serialize_events_async,
)
from .pipelines.vanilla import (
    VanillaLLMMultiTurnPipeline,
)
from .pipelines.rag import (
    RagMultiTurnPipeline,
)
from .pipelines.agent import (
    VanillaAgentPipeline,
    BrowserAgentPipeline,
)
from .utils.pipeline_manager import PipelineManager
from .services import TrialService
from benchmark.utils import PROMPTS

PIPELINE_CLASS_MAP = {
    'vanilla_llm': VanillaLLMMultiTurnPipeline,
    'rag': RagMultiTurnPipeline,
    'vanilla_agent': VanillaAgentPipeline,
    'browser_agent': BrowserAgentPipeline,
}

# ========================================== 
# Metrics & Analytics Helpers
# ========================================== 

def _calculate_stubbornness(trial_list):
    """
    Computes the stubbornness score based on answer similarity across incorrect trials.
    """
    total_stubbornness = 0.0
    incorrect_transitions = 0
    
    for i in range(len(trial_list) - 1):
        if trial_list[i].is_correct_llm is False:
            ans1 = trial_list[i].answer or ""
            ans2 = trial_list[i+1].answer or ""
            similarity_a = SequenceMatcher(None, ans1, ans2).ratio()
            total_stubbornness += similarity_a
            incorrect_transitions += 1

    if incorrect_transitions > 0:
        return total_stubbornness / incorrect_transitions
    return 0.0

def _calculate_query_metrics(trial_list, is_rag=False, is_agent=False, original_question=None):
    """
    Computes comprehensive query diversity metrics from session logs.

    Returns a dict with all query metrics:
    - query_shift: Average dissimilarity between consecutive queries
    - search_count: Total number of search queries
    - query_uniqueness: Ratio of unique queries (0-1)
    - query_repetition: Count of duplicate queries
    - avg_query_length: Mean word count per query
    - first_query_success: 1 if first trial was correct, 0 otherwise (or None)
    - query_drift: Average deviation from original question (0-1)
    - query_convergence: Diversity trend (negative = converging)
    """
    search_count = 0
    all_queries = []
    first_trial_correct = None

    for i, t in enumerate(trial_list):
        t_log = t.log or {}

        # Track first trial correctness for first_query_success
        if i == 0:
            first_trial_correct = t.is_correct_llm

        if is_agent:
            t_queries = t_log.get("search_queries", [])
            all_queries.extend(t_queries)
            search_count += t_log.get("query_count", len(t_queries))
        elif is_rag:
            q = t_log.get("search_query")
            if not q:
                # Try to extract from trace
                for msg in t_log.get("trace", []):
                     if msg.get("role") == "assistant" and "Search Query:" in msg.get("content", ""):
                        q = msg.get("content").replace("Search Query:", "").strip()
                        break
            if q:
                all_queries.append(q)
                search_count += 1

    # Initialize result dict with defaults
    result = {
        'query_shift': 0.0,
        'search_count': search_count,
        'query_uniqueness': None,
        'query_repetition': None,
        'avg_query_length': None,
        'first_query_success': None,
        'query_drift': None,
        'query_convergence': None,
    }

    # Return early if no queries
    if len(all_queries) == 0:
        return result

    # Basic metrics (valid for >= 1 query)
    unique_queries = set(all_queries)
    unique_count = len(unique_queries)
    result['query_uniqueness'] = unique_count / len(all_queries)
    result['query_repetition'] = len(all_queries) - unique_count
    result['avg_query_length'] = sum(len(q.split()) for q in all_queries) / len(all_queries)

    # First query success (valid for >= 1 query with first trial result)
    if first_trial_correct is not None:
        result['first_query_success'] = 1 if first_trial_correct else 0

    # Query drift from original question (valid for >= 1 query with original_question)
    if original_question and len(all_queries) >= 1:
        total_drift = 0.0
        for q in all_queries:
            similarity = SequenceMatcher(None, original_question.lower(), q.lower()).ratio()
            total_drift += (1.0 - similarity)
        result['query_drift'] = total_drift / len(all_queries)

    # Query shift (consecutive diversity, valid for >= 2 queries)
    if len(all_queries) > 1:
        shift_count = 0
        total_query_shift = 0.0
        for i in range(len(all_queries) - 1):
            q1, q2 = all_queries[i], all_queries[i+1]
            if q1 and q2:
                similarity = SequenceMatcher(None, q1, q2).ratio()
                total_query_shift += (1.0 - similarity)
                shift_count += 1
        if shift_count > 0:
            result['query_shift'] = total_query_shift / shift_count

    # Query convergence (diversity trend, valid for >= 3 queries)
    if len(all_queries) >= 3:
        mid = len(all_queries) // 2
        first_half_shifts = []
        second_half_shifts = []
        for i in range(len(all_queries) - 1):
            q1, q2 = all_queries[i], all_queries[i+1]
            if q1 and q2:
                sim = SequenceMatcher(None, q1, q2).ratio()
                shift = 1.0 - sim
                if i < mid:
                    first_half_shifts.append(shift)
                else:
                    second_half_shifts.append(shift)
        if first_half_shifts and second_half_shifts:
            first_avg = sum(first_half_shifts) / len(first_half_shifts)
            second_avg = sum(second_half_shifts) / len(second_half_shifts)
            result['query_convergence'] = second_avg - first_avg  # Negative = converging

    return result


def _calculate_session_metrics(trial_list, is_rag=False, is_agent=False, original_question=None):
    """
    Computes stubbornness and comprehensive query metrics for a session trajectory.

    Returns: (stubborn_score, query_metrics_dict)
    """
    if not isinstance(trial_list, list):
        trial_list = list(trial_list)

    if len(trial_list) == 0:
        return 0.0, {
            'query_shift': None,
            'search_count': 0,
            'query_uniqueness': None,
            'query_repetition': None,
            'avg_query_length': None,
            'first_query_success': None,
            'query_drift': None,
            'query_convergence': None,
        }

    stubborn_score = _calculate_stubbornness(trial_list)
    query_metrics = _calculate_query_metrics(trial_list, is_rag, is_agent, original_question)

    # Set query_shift to None for non-RAG/Agent pipelines
    if not (is_rag or is_agent):
        query_metrics['query_shift'] = None

    return stubborn_score, query_metrics


def _calculate_dynamics_metrics(trial_list, ground_truths=None, is_rag=False, is_agent=False):
    """
    Computes multi-turn dynamics metrics for a session trajectory.

    Returns dict with:
    - oscillation_count, oscillation_opportunities: For A→B→A pattern detection
    - near_miss_count, incorrect_count: For near-miss rate calculation
    - recovery_stuck, recovery_wasted, recovery_random, recovery_effective, recovery_total: Recovery strategy breakdown
    """
    if not isinstance(trial_list, list):
        trial_list = list(trial_list)

    result = {
        'oscillation_count': 0,
        'oscillation_opportunities': 0,
        'near_miss_count': 0,
        'incorrect_count': 0,
        'recovery_stuck': 0,
        'recovery_wasted': 0,
        'recovery_random': 0,
        'recovery_effective': 0,
        'recovery_total': 0,
    }

    if len(trial_list) == 0:
        return result

    answers = [t.answer for t in trial_list if t.answer]

    # 1. Answer Oscillation Detection (A→B→A patterns)
    if len(answers) >= 3:
        for i in range(2, len(answers)):
            result['oscillation_opportunities'] += 1
            sim_to_prev = SequenceMatcher(None, answers[i], answers[i-1]).ratio()
            sim_to_two_back = SequenceMatcher(None, answers[i], answers[i-2]).ratio()
            # Oscillation: similar to 2 steps back (>0.6), different from 1 step back (<0.4)
            if sim_to_two_back > 0.6 and sim_to_prev < 0.4:
                result['oscillation_count'] += 1

    # 2. Near-Miss Detection (incorrect answers >50% similar to ground truth)
    if ground_truths:
        for t in trial_list:
            if t.is_correct_llm is False and t.answer:
                result['incorrect_count'] += 1
                answer_lower = t.answer.lower().strip()
                max_sim = 0.0
                for gt in ground_truths:
                    sim = SequenceMatcher(None, answer_lower, gt.lower()).ratio()
                    max_sim = max(max_sim, sim)
                if max_sim > 0.5:
                    result['near_miss_count'] += 1

    # 3. Recovery Strategy Analysis (only for RAG/Agent with queries)
    if (is_rag or is_agent) and len(trial_list) >= 2:
        for i in range(len(trial_list) - 1):
            t1, t2 = trial_list[i], trial_list[i+1]
            # Only analyze recovery attempts (after incorrect trial)
            if t1.is_correct_llm is False:
                a1 = t1.answer or ""
                a2 = t2.answer or ""
                log1 = t1.log or {}
                log2 = t2.log or {}

                # Get queries
                if is_agent:
                    q1 = " ".join(log1.get("search_queries", []))
                    q2 = " ".join(log2.get("search_queries", []))
                else:  # RAG
                    q1 = log1.get("search_query", "")
                    q2 = log2.get("search_query", "")

                if a1 and a2 and q1 and q2:
                    result['recovery_total'] += 1
                    query_change = 1 - SequenceMatcher(None, q1, q2).ratio()
                    answer_change = 1 - SequenceMatcher(None, a1, a2).ratio()

                    # Categorize recovery strategy (threshold: 0.3)
                    if query_change < 0.3 and answer_change < 0.3:
                        result['recovery_stuck'] += 1
                    elif query_change >= 0.3 and answer_change < 0.3:
                        result['recovery_wasted'] += 1
                    elif query_change < 0.3 and answer_change >= 0.3:
                        result['recovery_random'] += 1
                    else:
                        result['recovery_effective'] += 1

    return result


# ==========================================
# Aggregate Metrics API
# ==========================================

from .utils.metrics import (
    calculate_aggregate_metrics,
    get_all_metric_colors,
    get_metric_groups,
    get_metric_definitions,
    get_metrics_by_group,
)

@admin_required
@require_POST
def calculate_metrics(request):
    """
    Calculate aggregate metrics from session results.

    Accepts POST with JSON body containing:
    - results: List of result dicts (from _get_run_results or frontend)
    - pipeline_type: Pipeline type to filter applicable metrics (vanilla_llm, rag, etc.)

    Returns:
    - metrics: Dict of all calculated metrics with values and colors
    - groups: Applicable metric groups for the pipeline
    - total: Total number of sessions
    - summary: Quick summary stats
    """
    try:
        data = json.loads(request.body)
        results = data.get("results", [])
        pipeline_type = data.get("pipeline_type")

        if not results:
            return JsonResponse({
                "status": "error",
                "message": "No results provided"
            }, status=400)

        metrics_data = calculate_aggregate_metrics(results, pipeline_type)
        return JsonResponse({
            "status": "ok",
            **metrics_data
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@admin_required
def get_metric_colors(request):
    """
    Get the color mapping for all metrics.

    Useful for frontend to preload consistent colors.
    """
    try:
        colors = get_all_metric_colors()
        return JsonResponse({
            "status": "ok",
            "colors": colors
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@admin_required
def get_metric_schema(request):
    """
    Get the full metric schema including groups, definitions, and colors.

    This provides the frontend with all information needed to render metrics
    without hardcoding any group or metric information.

    Returns:
    - groups: List of metric groups sorted by priority
    - definitions: Dict of all metric definitions
    - metrics_by_group: Metrics organized by group, sorted by priority within each group
    - colors: Color mapping for all metrics
    """
    try:
        return JsonResponse({
            "status": "ok",
            "groups": get_metric_groups(),
            "definitions": get_metric_definitions(),
            "metrics_by_group": get_metrics_by_group(),
            "colors": get_all_metric_colors(),
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


# ==========================================
# Core UI Views
# ========================================== 

@admin_required
def home(request):
    settings = BenchmarkSettings.get_effective_settings()
    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    context = {
        "llm_settings": settings,
        "search_settings": settings,
        "agent_settings": settings,
        "agent_memory_choices": BenchmarkSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": BenchmarkSettings.PROVIDER_CHOICES,
        "datasets": datasets,
        "settings": settings,
    }
    return render(request, "home.html", context)

def _render_benchmark_view(request, pipeline_type, template_name):
    """
    Generic helper to render benchmark views (Vanilla, RAG, Agent, etc.)
    Reduces duplication of context loading logic.
    """
    # Load questions from the default file (hard_questions_refined.jsonl)
    questions = []
    try:
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "hard_questions_refined.jsonl"
        )
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                for line in f:
                    if line.strip():
                        questions.append(json.loads(line))
    except Exception:
        pass

    # Load sessions and group them
    groups = (
        MultiTurnRun.objects.filter(sessions__pipeline_type=pipeline_type, is_ad_hoc=False)
        .prefetch_related(
            models.Prefetch(
                "sessions",
                queryset=MultiTurnSession.objects.filter(pipeline_type=pipeline_type).order_by("-created_at"),
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    individual_sessions = MultiTurnSession.objects.filter(
        models.Q(run__is_ad_hoc=True) | models.Q(run__isnull=True),
        pipeline_type=pipeline_type
    ).order_by("-created_at")

    datasets = BenchmarkDataset.objects.all().order_by("-created_at")

    settings = BenchmarkSettings.get_effective_settings()

    context = {
        "questions": questions,
        "groups": groups,
        "individual_sessions": individual_sessions,
        "llm_settings": settings,
        "search_settings": settings,
        "agent_settings": settings,
        "agent_memory_choices": BenchmarkSettings.MEMORY_TYPE_CHOICES,
        "search_provider_choices": BenchmarkSettings.PROVIDER_CHOICES,
        "datasets": datasets,
        "settings": settings,
    }
    return render(request, template_name, context)

@admin_required
def vanilla_llm(request):
    return _render_benchmark_view(request, 'vanilla_llm', "vanilla_llm.html")

@admin_required
def rag(request):
    return _render_benchmark_view(request, 'rag', "rag.html")

@admin_required
def vanilla_agent(request):
    return _render_benchmark_view(request, 'vanilla_agent', "vanilla_agent.html")

@admin_required
def browser_agent(request):
    return _render_benchmark_view(request, 'browser_agent', "browser_agent.html")

# ========================================== 
# Settings & Configuration
# ========================================== 

@admin_required
def get_default_settings(request):
    try:
        settings = BenchmarkSettings.get_effective_settings()

        config_data = {
            # LLM
            "llm_base_url": config("LLM_BASE_URL", default=settings.llm_base_url),
            "llm_api_key": config("LLM_API_KEY", default=settings.llm_api_key),
            "llm_model": config("LLM_MODEL", default=settings.llm_model),
            "llm_judge_model": config("LLM_JUDGE_MODEL", default=settings.llm_judge_model),
            "embedding_model": config("EMBEDDING_MODEL", default=settings.embedding_model),
            "max_retries": settings.max_retries,
            "allow_reasoning": settings.allow_reasoning,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,

            # Search
            "search_provider": settings.search_provider,
            "serper_api_key": config("SERPER_API_KEY", default=settings.serper_api_key),
            "search_limit": settings.search_limit,
            "serper_fetch_full_content": settings.fetch_full_content,

            # Agent
            "agent_memory_type": settings.memory_type,
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

@admin_required
@require_POST
def save_settings(request):
    try:
        data = json.loads(request.body)
        settings = BenchmarkSettings.load()
        
        # LLM Settings
        if "llm_base_url" in data: settings.llm_base_url = data.get("llm_base_url", "")
        if "llm_model" in data: settings.llm_model = data.get("llm_model", "")
        if "llm_api_key" in data: settings.llm_api_key = data.get("llm_api_key", "")
        if "llm_judge_model" in data: settings.llm_judge_model = data.get("llm_judge_model", "")
        if "embedding_model" in data: settings.embedding_model = data.get("embedding_model", "")
        if "max_retries" in data: settings.max_retries = int(data.get("max_retries", 3))
        if "allow_reasoning" in data: settings.allow_reasoning = data.get("allow_reasoning", True)
        if "temperature" in data: settings.temperature = float(data.get("temperature", 0.0))
        if "top_p" in data: settings.top_p = float(data.get("top_p", 1.0))
        
        max_tokens_val = data.get("max_tokens")
        if max_tokens_val is not None and max_tokens_val != "":
            settings.max_tokens = int(max_tokens_val)
        elif "max_tokens" in data:
            settings.max_tokens = None
            
        # Search Settings
        if "search_provider" in data: settings.search_provider = data.get("search_provider", settings.search_provider)
        if "serper_api_key" in data: settings.serper_api_key = data.get("serper_api_key", settings.serper_api_key)
        if "search_limit" in data: settings.search_limit = int(data.get("search_limit", settings.search_limit))
        if "serper_fetch_full_content" in data: settings.fetch_full_content = data.get("serper_fetch_full_content", settings.fetch_full_content)
        
        # Agent Settings
        if "memory_type" in data: settings.memory_type = data.get("memory_type", settings.memory_type)
        if "agent_memory_type" in data: settings.memory_type = data.get("agent_memory_type", settings.memory_type)

        settings.save()
        return JsonResponse({"status": "ok"})
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

# ========================================== 
# Dataset Management
# ========================================== 

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
            # Count questions from the uploaded file using secure temp file
            file = request.FILES['file']
            # Use NamedTemporaryFile for secure handling (avoids path traversal)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl') as temp_file:
                for chunk in file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            try:
                dataset.question_count = count_questions_in_file(temp_path)
            finally:
                os.unlink(temp_path)  # Always clean up temp file

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
                if not BenchmarkDataset.objects.filter(name=filename).exists():
                    file_path = os.path.join(data_dir, filename)
                    with open(file_path, "r") as f:
                        content = f.read()

                    is_active = filename == "hard_questions_refined.jsonl"
                    dataset = BenchmarkDataset(
                        name=filename,
                        description=f"Auto-detected from {filename}",
                        is_active=is_active,
                    )
                    dataset.question_count = count_questions_in_file(file_path)
                    dataset.file.save(filename, ContentFile(content))
                    dataset.save()
                    added_count += 1

        if not BenchmarkDataset.objects.filter(is_active=True).exists():
            try:
                default_ds = BenchmarkDataset.objects.get(name="hard_questions_refined.jsonl")
                default_ds.is_active = True
                default_ds.save()
            except BenchmarkDataset.DoesNotExist:
                pass

        return JsonResponse({"status": "ok", "added": added_count})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ========================================== 
# Session & Trial Lifecycle
# ========================================== 

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
    pipeline_type = data.get("pipeline_type", "vanilla_llm")

    if not question_text or not ground_truths:
        return JsonResponse(
            {"error": "Question and ground truths are required."}, status=400
        )
    
    settings = BenchmarkSettings.get_effective_settings()
    
    if group_id:
        group = get_object_or_404(MultiTurnRun, pk=group_id)
    else:
        group_name = f"Ad-hoc Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        new_settings = settings.clone()
        new_settings.save()
        group = MultiTurnRun.objects.create(name=group_name, settings=new_settings, is_ad_hoc=True)

    session = MultiTurnSession.objects.create(
        question=question_text,
        ground_truths=ground_truths,
        run=group,
        pipeline_type=pipeline_type
    )

    trial = MultiTurnTrial.objects.create(session=session, trial_number=1, status="processing")
    # Clear any stale Redis cache for this trial ID (prevents data leakage from reused IDs)
    clear_trial_cache(trial.id)

    return JsonResponse({"session_id": session.id, "trial_id": trial.id})

@admin_required
@handle_api_error
def run_trial(request, trial_id):
    trial = get_object_or_404(MultiTurnTrial.objects.select_related("session", "session__run"), pk=trial_id)
    session = trial.session
    
    settings = session.run.settings if session.run and session.run.settings else BenchmarkSettings.get_effective_settings()
    base_url = settings.llm_base_url
    model = settings.llm_model
    api_key = config("LLM_API_KEY", default=None)

    if not api_key or not model:
        db_settings = BenchmarkSettings.get_effective_settings()
        if not api_key:
            api_key = config("LLM_API_KEY", default=db_settings.llm_api_key)
        if not base_url:
            base_url = config("LLM_BASE_URL", default=db_settings.llm_base_url)
        if not model:
            model = db_settings.llm_model or config("LLM_MODEL", default="gpt-4o")

    common_kwargs = {"base_url": base_url, "api_key": api_key, "model": model, "max_retries": 1}
    pipeline_type = session.pipeline_type

    if pipeline_type in ['browser_agent', 'vanilla_agent']:
        factory_kwargs = {**common_kwargs, "pipeline_id": session.run_tag}
        PipelineClass = PIPELINE_CLASS_MAP.get(pipeline_type)
        if not PipelineClass:
            raise Exception(f"Unknown pipeline type: {pipeline_type}")

        answer, is_correct_llm, search_results, error_msg = PipelineManager.get_instance().run_trial(
            session.id, trial.id, factory_kwargs, PipelineClass
        )
        if error_msg:
            raise Exception(error_msg)
    else:
        PipelineClass = PIPELINE_CLASS_MAP.get(pipeline_type, VanillaLLMMultiTurnPipeline)
        pipeline = PipelineClass(**common_kwargs)
        answer, is_correct_llm, search_results = pipeline.run_single_turn(session, trial)

    if is_correct_llm:
        session.is_completed = True
        session.save()

    num_docs_used = len(search_results) if search_results else 0
    return JsonResponse({
        "answer": answer,
        "trial_id": trial.id,
        "is_correct": is_correct_llm,
        "is_correct_llm": is_correct_llm,
        "is_correct_rule": trial.is_correct_rule,
        "num_docs_used": num_docs_used,
    })

@admin_required
@require_POST
def retry_session(request, trial_id):
    try:
        data = json.loads(request.body)
        feedback = data.get("feedback")
        is_correct = data.get("is_correct")
        original_trial = get_object_or_404(MultiTurnTrial.objects.select_related("session", "session__run"), pk=trial_id)

        original_trial.feedback = feedback
        original_trial.is_correct_llm = is_correct
        original_trial.save()

        session = original_trial.session
        settings = session.run.settings if session.run and session.run.settings else BenchmarkSettings.get_effective_settings()
        max_retries = settings.max_retries

        if is_correct:
            session.is_completed = True
            session.save()
            return JsonResponse({"status": "completed", "session_id": session.id})

        if session.trials.count() >= max_retries:
            session.is_completed = True
            session.save()
            return JsonResponse({"status": "max_retries_reached", "session_id": session.id})

        new_trial = MultiTurnTrial.objects.create(
            session=session,
            trial_number=original_trial.trial_number + 1,
            status="processing",
        )
        # Clear any stale Redis cache for this trial ID (prevents data leakage from reused IDs)
        clear_trial_cache(new_trial.id)
        return JsonResponse({"status": "retrying", "new_trial_id": new_trial.id})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@admin_required
@require_POST
def stop_session(request):
    try:
        data = json.loads(request.body)
        session_id = data.get("session_id")
        if not session_id:
             return JsonResponse({"status": "error", "message": "Session ID required"}, status=400)
             
        session = get_object_or_404(MultiTurnSession, pk=session_id)
        processing_trials = session.trials.filter(status='processing')
        
        for trial in processing_trials:
            redis_client.delete(RedisKeys.trial_status(trial.id))
            redis_client.delete(RedisKeys.trial_trace(trial.id))
        
        processing_trials.update(status='error', feedback='Session stopped by user.')
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
             pass
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

@admin_required
@require_POST
def rename_session_group(request, group_id):
    try:
        data = json.loads(request.body)
        new_name = data.get("name", "").strip()

        if not new_name:
            return JsonResponse({"status": "error", "message": "Name cannot be empty."}, status=400)

        group = get_object_or_404(MultiTurnRun, pk=group_id)
        group.name = new_name
        group.save()
        return JsonResponse({"status": "ok", "name": group.name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@require_POST
def batch_delete_sessions(request):
    try:
        data = json.loads(request.body)
        session_ids = data.get("session_ids", [])
        if not session_ids:
            return JsonResponse({"status": "error", "message": "No session IDs provided."}, status=400)

        try:
            session_ids = [int(sid) for sid in session_ids]
        except (ValueError, TypeError):
            return JsonResponse({"status": "error", "message": "Invalid session ID format."}, status=400)

        sessions = MultiTurnSession.objects.filter(id__in=session_ids)
        deleted_ids = list(sessions.values_list("id", flat=True))
        deleted_count = sessions.count()
        sessions.delete()

        return JsonResponse({"status": "ok", "message": f"{deleted_count} sessions deleted.", "deleted_ids": deleted_ids})
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ========================================== 
# Batch Pipeline Execution (Generic)
# ========================================== 

def _get_llm_settings_from_request(request, data_source=None):
    """
    Helper to extract LLM settings from a data source (dict) or request.POST,
    falling back to database settings.
    """
    db_settings = BenchmarkSettings.get_effective_settings()
    data = data_source if data_source is not None else request.POST
    
    base_url = data.get("llm_base_url") or db_settings.llm_base_url
    api_key = data.get("llm_api_key") or db_settings.llm_api_key
    model = data.get("llm_model") or db_settings.llm_model 
    max_retries = int(data.get("max_retries", 3))
    
    return base_url, api_key, model, max_retries

@handle_api_error
def _run_pipeline_generic(request, pipeline_class, redis_prefix_template, **kwargs):
    base_url, api_key, model, max_retries = _get_llm_settings_from_request(request)
    pipeline_id = request.POST.get("pipeline_id")
    dataset_id = request.POST.get("dataset_id")
    group_id = request.POST.get("group_id")

    if not api_key:
        return JsonResponse({"error": "An API Key is required to run the benchmark."}, status=400)

    if pipeline_id:
        try:
            prefix = redis_prefix_template.format(**kwargs)
        except KeyError:
            prefix = redis_prefix_template
        redis_key = RedisKeys.pipeline_active(prefix, pipeline_id)
        redis_client.set(redis_key, "1", ex=RedisKeys.DEFAULT_TTL)

    constructor_args = {
        "base_url": base_url, "api_key": api_key, "model": model,
        "pipeline_id": pipeline_id, "dataset_id": dataset_id, "group_id": group_id,
    }
    if issubclass(pipeline_class, (BaseMultiTurnPipeline, VanillaAgentPipeline)):
            constructor_args["max_retries"] = max_retries
    constructor_args.update(kwargs)
    pipeline = pipeline_class(**constructor_args)
    return StreamingHttpResponse(serialize_events(pipeline.run()), content_type="application/json")

@handle_api_error
def _stop_pipeline_generic(request, redis_prefix_template):
    data = json.loads(request.body)
    pipeline_id = data.get("pipeline_id")
    if pipeline_id:
        redis_client.delete(RedisKeys.pipeline_active(redis_prefix_template, pipeline_id))
    return JsonResponse({"status": "ok"})

@admin_required
@require_POST
def pipeline_start(request, pipeline_type):
    if pipeline_type == 'vanilla_llm':
        return _run_pipeline_generic(request, VanillaLLMMultiTurnPipeline, "vanilla_llm_pipeline_active")
    elif pipeline_type == 'rag':
        return _run_pipeline_generic(request, RagMultiTurnPipeline, "rag_pipeline_active")
    elif pipeline_type == 'vanilla_agent':
        return _run_pipeline_generic_async_wrapper(request, VanillaAgentPipeline, "vanilla_agent_pipeline_active")
    elif pipeline_type == 'browser_agent':
        return _run_pipeline_generic_async_wrapper(request, BrowserAgentPipeline, "browser_agent_pipeline_active")
    else:
        return JsonResponse({"status": "error", "message": f"Unknown pipeline type: {pipeline_type}"}, status=400)

@admin_required
@require_POST
def pipeline_stop(request, pipeline_type):
    redis_prefix_map = {
        'vanilla_llm': "vanilla_llm_pipeline_active",
        'rag': "rag_pipeline_active",
        'vanilla_agent': "vanilla_agent_pipeline_active",
        'browser_agent': "browser_agent_pipeline_active",
    }
    prefix = redis_prefix_map.get(pipeline_type)
    if prefix:
        return _stop_pipeline_generic(request, prefix)
    return JsonResponse({"status": "error", "message": f"Unknown pipeline type: {pipeline_type}"}, status=400)

def sync_iterator_from_async(async_gen):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        iter_ = async_gen.__aiter__()
        while True:
            try:
                item = loop.run_until_complete(iter_.__anext__())
                yield item
            except StopAsyncIteration:
                break
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()

@handle_api_error
def _run_pipeline_generic_async_wrapper(request, pipeline_class, redis_prefix_template, **kwargs):
    base_url, api_key, model, max_retries = _get_llm_settings_from_request(request)
    pipeline_id = request.POST.get("pipeline_id")
    dataset_id = request.POST.get("dataset_id")
    group_id = request.POST.get("group_id")

    if not api_key:
        return JsonResponse({"error": "An API Key is required to run the benchmark."}, status=400)
    if pipeline_id:
        redis_client.set(RedisKeys.pipeline_active(redis_prefix_template, pipeline_id), "1", ex=RedisKeys.DEFAULT_TTL)

    async def pipeline_lifecycle_wrapper():
        try:
            pipeline = await pipeline_class.create(
                base_url=base_url, api_key=api_key, model=model, max_retries=max_retries,
                pipeline_id=pipeline_id, dataset_id=dataset_id, group_id=group_id, **kwargs
            )
            async for event in pipeline.run():
                yield event
        except Exception as e:
            yield {'error': str(e)}

    def serialize_events_sync_bridge():
        for event in sync_iterator_from_async(pipeline_lifecycle_wrapper()):
            yield json.dumps(event) + "\n"

    return StreamingHttpResponse(serialize_events_sync_bridge(), content_type="application/json")

# ========================================== 
# Result Retrieval & Data Export
# ========================================== 

@admin_required
def get_session(request, session_id):
    try:
        session = MultiTurnSession.objects.select_related("run").get(pk=session_id)
    except MultiTurnSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)
    
    pipeline_type = session.pipeline_type
    settings = session.run.settings if session.run and session.run.settings else BenchmarkSettings.get_effective_settings()
    snapshot = settings.to_snapshot_dict()
    max_retries = settings.max_retries

    trials_qs = session.trials.values(
        "id", "trial_number", "answer", "feedback", "is_correct_llm", "is_correct_rule",
        "created_at", "status", "log"
    )
    trials = list(trials_qs)

    for t in trials:
        log = t.pop("log", {}) or {}
        messages = log.get("messages", [])

        # Parse trace on-demand for UI rendering
        if messages:
            # Handle both simple dicts and complex agent Msg dicts
            trace_msgs = []
            for m in messages:
                role = m.get("role", "assistant")
                content = m.get("content", "")
                trace_msgs.append(SimpleMsg(role, content))
            t["trace"], _ = TraceFormatter.serialize(trace_msgs)
        else:
            t["trace"] = []

        # Apply pipeline-specific metadata (search data for RAG, memory data for agents)
        apply_trial_metadata(t, log, pipeline_type)

    return JsonResponse({
        "session": {
            "id": session.id, "question": session.question, "ground_truths": session.ground_truths,
            "is_completed": session.is_completed, "created_at": session.created_at,
            "max_retries": max_retries, "group_id": session.run_id,
            "pipeline_type": pipeline_type, "settings": snapshot,
        },
        "trials": trials,
    })

def _get_run_results(group_id, pipeline_types):
    group = get_object_or_404(MultiTurnRun, pk=group_id)
    if isinstance(pipeline_types, str):
        pipeline_types = [pipeline_types]
        
    sessions = group.sessions.filter(pipeline_type__in=pipeline_types).prefetch_related("trials")
    results = []
    settings = group.settings if group.settings else BenchmarkSettings.get_effective_settings()
    snapshot = settings.to_snapshot_dict()
    max_retries = settings.max_retries

    for session in sessions:
        trials = list(session.trials.all().order_by('trial_number'))
        if not trials: continue
            
        first_trial, last_trial = trials[0], trials[-1]
        session_coherence, matches, evaluated_trials = 0.0, 0, 0
        for t in trials:
            if t.is_correct_llm is not None and t.is_correct_rule is not None:
                evaluated_trials += 1
                if t.is_correct_llm == t.is_correct_rule: matches += 1
        if evaluated_trials > 0: session_coherence = matches / evaluated_trials

        ptype = session.pipeline_type
        is_agent, is_rag = ptype in ['vanilla_agent', 'browser_agent'], 'rag' in ptype
        stubborn_score, query_metrics = _calculate_session_metrics(
            trials, is_rag=is_rag, is_agent=is_agent, original_question=session.question
        )
        dynamics_metrics = _calculate_dynamics_metrics(
            trials, ground_truths=session.ground_truths, is_rag=is_rag, is_agent=is_agent
        )

        results.append({
            "question": session.question, "correct": last_trial.is_correct_llm,
            "is_correct_llm": last_trial.is_correct_llm, "is_correct_rule": last_trial.is_correct_rule,
            "coherence": session_coherence, "trials": len(trials), "session_id": session.id,
            "final_answer": last_trial.answer, "ground_truths": session.ground_truths, "max_retries": max_retries,
            "initial_correct": first_trial.is_correct_llm, "initial_correct_rule": first_trial.is_correct_rule,
            "pipeline_type": session.pipeline_type, "stubborn_score": stubborn_score,
            # Flatten query metrics into result
            "query_shift": query_metrics.get('query_shift'),
            "search_count": query_metrics.get('search_count'),
            "query_uniqueness": query_metrics.get('query_uniqueness'),
            "query_repetition": query_metrics.get('query_repetition'),
            "avg_query_length": query_metrics.get('avg_query_length'),
            "first_query_success": query_metrics.get('first_query_success'),
            "query_drift": query_metrics.get('query_drift'),
            "query_convergence": query_metrics.get('query_convergence'),
            # Flatten dynamics metrics into result
            "oscillation_count": dynamics_metrics.get('oscillation_count'),
            "oscillation_opportunities": dynamics_metrics.get('oscillation_opportunities'),
            "near_miss_count": dynamics_metrics.get('near_miss_count'),
            "incorrect_count": dynamics_metrics.get('incorrect_count'),
            "recovery_stuck": dynamics_metrics.get('recovery_stuck'),
            "recovery_wasted": dynamics_metrics.get('recovery_wasted'),
            "recovery_random": dynamics_metrics.get('recovery_random'),
            "recovery_effective": dynamics_metrics.get('recovery_effective'),
            "recovery_total": dynamics_metrics.get('recovery_total'),
        })
    return JsonResponse({"results": results, "group_name": group.name, "settings": snapshot})

@admin_required
def load_benchmark_run(request, group_id, pipeline_category):
    if pipeline_category == 'vanilla_llm':
        return _get_run_results(group_id, 'vanilla_llm')
    elif pipeline_category == 'rag':
        return _get_run_results(group_id, 'rag')
    elif pipeline_category == 'agent_multi_turn':
        return _get_run_results(group_id, ['vanilla_agent', 'browser_agent'])
    else:
        return JsonResponse({"error": f"Unknown pipeline category: {pipeline_category}"}, status=400)

@admin_required
def export_session(request, session_id):
    try:
        session = MultiTurnSession.objects.select_related("run").get(pk=session_id)
    except MultiTurnSession.DoesNotExist:
        return HttpResponse("Session not found", status=404)
    
    pipeline_type = session.pipeline_type
    settings = session.run.settings if session.run and session.run.settings else BenchmarkSettings.get_effective_settings()
    snapshot = settings.to_snapshot_dict()
    if snapshot and "llm" in snapshot:
        snapshot["llm"].pop("llm_api_key", None)
    max_retries = settings.max_retries

    trials = list(session.trials.values(
        "trial_number", "answer", "feedback", "is_correct_llm", "is_correct_rule",
        "created_at", "log"
    ))

    for trial in trials:
        if trial.get("created_at"): trial["created_at"] = trial["created_at"].isoformat()
        log = trial.pop("log", {}) or {}

        # Export raw messages (authentic LLM/agent context)
        messages = log.get("messages", [])

        # Ensure system prompt is included (stored separately for agent pipelines)
        system_prompt = log.get("system_prompt")
        if system_prompt:
            # Check if first message is already a system message
            has_system_msg = messages and isinstance(messages[0], dict) and messages[0].get("role") == "system"
            if not has_system_msg:
                messages = [{"role": "system", "content": system_prompt}] + messages

        trial["messages"] = messages

        # Apply pipeline-specific metadata (search data for RAG, memory data for agents)
        apply_trial_metadata(trial, log, pipeline_type)

    export_format = request.GET.get("format", "json")
    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="benchmark_session_{session_id}.csv"'
        writer = csv.writer(response)
        headers = ["Session ID", "Question", "Ground Truths", "Pipeline Type", "Session Created At", "Trial Number", "Answer", "Feedback", "Is Correct (LLM)", "Is Correct (Rule)", "Trial Created At"]
        if is_rag_pipeline(pipeline_type): headers.extend(["Search Query", "Search Results"])
        writer.writerow(headers)
        for trial in trials:
            row = [session.id, session.question, session.ground_truths, pipeline_type, session.created_at.isoformat(), trial.get("trial_number"), trial.get("answer"), trial.get("feedback"), trial.get("is_correct_llm"), trial.get("is_correct_rule"), trial.get("created_at")]
            if is_rag_pipeline(pipeline_type): row.extend([trial.get("search_query"), trial.get("search_results")])
            writer.writerow(row)
        return response
    else:
        export_data = {"session_id": session.id, "question": session.question, "ground_truths": session.ground_truths, "is_completed": session.is_completed, "pipeline_type": pipeline_type, "created_at": session.created_at.isoformat(), "max_retries": max_retries, "settings": snapshot, "trials": trials}
        response = HttpResponse(json.dumps(export_data, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="benchmark_session_{session_id}.json"'
        return response

@admin_required
def export_run(request, group_id):
    try:
        group = get_object_or_404(MultiTurnRun, pk=group_id)
        sessions = group.sessions.all().order_by('id')
        
        export_data = {
            "group_id": group.id,
            "group_name": group.name,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "settings": None,
            "sessions": []
        }
        
        # Get settings from the run
        settings = group.settings
        if settings:
             snapshot = settings.to_snapshot_dict()
             if snapshot and "llm" in snapshot:
                snapshot["llm"].pop("llm_api_key", None)
             export_data["settings"] = snapshot

        sessions_data = []
        for session in sessions:
            trials = list(session.trials.values(
                "trial_number", "answer", "feedback", "is_correct_llm", "is_correct_rule",
                "created_at", "log"
            ))

            session_pipeline_type = session.pipeline_type or ''

            for trial in trials:
                if trial.get("created_at"): trial["created_at"] = trial.get("created_at").isoformat()
                log = trial.pop("log", {}) or {}

                # Export raw messages (authentic LLM/agent context)
                messages = log.get("messages", [])

                # Ensure system prompt is included (stored separately for agent pipelines)
                system_prompt = log.get("system_prompt")
                if system_prompt:
                    # Check if first message is already a system message
                    has_system_msg = messages and isinstance(messages[0], dict) and messages[0].get("role") == "system"
                    if not has_system_msg:
                        messages = [{"role": "system", "content": system_prompt}] + messages

                trial["messages"] = messages

                # Apply pipeline-specific metadata (search data for RAG, memory data for agents)
                apply_trial_metadata(trial, log, session_pipeline_type)

            sessions_data.append({
                "session_id": session.id,
                "question": session.question,
                "ground_truths": session.ground_truths,
                "is_completed": session.is_completed,
                "pipeline_type": session.pipeline_type,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "trials": trials
            })
        
        export_data["sessions"] = sessions_data

        response = HttpResponse(json.dumps(export_data, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="benchmark_run_{group_id}.json"'
        return response
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ========================================== 
# Debug & Interaction Utilities
# ========================================== 

def get_trial_trace(request, trial_id):
    try:
        cursor = int(request.GET.get('cursor', 0))
        response_data = TrialService.get_trace_data(trial_id, cursor)
        return JsonResponse(response_data)
    except Exception as e:
        print_debug(f"View Error in get_trial_trace: {e}")
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

@admin_required
def get_trial_prompt(request, trial_id):
    trial = get_object_or_404(MultiTurnTrial.objects.select_related("session", "session__run"), pk=trial_id)
    session = trial.session
    pipeline_type = session.pipeline_type
    if pipeline_type not in ['vanilla_llm', 'rag']:
        return JsonResponse({"error": "Prompt reconstruction only supported for Vanilla and RAG baselines."}, status=400)
    try:
        PipelineClass = PIPELINE_CLASS_MAP.get(pipeline_type)
        pipeline = PipelineClass(base_url="", api_key="", model="", max_retries=1)
        completed_trials = list(session.trials.filter(trial_number__lt=trial.trial_number, status='completed').order_by('trial_number'))
        messages = pipeline._construct_messages(session, trial, completed_trials)
        return JsonResponse({"status": "ok", "messages": messages})
    except Exception as e:
        print_debug(f"Error in get_trial_prompt: {e}")
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

@require_POST
def web_search(request):
    try:
        data = json.loads(request.body)
        query = data.get("query")
        if not query: return JsonResponse({"error": "Query is required."}, status=400)
        search_engine = get_search_engine()
        results = search_engine.search(query)
        return JsonResponse({"results": results})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
