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
from task_manager.utils import check_answer_rule, check_answer_llm

from datetime import datetime
from .models import LLMSettings, InteractiveSession, InteractiveTrial, AdhocRun, AdhocSessionResult, InteractiveSessionGroup


@admin_required
def index(request):
    settings = LLMSettings.load()
    context = {
        'llm_settings': settings
    }
    return render(request, 'benchmark/index.html', context)


def qa_pipeline_stream(base_url, api_key, model, questions_data=None):
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    
    def process_line(line):
        data = json.loads(line)
        question = data['question']
        ground_truths = data.get('answer', data.get('ground_truths', [])) # Flexibility for different key names

        try:
            answer_prompt = f"""Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {question}
Answer:"""
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": answer_prompt}]
            )
            answer = response.choices[0].message.content
            
            rule_result = check_answer_rule(question, ground_truths, answer)
            llm_result = check_answer_llm(question, ground_truths, answer, client=client, model=model)

            result_data = {
                'question': question,
                'answer': answer,
                'ground_truths': ground_truths,
                'rule_result': rule_result,
                'llm_result': llm_result
            }
            
            return json.dumps(result_data) + "\n"

        except Exception as e:
            # Echo back the question on error to help with identification
            error_data = {'error': str(e), 'question': question}
            return json.dumps(error_data) + "\n"

    if questions_data:
        for item in questions_data:
            # When retrying, the data is already a dict, not a JSON string
            yield process_line(json.dumps(item))
    else:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f_in:
            for line in f_in:
                yield process_line(line)

@admin_required
def adhoc_llm(request):
    if request.method == 'POST':
        try:
            # This logic is now for saving the results of a run
            data = json.loads(request.body)
            run_name = data.get('name')
            results = data.get('results')
            
            if not run_name or not results:
                return JsonResponse({'error': 'Run name and results are required.'}, status=400)

            settings = LLMSettings.load()
            
            total_questions = len(results)
            correct_answers_llm = sum(1 for r in results if r.get('llm_result'))

            run = AdhocRun.objects.create(
                name=run_name,
                settings=settings,
                total_questions=total_questions,
                correct_answers=correct_answers_llm,
                accuracy=(correct_answers_llm / total_questions * 100) if total_questions > 0 else 0
            )

            for result in results:
                AdhocSessionResult.objects.create(
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
    runs = AdhocRun.objects.all().prefetch_related('settings')
    selected_run = None
    run_results = []
    run_id = request.GET.get('run_id')

    if run_id:
        try:
            selected_run = get_object_or_404(AdhocRun, pk=run_id)
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
            # This can happen if migrations haven't been run yet.
            # We can't save, but we can still pass the .env values to the context.
            pass
    
    context = {
        'runs': runs,
        'selected_run': selected_run,
        'run_results_json': json.dumps(run_results),
        'llm_settings': settings_obj
    }
    return render(request, 'adhoc_llm.html', context)


@admin_required
def list_runs(request):
    try:
        runs = InteractiveSession.objects.filter(run_tag__isnull=False).values_list('run_tag', flat=True).distinct().order_by('-run_tag')
        return JsonResponse({'runs': list(runs)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def load_run(request, run_tag):
    def stream_run_from_db(run_tag):
        sessions = InteractiveSession.objects.filter(run_tag=run_tag).prefetch_related('trials')
        for session in sessions:
            trial = session.trials.first() # Assuming one trial per session for ad-hoc runs
            if trial:
                # Reconstruct the result structure expected by the frontend
                result_data = {
                    'question': session.question,
                    'answer': trial.answer,
                    'ground_truths': session.ground_truths,
                    'rule_result': trial.is_correct,
                    'llm_result': trial.is_correct, # Assuming rule_result and llm_result are the same for now
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

        # Ensure all IDs are integers
        try:
            session_ids = [int(sid) for sid in session_ids]
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid session ID format.'}, status=400)

        sessions_to_delete = InteractiveSession.objects.filter(id__in=session_ids)
        deleted_count = sessions_to_delete.count()
        deleted_ids = list(sessions_to_delete.values_list('id', flat=True))
        
        sessions_to_delete.delete()

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


from django.views.decorators.http import require_http_methods
import re

@admin_required
def interactive_llm(request):
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
    groups = InteractiveSessionGroup.objects.prefetch_related(
        models.Prefetch('sessions', queryset=InteractiveSession.objects.order_by('-created_at'))
    ).order_by('-created_at')
    
    individual_sessions = InteractiveSession.objects.filter(group__isnull=True).order_by('-created_at')

    context = {
        'questions': questions,
        'groups': groups,
        'individual_sessions': individual_sessions,
        'llm_settings': LLMSettings.load()
    }
    return render(request, 'interactive_llm.html', context)

@csrf_exempt
@require_POST
def create_session_group(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', f"Pipeline Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        group = InteractiveSessionGroup.objects.create(name=name)
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

        if not question_text or not ground_truths:
            return JsonResponse({'error': 'Question and ground truths are required.'}, status=400)

        settings = LLMSettings.load()
        
        session_data = {
            "settings": settings,
            "question": question_text,
            "ground_truths": ground_truths
        }
        
        if group_id:
            session_data['group'] = get_object_or_404(InteractiveSessionGroup, pk=group_id)

        session = InteractiveSession.objects.create(**session_data)
        
        trial = InteractiveTrial.objects.create(
            session=session,
            trial_number=1,
            status='processing'
        )
        
        return JsonResponse({'session_id': session.id, 'trial_id': trial.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def get_session(request, session_id):
    session = get_object_or_404(InteractiveSession, pk=session_id)
    trials = list(session.trials.values('id', 'trial_number', 'answer', 'feedback', 'is_correct', 'created_at', 'status'))
    return JsonResponse({
        'session': {
            'id': session.id,
            'question': session.question,
            'ground_truths': session.ground_truths,
            'is_completed': session.is_completed,
            'created_at': session.created_at,
            'max_retries': session.settings.max_retries,
            'group_id': session.group_id
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

        original_trial = get_object_or_404(InteractiveTrial, pk=trial_id)
        original_trial.feedback = feedback
        original_trial.is_correct = is_correct
        original_trial.save()

        session = original_trial.session

        if is_correct:
            session.is_completed = True
            session.save()
            return JsonResponse({'status': 'completed', 'session_id': session.id})

        if session.trials.count() >= session.settings.max_retries:
            session.is_completed = True
            session.save()
            return JsonResponse({'status': 'max_retries_reached', 'session_id': session.id})

        new_trial = InteractiveTrial.objects.create(
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
        trial = get_object_or_404(InteractiveTrial, pk=trial_id)
        session = trial.session
        db_settings = session.settings

        # Fallback logic for settings
        base_url = db_settings.llm_base_url or config("LLM_BASE_URL", default=None)
        api_key = db_settings.llm_api_key or config("LLM_API_KEY", default=None)
        model = db_settings.llm_model or config("LLM_MODEL", default='gpt-3.5-turbo')

        if not base_url or not api_key:
            trial.status = 'error'
            trial.save()
            return JsonResponse({
                'error': 'LLM Base URL or API Key is not configured. Please configure them in the LLM Configuration section or your .env file.',
                'trial_id': trial.id
            }, status=400)

        messages = []
        if trial.trial_number == 1:
            # First turn
            answer_prompt = f"""Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {session.question}
Answer:"""
            messages.append({"role": "user", "content": answer_prompt})
        else:
            # Subsequent turns
            messages.append({"role": "user", "content": f"Question: {session.question}"})
            for prev_trial in session.trials.order_by('trial_number'):
                if prev_trial.id < trial.id:
                    if prev_trial.answer:
                        messages.append({"role": "assistant", "content": prev_trial.answer})
                    if prev_trial.is_correct == False:
                        messages.append({"role": "user", "content": "Your previous answer was incorrect."})
            
            # Re-iterate the strict rules for retries.
            strict_rules = """Your task is to answer the question again. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Answer:"""
            messages.append({"role": "user", "content": strict_rules})
            
        client = openai.OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        answer = response.choices[0].message.content
        print_debug(f"LLM Response: {answer}")

        trial.answer = answer
        
        # Perform automated judgment
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=client, model=model)
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        
        trial.status = 'completed'
        trial.save()

        # If the answer is correct or max retries are reached, mark the session as completed
        if is_correct or trial.trial_number >= session.settings.max_retries:
            session.is_completed = True
            session.save()

        return JsonResponse({'answer': answer, 'trial_id': trial.id})
    except Exception as e:
        traceback.print_exc()
        trial.status = 'error'
        trial.save()
        return JsonResponse({'error': str(e), 'trial_id': trial.id}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_session(request, session_id):
    try:
        session = get_object_or_404(InteractiveSession, pk=session_id)
        session.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_session_group(request, group_id):
    try:
        group = get_object_or_404(InteractiveSessionGroup, pk=group_id)
        group.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@admin_required
def export_session(request, session_id):
    session = get_object_or_404(InteractiveSession, pk=session_id)
    trials = list(session.trials.values('trial_number', 'answer', 'feedback', 'is_correct', 'created_at'))
    
    export_data = {
        'session_id': session.id,
        'question': session.question,
        'ground_truths': session.ground_truths,
        'is_completed': session.is_completed,
        'created_at': session.created_at.isoformat(),
        'max_retries': session.settings.max_retries,
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

        # Conditionally update settings only if config is provided correctly
        if isinstance(run_config, dict):
            settings.llm_base_url = run_config.get('llm_base_url', settings.llm_base_url)
            settings.llm_model = run_config.get('llm_model', settings.llm_model)
            settings.llm_api_key = run_config.get('llm_api_key', settings.llm_api_key)
            settings.save()

        for result in run_data:
            # Skip entries that are errors and don't have the necessary data
            if not result.get('question'):
                continue

            session = InteractiveSession.objects.create(
                settings=settings,
                question=result.get('question'),
                ground_truths=result.get('ground_truths'),
                run_tag=run_name,
                is_completed=True 
            )
            InteractiveTrial.objects.create(
                session=session,
                trial_number=1,
                answer=result.get('answer'),
                is_correct=result.get('rule_result') # Storing the rule_result as the correctness
            )
        
        return JsonResponse({"status": "ok", "filename": run_name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@admin_required
@require_http_methods(["DELETE"])
def delete_run(request, run_tag):
    try:
        InteractiveSession.objects.filter(run_tag=run_tag).delete()
        return JsonResponse({"status": "ok", "filename": run_name})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@admin_required
def load_interactive_run(request, group_id):
    group = get_object_or_404(InteractiveSessionGroup, pk=group_id)
    sessions = group.sessions.all().prefetch_related('trials')
    
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
                'max_retries': session.settings.max_retries
            })

    return JsonResponse({'results': results, 'group_name': group.name})


@admin_required
def run_adhoc_pipeline(request):
    try:
        pipeline_base_url = request.GET.get('llm_base_url') or config("LLM_BASE_URL", default=None)
        pipeline_api_key = request.GET.get('llm_api_key') or config("LLM_API_KEY", default=None)
        pipeline_model = request.GET.get('llm_model') or config("LLM_MODEL", default='gpt-3.5-turbo')

        if not pipeline_api_key:
            return JsonResponse({'error': 'An API Key is required to run the benchmark.'}, status=400)

        return StreamingHttpResponse(qa_pipeline_stream(pipeline_base_url, pipeline_api_key, pipeline_model), content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def list_adhoc_runs(request):
    try:
        runs = AdhocRun.objects.values('id', 'name', 'created_at', 'accuracy').order_by('-created_at')
        return JsonResponse({'runs': list(runs)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def get_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id)
        results = list(run.results.values('question', 'answer', 'ground_truths', 'is_correct_rule', 'is_correct_llm'))
        run_data = {
            'id': run.id,
            'name': run.name,
            'created_at': run.created_at,
            'accuracy': run.accuracy,
            'total_questions': run.total_questions,
            'correct_answers': run.correct_answers,
            'settings': {
                'llm_model': run.settings.llm_model if run.settings else 'N/A'
            },
            'results': results
        }
        return JsonResponse(run_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
@require_http_methods(["DELETE"])
def delete_adhoc_run(request, run_id):
    try:
        run = get_object_or_404(AdhocRun, pk=run_id)
        run.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)