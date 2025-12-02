from django.views.decorators.http import require_POST, require_http_methods
import re
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
import openai
from decouple import config
import os
import json
from user_system.decorators import admin_required
from django.db import OperationalError

from task_manager.utils import check_answer_rule, check_answer_llm

from datetime import datetime
from .models import LLMSettings


def qa_pipeline_stream(base_url, api_key, model):
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
    
    with open(file_path, 'r') as f_in:
        for line in f_in:
            data = json.loads(line)
            question = data['question']
            ground_truths = data['answer']

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
                
                # Perform dual validation
                rule_result = check_answer_rule(question, ground_truths, answer)
                llm_result = check_answer_llm(question, ground_truths, answer, client=client, model=model)

                # Backend rendering of ground truths HTML
                remaining_count = len(ground_truths) - 3
                gt_html = f'<ul class="list-unstyled mb-0" data-expanded="false" data-remaining="{remaining_count}">'
                for i, gt in enumerate(ground_truths):
                    display_style = 'style="display:none;"' if i >= 3 else ''
                    gt_html += f'<li class="text-secondary small ground-truth-item" {display_style}><i class="bi bi-dot me-1 text-muted"></i>{gt}</li>'
                if len(ground_truths) > 3:
                    gt_html += f'<li class="show-more-item"><a href="#" class="toggle-answers-link small text-decoration-none">... Show {remaining_count} more</a></li>'
                gt_html += '</ul>'

                result_data = {
                    'question': question,
                    'answer': answer,
                    'ground_truths': ground_truths,
                    'rule_result': rule_result,
                    'llm_result': llm_result
                }
                
                yield json.dumps(result_data) + "\n"

            except Exception as e:
                error_data = {'error': str(e)}
                yield json.dumps(error_data) + "\n"

@admin_required
def naive_llm(request):
    if request.method == 'POST':
        try:
            # Explicitly define the configuration precedence to avoid errors.
            # Use specific variable names to avoid any potential naming conflicts.
            # 1. Start with values from the submitted form.
            pipeline_base_url = request.POST.get('llm_base_url')
            pipeline_api_key = request.POST.get('llm_api_key')
            pipeline_model = request.POST.get('llm_model')

            # 2. If a form value is missing, fall back to the .env file.
            if not pipeline_base_url:
                pipeline_base_url = config("LLM_BASE_URL", default=None)
            if not pipeline_api_key:
                pipeline_api_key = config("LLM_API_KEY", default=None)
            if not pipeline_model:
                pipeline_model = config("LLM_MODEL", default=None)

            # 3. If there's still no model, use a hardcoded default.
            if not pipeline_model:
                pipeline_model = 'gpt-3.5-turbo'

            # 4. Final validation: API key is mandatory.
            if not pipeline_api_key:
                return JsonResponse({'error': 'An API Key is required to run the benchmark.'}, status=400)

            return StreamingHttpResponse(qa_pipeline_stream(pipeline_base_url, pipeline_api_key, pipeline_model), content_type='application/json')
        except Exception as e:
            # Catch any other unexpected errors during the run.
            return JsonResponse({'error': str(e)}, status=500)

    # Logic for the GET request (loading the page)
    try:
        settings_obj = LLMSettings.load()
        # On first run, if the database is empty, automatically populate it from the .env file.
        if not settings_obj.llm_api_key and not settings_obj.llm_model:
            llm_api_key_env = config('LLM_API_KEY', default=None)
            llm_model_env = config('LLM_MODEL', default=None)
            
            if llm_api_key_env or llm_model_env:
                settings_obj.llm_base_url = config('LLM_BASE_URL', default='')
                settings_obj.llm_api_key = llm_api_key_env or ''
                settings_obj.llm_model = llm_model_env or 'gpt-3.5-turbo'
                settings_obj.save()

        context = {
            'llm_base_url': settings_obj.llm_base_url,
            'llm_api_key': settings_obj.llm_api_key,
            'llm_model': settings_obj.llm_model,
        }
    except OperationalError:
        # This can happen if the migrations haven't been run yet. Fallback to .env for display only.
        context = {
            'llm_base_url': config('LLM_BASE_URL', default=''),
            'llm_api_key': config('LLM_API_KEY', default=''),
            'llm_model': config('LLM_MODEL', default='gpt-3.5-turbo'),
        }

    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')
        with open(file_path, 'r') as f:
            context['total_questions'] = sum(1 for line in f)
    except FileNotFoundError:
        context['total_questions'] = 0

    return render(request, 'naive_llm.html', context)

@admin_required
def list_runs(request):
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    if not os.path.exists(results_dir):
        return JsonResponse({'runs': []})

    try:
        # Sort files by modification time, newest first
        files = sorted(
            [f for f in os.listdir(results_dir) if f.endswith('.jsonl')],
            key=lambda f: os.path.getmtime(os.path.join(results_dir, f)),
            reverse=True
        )
        return JsonResponse({'runs': files})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def load_run(request, filename):
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    file_path = os.path.join(results_dir, filename)

    if not os.path.exists(file_path):
        return JsonResponse({'error': 'File not found'}, status=404)

    def file_streamer_with_conversion(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Convert old string format to new array format for backward compatibility
                    if isinstance(data.get('ground_truths'), str):
                        data['ground_truths'] = [s.strip() for s in data['ground_truths'].split(',')]
                    yield json.dumps(data) + "\n"
                except json.JSONDecodeError:
                    # Skip corrupted lines if any
                    continue

    return StreamingHttpResponse(file_streamer_with_conversion(file_path), content_type='application/json')

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

@admin_required
@require_POST
def save_llm_settings(request):
    try:
        data = json.loads(request.body)
        settings_obj = LLMSettings.load()
        settings_obj.llm_base_url = data.get("llm_base_url", "")
        settings_obj.llm_model = data.get("llm_model", "")
        settings_obj.llm_api_key = data.get("llm_api_key", "")
        settings_obj.save()
        return JsonResponse({"status": "ok"})
    except OperationalError:
        return JsonResponse({
            "status": "error", 
            "message": "Database not migrated. Please run migrations for the 'benchmark' app to save settings."
        }, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


from django.views.decorators.http import require_http_methods
import re

@admin_required
@require_POST
def save_run(request):
    try:
        body = json.loads(request.body)
        run_name = body.get('name')
        run_data = body.get('data')

        if not run_name or not isinstance(run_data, list):
            return JsonResponse({"status": "error", "message": "Invalid data format"}, status=400)
        
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(results_dir, exist_ok=True)

        # Sanitize filename
        s_run_name = re.sub(r'[^\w\s-]', '', run_name).strip()
        s_run_name = re.sub(r'[-\s]+', '_', s_run_name)
        save_filename = os.path.join(results_dir, f"{s_run_name}.jsonl")

        with open(save_filename, 'w') as f_out:
            for result in run_data:
                f_out.write(json.dumps(result) + '\n')
        
        return JsonResponse({"status": "ok", "filename": os.path.basename(save_filename)})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
@admin_required
@require_http_methods(["DELETE"])
def delete_run(request, filename):
    try:
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        # Security: prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return JsonResponse({'status': 'error', 'message': 'Invalid filename'}, status=400)
        
        file_path = os.path.join(results_dir, filename)

        if os.path.exists(file_path):
            os.remove(file_path)
            return JsonResponse({"status": "ok", "filename": filename})
        else:
            return JsonResponse({"status": "error", "message": "File not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
