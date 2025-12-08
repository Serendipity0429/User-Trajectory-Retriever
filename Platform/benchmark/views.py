from django.db import models
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
import re
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
import openai
from decouple import config
import os
import json
from user_system.decorators import admin_required
from django.db import OperationalError
import traceback
from user_system.utils import print_debug

import httpx
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from .search_utils import get_search_engine
from .models import (
    LLMSettings, 
    RagSettings, 
    SearchSettings,
    VanillaLLMMultiTurnSession,
    VanillaLLMMultiTurnTrial,
    RAGMultiTurnSession,
    RAGMultiTurnTrial,
    MultiTurnSessionGroup, 
    VanillaLLMAdhocRun, 
    VanillaLLMAdhocResult,
    RagAdhocRun, 
    RagAdhocResult,
    BenchmarkDataset
)
from .forms import BenchmarkDatasetForm

from datetime import datetime

# Import from the new utils module
from .pipeline_utils import (
    VanillaLLMAdhocPipeline,
    RagAdhocPipeline,
    BaseMultiTurnPipeline,
    VanillaLLMMultiTurnPipeline,
    RagMultiTurnPipeline
)

@admin_required
def home(request):
    settings = LLMSettings.load()

    # If the settings are empty, try to populate from .env file
    if not settings.llm_api_key and not settings.llm_model:
        try:
            llm_api_key_env = config('LLM_API_KEY', default=None)
            llm_model_env = config('LLM_MODEL', default=None)
            if llm_api_key_env or llm_model_env:
                settings.llm_base_url = config('LLM_BASE_URL', default='')
                settings.llm_api_key = llm_api_key_env or ''
                settings.llm_model = llm_model_env or ''
                settings.save()
        except OperationalError:
            pass

    rag_settings = RagSettings.load()
    search_settings = SearchSettings.load()
    datasets = BenchmarkDataset.objects.all().order_by('-created_at')
    
    context = {
        'llm_settings': settings,
        'rag_settings': rag_settings,
        'search_settings': search_settings,
        'datasets': datasets
    }
    return render(request, 'home.html', context)

@admin_required
def dataset_list(request):
    datasets = BenchmarkDataset.objects.all().order_by('-created_at')
    return JsonResponse({'datasets': list(datasets.values('id', 'name', 'description', 'created_at', 'is_active'))})


@admin_required
def get_dataset_questions(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)
        
        if not dataset.file:
            return JsonResponse({'questions': []})

        questions = []
        with dataset.file.open('r') as f:
            for line in f:
                if line.strip():
                    questions.append(json.loads(line))
        
        return JsonResponse({'questions': questions})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
@require_POST
def activate_dataset(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)
        dataset.is_active = True
        dataset.save()
        return JsonResponse({'status': 'ok', 'active_dataset_id': dataset.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
@require_POST
def dataset_upload(request):
    form = BenchmarkDatasetForm(request.POST, request.FILES)
    if form.is_valid():
        dataset = form.save()
        return JsonResponse({'status': 'ok', 'dataset_id': dataset.id, 'name': dataset.name})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@admin_required
@require_http_methods(["DELETE"])
def dataset_delete(request, dataset_id):
    try:
        dataset = get_object_or_404(BenchmarkDataset, pk=dataset_id)
        dataset.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

from django.core.files.base import ContentFile

@admin_required
@require_POST
def sync_datasets(request):
    try:
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if not os.path.exists(data_dir):
            return JsonResponse({'status': 'error', 'message': 'Data directory not found.'}, status=404)

        added_count = 0
        for filename in os.listdir(data_dir):
            if filename.endswith('.jsonl'):
                # Check if dataset with this name already exists
                if not BenchmarkDataset.objects.filter(name=filename).exists():
                    file_path = os.path.join(data_dir, filename)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Set hard_questions_refined.jsonl as active by default
                    is_active = (filename == 'hard_questions_refined.jsonl')

                    dataset = BenchmarkDataset(
                        name=filename,
                        description=f"Auto-detected from {filename}",
                        is_active=is_active
                    )
                    # Save the file content to the FileField
                    dataset.file.save(filename, ContentFile(content))
                    dataset.save()
                    added_count += 1
        
        # Fallback: If hard_questions_refined.jsonl exists and no dataset is active, make it active
        if not BenchmarkDataset.objects.filter(is_active=True).exists():
            try:
                default_ds = BenchmarkDataset.objects.get(name='hard_questions_refined.jsonl')
                default_ds.is_active = True
                default_ds.save()
            except BenchmarkDataset.DoesNotExist:
                pass
        
        return JsonResponse({'status': 'ok', 'added': added_count})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
def vanilla_llm_adhoc(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            run_name = data.get('name')
            results = data.get('results')
            run_id = data.get('run_id') # New: to identify existing run for updates
            
            if not run_name or not results:
                return JsonResponse({'error': 'Run name and results are required.'}, status=400)

            settings = LLMSettings.load()
            
            total_questions = len(results)
            correct_answers_llm = sum(1 for r in results if r.get('llm_result'))

            if run_id:
                # Update existing run
                run = get_object_or_404(VanillaLLMAdhocRun, pk=run_id)
                run.name = run_name
                run.llm_settings = settings
                run.total_questions = total_questions
                run.correct_answers = correct_answers_llm
                run.accuracy = (correct_answers_llm / total_questions * 100) if total_questions > 0 else 0
                run.save()

                # Delete old results and create new ones
                run.results.all().delete()
            else:
                # Create new run
                run = VanillaLLMAdhocRun.objects.create(
                    name=run_name,
                    llm_settings=settings,
                    total_questions=total_questions,
                    correct_answers=correct_answers_llm,
                    accuracy=(correct_answers_llm / total_questions * 100) if total_questions > 0 else 0
                )

            for result in results:
                VanillaLLMAdhocResult.objects.create(
                    run=run,
                    question=result.get('question', ''),
                    ground_truths=result.get('ground_truths', []),
                    answer=result.get('answer', ''),
                    is_correct_rule=result.get('rule_result', False),
                    is_correct_llm=result.get('llm_result', False)
                )
            
            return JsonResponse({'status': 'ok', 'run_id': run.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET request logic
    runs = VanillaLLMAdhocRun.objects.all().prefetch_related('llm_settings')
    selected_run = None
    run_results = []
    run_id = request.GET.get('run_id')

    if run_id:
        try:
            selected_run = get_object_or_404(VanillaLLMAdhocRun, pk=run_id)
            # Serialize the results to pass as JSON to the template
            run_results = list(selected_run.results.values(
                'question', 'answer', 'ground_truths', 'is_correct_rule', 'is_correct_llm'
            ))
        except (ValueError, TypeError):
            pass # Ignore invalid run_id

    settings_obj = LLMSettings.load()

    # If the settings are empty, try to populate from .env file
    if not settings_obj.llm_api_key and not settings_obj.llm_model:
        try:
            llm_api_key_env = config('LLM_API_KEY', default=None)
            llm_model_env = config('LLM_MODEL', default=None)
            if llm_api_key_env or llm_model_env:
                settings_obj.llm_base_url = config('LLM_BASE_URL', default='')
                settings_obj.llm_api_key = llm_api_key_env or ''
                settings_obj.llm_model = llm_model_env or ''
                settings_obj.save()
        except OperationalError:
            pass
    
    # Load questions from the file
    questions = []
    # Default fallback if no dataset is selected or found
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                # Normalize ground truths
                if 'answer' in data and 'ground_truths' not in data:
                    data['ground_truths'] = data['answer']
                questions.append(data)
    except FileNotFoundError:
        pass

    datasets = BenchmarkDataset.objects.all().order_by('-created_at')

    context = {
        'runs': runs,
        'selected_run': selected_run,
        'run_results_json': json.dumps(run_results),
        'llm_settings': settings_obj,
        'questions': questions,
        'total_questions': len(questions),
        'datasets': datasets
    }
    return render(request, 'vanilla_llm_adhoc.html', context)


@admin_required
def list_runs(request):
    try:
        vanilla_runs = VanillaLLMMultiTurnSession.objects.filter(run_tag__isnull=False).values_list('run_tag', flat=True)
        rag_runs = RAGMultiTurnSession.objects.filter(run_tag__isnull=False).values_list('run_tag', flat=True)
        runs = sorted(list(set(list(vanilla_runs) + list(rag_runs))), reverse=True)
        return JsonResponse({'runs': runs})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def load_run(request, run_tag):
    def stream_run_from_db(run_tag):
        # This function seems to be for ad-hoc runs saved as multi-turn sessions.
        # Defaulting to Vanilla LLM as the model type is not specified.
        sessions = VanillaLLMMultiTurnSession.objects.filter(run_tag=run_tag).prefetch_related('trials')
        for session in sessions:
            trial = session.trials.first()
            if trial:
                result_data = {
                    'question': session.question,
                    'answer': trial.answer,
                    'ground_truths': session.ground_truths,
                    'rule_result': trial.is_correct,
                    'llm_result': trial.is_correct,
                }
                yield json.dumps(result_data) + "\n"

    return StreamingHttpResponse(stream_run_from_db(run_tag), content_type='application/json')


@admin_required
def get_llm_env_vars(request):
    try:
        settings = LLMSettings.load()
        config_data = {
            'llm_base_url': config('LLM_BASE_URL', default=settings.llm_base_url),
            'llm_api_key': config('LLM_API_KEY', default=settings.llm_api_key),
            'llm_model': config('LLM_MODEL', default=settings.llm_model or 'gpt-3.5-turbo'),
        }
        return JsonResponse(config_data)
    except OperationalError:
        return JsonResponse({
            "status": "error", 
            "message": "Database not migrated. Please run migrations for the 'benchmark' app."
        }, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
@csrf_exempt
def batch_delete_sessions(request):
    try:
        data = json.loads(request.body)
        session_ids = data.get('session_ids', [])
        if not session_ids:
            return JsonResponse({'status': 'error', 'message': 'No session IDs provided.'}, status=400)

        try:
            session_ids = [int(sid) for sid in session_ids]
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid session ID format.'}, status=400)

        vanilla_sessions = VanillaLLMMultiTurnSession.objects.filter(id__in=session_ids)
        rag_sessions = RAGMultiTurnSession.objects.filter(id__in=session_ids)
        
        deleted_vanilla_ids = list(vanilla_sessions.values_list('id', flat=True))
        deleted_rag_ids = list(rag_sessions.values_list('id', flat=True))
        
        deleted_count = len(deleted_vanilla_ids) + len(deleted_rag_ids)
        deleted_ids = deleted_vanilla_ids + deleted_rag_ids
        
        vanilla_sessions.delete()
        rag_sessions.delete()

        return JsonResponse({'status': 'ok', 'message': f'{deleted_count} sessions deleted.', 'deleted_ids': deleted_ids})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
        settings_obj.save()
        return JsonResponse({"status": "ok"})
    except OperationalError:
        return JsonResponse({
            "status": "error", 
            "message": "Database not migrated. Please run migrations for the 'benchmark' app to save settings."
        }, status=400)
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
            return JsonResponse({"status": "error", "message": "Base URL and API Key are required."}, status=400)

        timeout = httpx.Timeout(10.0, connect=10.0)
        client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        
        # Test the connection by listing models
        models = client.models.list()
        
        return JsonResponse({"status": "ok", "message": f"Connection successful! Found {len(models.data)} models."})
    except openai.APIConnectionError as e:
        return JsonResponse({"status": "error", "message": f"Connection failed: {e.__cause__}"}, status=400)
    except openai.AuthenticationError as e:
        return JsonResponse({"status": "error", "message": "Authentication failed. Please check your API Key."}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"An unexpected error occurred: {e}"}, status=400)


@admin_required
def vanilla_llm_multi_turn(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        # Handle case where file doesn't exist
        pass

    # Load sessions and group them
    groups = MultiTurnSessionGroup.objects.filter(
        vanilla_sessions__isnull=False
    ).prefetch_related(
        models.Prefetch('vanilla_sessions', queryset=VanillaLLMMultiTurnSession.objects.order_by('-created_at'))
    ).order_by('-created_at').distinct()
    
    individual_sessions = VanillaLLMMultiTurnSession.objects.filter(group__isnull=True).order_by('-created_at')

    datasets = BenchmarkDataset.objects.all().order_by('-created_at')

    context = {
        'questions': questions,
        'groups': groups,
        'individual_sessions': individual_sessions,
        'llm_settings': LLMSettings.load(),
        'datasets': datasets
    }
    return render(request, 'vanilla_llm_multi_turn.html', context)


@admin_required
def rag_multi_turn(request):
    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f:
            for line in f:
                questions.append(json.loads(line))
    except FileNotFoundError:
        pass

    # Load sessions and group them
    groups = MultiTurnSessionGroup.objects.filter(
        rag_sessions__isnull=False
    ).prefetch_related(
        models.Prefetch('rag_sessions', queryset=RAGMultiTurnSession.objects.order_by('-created_at'))
    ).order_by('-created_at').distinct()
    
    individual_sessions = RAGMultiTurnSession.objects.filter(group__isnull=True).order_by('-created_at')

    datasets = BenchmarkDataset.objects.all().order_by('-created_at')

    context = {
        'questions': questions,
        'groups': groups,
        'individual_sessions': individual_sessions,
        'llm_settings': LLMSettings.load(),
        'datasets': datasets
    }
    return render(request, 'rag_multi_turn.html', context)


@admin_required
def rag_adhoc(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            run_name = data.get('name')
            results = data.get('results')
            run_id = data.get('run_id') # New: to identify existing run for updates
            
            if not run_name or not results:
                return JsonResponse({'error': 'Run name and results are required.'}, status=400)

            llm_settings = LLMSettings.load()
            rag_settings = RagSettings.load()
            
            total_questions = len(results)
            correct_answers_llm = sum(1 for r in results if r.get('llm_result'))

            if run_id:
                # Update existing run
                run = get_object_or_404(RagAdhocRun, pk=run_id)
                run.name = run_name
                run.llm_settings = llm_settings
                run.rag_settings = rag_settings
                run.total_questions = total_questions
                run.correct_answers = correct_answers_llm
                run.accuracy = (correct_answers_llm / total_questions * 100) if total_questions > 0 else 0
                run.save()
                
                # Delete old results and create new ones
                run.results.all().delete()
            else:
                # Create new run
                run = RagAdhocRun.objects.create(
                    name=run_name,
                    llm_settings=llm_settings,
                    rag_settings=rag_settings,
                    total_questions=total_questions,
                    correct_answers=correct_answers_llm,
                    accuracy=(correct_answers_llm / total_questions * 100) if total_questions > 0 else 0
                )

            for result in results:
                RagAdhocResult.objects.create(
                    run=run,
                    question=result.get('question', ''),
                    ground_truths=result.get('ground_truths', []),
                    answer=result.get('answer', ''),
                    is_correct_rule=result.get('rule_result', False),
                    is_correct_llm=result.get('llm_result'),
                    num_docs_used=result.get('num_docs_used', 0),
                    search_results=result.get('search_results', [])
                )
            
            return JsonResponse({'status': 'ok', 'run_id': run.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # Load questions from the file
    questions = []
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                if 'answer' in data and 'ground_truths' not in data:
                    data['ground_truths'] = data['answer']
                questions.append(data)
    except FileNotFoundError:
        pass

    datasets = BenchmarkDataset.objects.all().order_by('-created_at')

    context = {
        'questions': questions,
        'total_questions': len(questions),
        'llm_settings': LLMSettings.load(),
        'rag_settings': RagSettings.load(),
        'datasets': datasets
    }
    return render(request, 'rag_adhoc.html', context)

@admin_required
@require_POST
def save_rag_settings(request):
    try:
        data = json.loads(request.body)
        settings = RagSettings.load()
        settings.prompt_template = data.get('prompt_template', settings.prompt_template)
        settings.save()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@admin_required
@require_POST
def save_search_settings(request):
    try:
        data = json.loads(request.body)
        settings = SearchSettings.load()
        settings.search_provider = data.get('search_provider', settings.search_provider)
        settings.serper_api_key = data.get('serper_api_key', settings.serper_api_key)
        settings.save()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)




@admin_required
def list_rag_adhoc_runs(request):
    try:
        runs = RagAdhocRun.objects.values('id', 'name', 'created_at', 'accuracy').order_by('-created_at')
        return JsonResponse({'runs': list(runs)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def get_rag_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(RagAdhocRun, pk=run_id)
        results = list(run.results.values('question', 'answer', 'ground_truths', 'is_correct_rule', 'is_correct_llm', 'num_docs_used', 'search_results'))
        run_data = {
            'id': run.id,
            'name': run.name,
            'created_at': run.created_at,
            'accuracy': run.accuracy,
            'total_questions': run.total_questions,
            'correct_answers': run.correct_answers,
            'results': results
        }
        return JsonResponse(run_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_rag_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(RagAdhocRun, pk=run_id)
        run.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_POST
def create_session_group(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', f"Pipeline Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        group = MultiTurnSessionGroup.objects.create(name=name)
        return JsonResponse({'group_id': group.id, 'group_name': group.name})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def create_session(request):
    try:
        data = json.loads(request.body)
        question_text = data.get('question')
        ground_truths = data.get('ground_truths')
        group_id = data.get('group_id')
        pipeline_type = data.get('pipeline_type', 'vanilla_llm_multi_turn') # Default to 'vanilla_llm_multi_turn'

        if not question_text or not ground_truths:
            return JsonResponse({'error': 'Question and ground truths are required.'}, status=400)

        settings = LLMSettings.load()
        
        session_data = {
            "llm_settings": settings,
            "question": question_text,
            "ground_truths": ground_truths,
        }
        
        if group_id:
            session_data['group'] = get_object_or_404(MultiTurnSessionGroup, pk=group_id)

        if 'rag' in pipeline_type:
            rag_settings = RagSettings.load()
            session_data['rag_settings'] = rag_settings
            if 'reform' in pipeline_type:
                session_data['reformulation_strategy'] = 'reform'
            else:
                session_data['reformulation_strategy'] = 'no_reform'
            
            session = RAGMultiTurnSession.objects.create(**session_data)
            trial = RAGMultiTurnTrial.objects.create(
                session=session,
                trial_number=1,
                status='processing'
            )
        else:
            session = VanillaLLMMultiTurnSession.objects.create(**session_data)
            trial = VanillaLLMMultiTurnTrial.objects.create(
                session=session,
                trial_number=1,
                status='processing'
            )
        
        return JsonResponse({'session_id': session.id, 'trial_id': trial.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def get_session(request, session_id):
    try:
        session = VanillaLLMMultiTurnSession.objects.select_related('llm_settings').get(pk=session_id)
        pipeline_type = 'vanilla_llm_multi_turn'
    except VanillaLLMMultiTurnSession.DoesNotExist:
        try:
            session = RAGMultiTurnSession.objects.select_related('llm_settings', 'rag_settings').get(pk=session_id)
            pipeline_type = f"rag_multi_turn_{session.reformulation_strategy}"
        except RAGMultiTurnSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)

    if isinstance(session, RAGMultiTurnSession):
        trials = list(session.trials.values(
            'id', 'trial_number', 'answer', 'feedback', 'is_correct',
            'created_at', 'status', 'search_query', 'search_results'
        ))
    else:
        trials = list(session.trials.values(
            'id', 'trial_number', 'answer', 'feedback', 'is_correct',
            'created_at', 'status'
        ))

    return JsonResponse({
        'session': {
            'id': session.id,
            'question': session.question,
            'ground_truths': session.ground_truths,
            'is_completed': session.is_completed,
            'created_at': session.created_at,
            'max_retries': session.llm_settings.max_retries,
            'group_id': session.group_id,
            'pipeline_type': pipeline_type
        },
        'trials': trials
    })

@admin_required
@require_POST
def retry_session(request, trial_id):
    try:
        data = json.loads(request.body)
        feedback = data.get('feedback')
        is_correct = data.get('is_correct')

        try:
            original_trial = VanillaLLMMultiTurnTrial.objects.select_related('session__llm_settings').get(pk=trial_id)
            TrialModel = VanillaLLMMultiTurnTrial
        except VanillaLLMMultiTurnTrial.DoesNotExist:
            try:
                original_trial = RAGMultiTurnTrial.objects.select_related('session__llm_settings').get(pk=trial_id)
                TrialModel = RAGMultiTurnTrial
            except RAGMultiTurnTrial.DoesNotExist:
                return JsonResponse({'error': 'Trial not found'}, status=404)

        original_trial.feedback = feedback
        original_trial.is_correct = is_correct
        original_trial.save()

        session = original_trial.session

        if is_correct:
            session.is_completed = True
            session.save()
            return JsonResponse({'status': 'completed', 'session_id': session.id})

        if session.trials.count() >= session.llm_settings.max_retries:
            session.is_completed = True
            session.save()
            return JsonResponse({'status': 'max_retries_reached', 'session_id': session.id})

        new_trial = TrialModel.objects.create(
            session=session,
            trial_number=original_trial.trial_number + 1,
            status='processing'
        )

        return JsonResponse({'status': 'retrying', 'new_trial_id': new_trial.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

import traceback

@admin_required
def run_trial(request, trial_id):
    try:
        try:
            trial = VanillaLLMMultiTurnTrial.objects.select_related('session__llm_settings').get(pk=trial_id)
        except VanillaLLMMultiTurnTrial.DoesNotExist:
            try:
                trial = RAGMultiTurnTrial.objects.select_related('session__llm_settings').get(pk=trial_id)
            except RAGMultiTurnTrial.DoesNotExist:
                return JsonResponse({'error': 'Trial not found'}, status=404)

        session = trial.session
        db_settings = session.llm_settings

        base_url = db_settings.llm_base_url or config("LLM_BASE_URL", default=None)
        api_key = db_settings.llm_api_key or config("LLM_API_KEY", default=None)
        model = db_settings.llm_model or config("LLM_MODEL", default='gpt-3.5-turbo')
        
        if isinstance(session, RAGMultiTurnSession):
            pipeline = RagMultiTurnPipeline(
                base_url=base_url, 
                api_key=api_key, 
                model=model, 
                max_retries=1,
                reformulation_strategy=session.reformulation_strategy
            )
        else:
            pipeline = VanillaLLMMultiTurnPipeline(
                base_url=base_url, 
                api_key=api_key, 
                model=model, 
                max_retries=1
            )
        
        answer, is_correct, search_results = pipeline.run_single_turn(session, trial)
        
        if is_correct:
            session.is_completed = True
            session.save()

        num_docs_used = len(search_results) if search_results else 0

        return JsonResponse({'answer': answer, 'trial_id': trial.id, 'is_correct': is_correct, 'num_docs_used': num_docs_used})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'trial_id': trial_id}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_session(request, session_id):
    try:
        try:
            session = VanillaLLMMultiTurnSession.objects.get(pk=session_id)
            session.delete()
        except VanillaLLMMultiTurnSession.DoesNotExist:
            try:
                session = RAGMultiTurnSession.objects.get(pk=session_id)
                session.delete()
            except RAGMultiTurnSession.DoesNotExist:
                pass  # Session already deleted
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_session_group(request, group_id):
    try:
        group = get_object_or_404(MultiTurnSessionGroup, pk=group_id)
        group.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@admin_required
def run_vanilla_llm_multi_turn_pipeline(request):
    try:
        base_url = request.GET.get('llm_base_url') or config("LLM_BASE_URL", default=None)
        api_key = request.GET.get('llm_api_key') or config("LLM_API_KEY", default=None)
        model = request.GET.get('llm_model') or config("LLM_MODEL", default='gpt-3.5-turbo')
        max_retries = int(request.GET.get('max_retries', 3))
        pipeline_id = request.GET.get('pipeline_id')
        dataset_id = request.GET.get('dataset_id')

        if not api_key:
            return JsonResponse({'error': 'An API Key is required to run the benchmark.'}, status=400)

        if pipeline_id:
            redis_client.set(f"vanilla_llm_multi_turn_pipeline_active:{pipeline_id}", "1", ex=3600)

        pipeline = VanillaLLMMultiTurnPipeline(
            base_url=base_url, 
            api_key=api_key, 
            model=model, 
            max_retries=max_retries, 
            pipeline_id=pipeline_id, 
            dataset_id=dataset_id
        )
        return StreamingHttpResponse(pipeline.run(), content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
@require_POST
def stop_vanilla_llm_multi_turn_pipeline(request):
    try:
        data = json.loads(request.body)
        pipeline_id = data.get('pipeline_id')
        if pipeline_id:
            redis_client.delete(f"vanilla_llm_multi_turn_pipeline_active:{pipeline_id}")
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@admin_required
@require_POST
def run_vanilla_llm_adhoc_pipeline(request):
    try:
        pipeline_id = request.POST.get('pipeline_id')
        dataset_id = request.POST.get('dataset_id')

        if pipeline_id:
            redis_client.set(f"vanilla_llm_adhoc_pipeline_active:{pipeline_id}", "1", ex=3600)

        pipeline = VanillaLLMAdhocPipeline(
            base_url=request.POST.get('llm_base_url'),
            api_key=request.POST.get('llm_api_key'),
            model=request.POST.get('llm_model'),
            pipeline_id=pipeline_id,
            dataset_id=dataset_id
        )
        
        def stream_generator():
            try:
                for result in pipeline.run():
                    yield json.dumps(result) + "\n"
            except Exception as e:
                yield json.dumps({"error": str(e)}) + "\n"

        return StreamingHttpResponse(stream_generator(), content_type='application/json')

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_POST
def stop_vanilla_llm_adhoc_pipeline(request):
    try:
        data = json.loads(request.body)
        pipeline_id = data.get('pipeline_id')
        if pipeline_id:
            redis_client.delete(f"vanilla_llm_adhoc_pipeline_active:{pipeline_id}")
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@admin_required
@require_POST
def run_rag_adhoc_pipeline(request):
    try:
        pipeline_id = request.POST.get('pipeline_id')
        dataset_id = request.POST.get('dataset_id')

        if pipeline_id:
            redis_client.set(f"rag_adhoc_pipeline_active:{pipeline_id}", "1", ex=3600)

        pipeline = RagAdhocPipeline(
            base_url=request.POST.get('llm_base_url'),
            api_key=request.POST.get('llm_api_key'),
            model=request.POST.get('llm_model'),
            rag_prompt_template=request.POST.get('rag_prompt_template'),
            pipeline_id=pipeline_id,
            dataset_id=dataset_id
        )
        
        def stream_generator():
            try:
                for result in pipeline.run():
                    yield json.dumps(result) + "\n"
            except Exception as e:
                yield json.dumps({"error": str(e)}) + "\n"

        return StreamingHttpResponse(stream_generator(), content_type='application/json')

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_POST
def stop_rag_adhoc_pipeline(request):
    try:
        data = json.loads(request.body)
        pipeline_id = data.get('pipeline_id')
        if pipeline_id:
            redis_client.delete(f"rag_adhoc_pipeline_active:{pipeline_id}")
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)




@admin_required
def export_session(request, session_id):
    try:
        session = VanillaLLMMultiTurnSession.objects.select_related('llm_settings').get(pk=session_id)
        pipeline_type = 'vanilla_llm_multi_turn'
    except VanillaLLMMultiTurnSession.DoesNotExist:
        try:
            session = RAGMultiTurnSession.objects.select_related('llm_settings').get(pk=session_id)
            pipeline_type = f"rag_multi_turn_{session.reformulation_strategy}"
        except RAGMultiTurnSession.DoesNotExist:
            return HttpResponse("Session not found", status=404)

    if isinstance(session, RAGMultiTurnSession):
        trials = list(session.trials.values(
            'trial_number', 'answer', 'feedback', 'is_correct', 
            'created_at', 'search_query', 'search_results'
        ))
    else:
        trials = list(session.trials.values(
            'trial_number', 'answer', 'feedback', 'is_correct', 
            'created_at'
        ))
    
    export_data = {
        'session_id': session.id,
        'question': session.question,
        'ground_truths': session.ground_truths,
        'is_completed': session.is_completed,
        'pipeline_type': pipeline_type,
        'created_at': session.created_at.isoformat(),
        'max_retries': session.llm_settings.max_retries,
        'trials': trials
    }

    response = HttpResponse(json.dumps(export_data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="benchmark_session_{session_id}.json"'
    return response

@admin_required
@require_POST
def save_run(request):
    try:
        body = json.loads(request.body)
        run_name = body.get('name')
        run_data = body.get('data')
        run_config = body.get('config')

        if not run_name:
            return JsonResponse({"status": "error", "message": "Invalid data format: 'name' is missing."}, status=400)
        if not isinstance(run_data, list):
            return JsonResponse({"status": "error", "message": "Invalid data format: 'data' is not a list."}, status=400)
        
        settings = LLMSettings.load()

        if isinstance(run_config, dict):
            settings.llm_base_url = run_config.get('llm_base_url', settings.llm_base_url)
            settings.llm_model = run_config.get('llm_model', settings.llm_model)
            settings.llm_api_key = run_config.get('llm_api_key', settings.llm_api_key)
            settings.save()

        for result in run_data:
            if not result.get('question'):
                continue

            session = VanillaLLMMultiTurnSession.objects.create(
                llm_settings=settings,
                question=result.get('question'),
                ground_truths=result.get('ground_truths'),
                run_tag=run_name,
                is_completed=True 
            )
            VanillaLLMMultiTurnTrial.objects.create(
                session=session,
                trial_number=1,
                answer=result.get('answer'),
                is_correct=result.get('rule_result')
            )
        
        return JsonResponse({"status": "ok", "filename": run_name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@admin_required
@require_http_methods(["DELETE"])
def delete_run(request, run_tag):
    try:
        VanillaLLMMultiTurnSession.objects.filter(run_tag=run_tag).delete()
        RAGMultiTurnSession.objects.filter(run_tag=run_tag).delete()
        return JsonResponse({"status": "ok", "filename": run_tag})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
def load_vanilla_llm_multi_turn_run(request, group_id):
    group = get_object_or_404(MultiTurnSessionGroup, pk=group_id)
    sessions = group.vanilla_sessions.all().prefetch_related('trials')
    
    results = []
    for session in sessions:
        last_trial = session.trials.last()
        if last_trial:
            results.append({
                'question': session.question,
                'correct': last_trial.is_correct,
                'trials': session.trials.count(),
                'session_id': session.id,
                'final_answer': last_trial.answer,
                'ground_truths': session.ground_truths,
                'max_retries': session.llm_settings.max_retries
            })

    return JsonResponse({'results': results, 'group_name': group.name})




@admin_required
def list_vanilla_llm_adhoc_runs(request):
    try:
        runs = VanillaLLMAdhocRun.objects.values('id', 'name', 'created_at', 'accuracy').order_by('-created_at')
        return JsonResponse({'runs': list(runs)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def get_vanilla_llm_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(VanillaLLMAdhocRun, pk=run_id)
        results = list(run.results.values('question', 'answer', 'ground_truths', 'is_correct_rule', 'is_correct_llm'))
        run_data = {
            'id': run.id,
            'name': run.name,
            'created_at': run.created_at,
            'accuracy': run.accuracy,
            'total_questions': run.total_questions,
            'correct_answers': run.correct_answers,
            'settings': {
                'llm_model': run.llm_settings.llm_model if run.llm_settings else 'N/A'
            },
            'results': results
        }
        return JsonResponse(run_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def web_search(request):
    try:
        data = json.loads(request.body)
        query = data.get('query')

        if not query:
            return JsonResponse({'error': 'Query is required.'}, status=400)

        search_engine = get_search_engine()
        results = search_engine.search(query)
        
        return JsonResponse({'results': results})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@admin_required
@require_http_methods(["DELETE"])
def delete_vanilla_llm_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(VanillaLLMAdhocRun, pk=run_id)
        run.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
@admin_required
def get_default_rag_prompt(request):
    default_prompt = RagSettings._meta.get_field('prompt_template').get_default()
    return JsonResponse({'default_prompt': default_prompt})
