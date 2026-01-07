import logging
import re
from functools import wraps
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handle_api_error(view_func):
    """
    Decorator to handle exceptions in API views and return a JSON error response.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            print_debug(f"Error in {view_func.__name__}: {e}")
            return JsonResponse({"status": "error", "message": str(e), "error": str(e)}, status=500)
    return _wrapped_view


def handle_async_api_error(view_func):
    """
    Decorator to handle exceptions in Async API views.
    """
    @wraps(view_func)
    async def _wrapped_view(request, *args, **kwargs):
        try:
            return await view_func(request, *args, **kwargs)
        except Exception as e:
            print_debug(f"Error in {view_func.__name__}: {e}")
            return JsonResponse({"status": "error", "message": str(e), "error": str(e)}, status=500)
    return _wrapped_view


from core.utils import print_debug





def count_questions_in_file(file_path):



    count = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception as e:
        print_debug(f"Error counting lines in {file_path}: {e}")
        return 0
    return count

def extract_final_answer(text):
    """
    Extracts the final answer from an LLM response.
    1. Handles <think>...</think> blocks by removing them.
    2. Looks for "Final Answer:".
    Robust to case and Markdown formatting.
    """
    if not text:
        return ""
        
    # Remove <think> blocks if present
    text = re.sub(r'(?s)<think>.*?</think>', '', text).strip()
        
    # Regex to find "Final Answer" with optional bolding/casing and optional colon
    pattern = r"(?i)(\*\*|#+\s*)?(Final Answer|Answer)(\*\*)?:?"
    
    # We want to find the LAST occurrence of this pattern to avoid false positives
    matches = list(re.finditer(pattern, text))
    if matches:
        last_match = matches[-1]
        return text[last_match.end():].lower().strip()
    else:
        # If no "Final Answer" marker found but there was a think block, 
        # the remaining text IS likely the answer.
        return text.lower().strip()

def extract_query(text):
    """
    Extracts the query from an LLM response.
    1. Handles <think>...</think> blocks by removing them.
    2. Looks for "Query:".
    """
    if not text:
        return ""
        
    # Remove <think> blocks if present
    text = re.sub(r'(?s)<think>.*?</think>', '', text).strip()
        
    pattern = r"(?i)(\*\*|#+\s*)?Query(\*\*)?:?"
    
    matches = list(re.finditer(pattern, text))
    if matches:
        last_match = matches[-1]
        return text[last_match.end():].strip().strip('"').strip("'")
    else:
        # If no "Query" marker found but there was a think block,
        # the remaining text IS likely the query.
        return text.strip().strip('"').strip("'")

import json
from asgiref.sync import sync_to_async
import asyncio

class TrialGuard:
    """
    Context manager to handle trial errors and update Redis status (Sync).
    """
    def __init__(self, trial):
        self.trial = trial

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # 1. Fetch Partial Trace from Redis
            partial_trace = []
            try:
                from task_manager.utils import redis_client
                trace_json = redis_client.get(f"trial_trace:{self.trial.id}")
                if trace_json:
                    partial_trace = json.loads(trace_json)
            except Exception:
                pass

            # 2. Update DB Status and Log
            self.trial.status = 'error'
            self.trial.log = self.trial.log or {}
            if partial_trace:
                self.trial.log["trace"] = partial_trace
            self.trial.save()
            
            # 3. Update Redis Status
            try:
                from task_manager.utils import redis_client
                redis_client.set(
                    f"trial_status:{self.trial.id}", 
                    json.dumps({"status": "error", "error": str(exc_val)}), 
                    ex=3600
                )
            except Exception as e:
                print_debug(f"TrialGuard Error: {e}")
            # Propagate exception
            return False

class AsyncTrialGuard:
    """
    Context manager to handle trial errors and update Redis status (Async).
    """
    def __init__(self, trial):
        self.trial = trial

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # 1. Fetch Partial Trace from Redis
            partial_trace = []
            try:
                from task_manager.utils import redis_client
                import asyncio
                trace_json = await asyncio.to_thread(redis_client.get, f"trial_trace:{self.trial.id}")
                if trace_json:
                    partial_trace = json.loads(trace_json)
            except Exception:
                pass

            # 2. Update DB Status and Log
            self.trial.status = 'error'
            if not self.trial.log:
                self.trial.log = {}
            if partial_trace:
                self.trial.log["trace"] = partial_trace
            await sync_to_async(self.trial.save)()
            
            # 3. Update Redis Status
            try:
                from task_manager.utils import redis_client
                await asyncio.to_thread(
                    redis_client.set,
                    f"trial_status:{self.trial.id}", 
                    json.dumps({"status": "error", "error": str(exc_val)}), 
                    ex=3600
                )
            except Exception as e:
                print_debug(f"AsyncTrialGuard Error: {e}")
            return False