"""
Django-specific utilities: decorators, context managers with ORM integration.
"""

import json
import asyncio
from functools import wraps
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from core.utils import print_debug
from .redis import RedisKeys


def handle_api_error(view_func):
    """Decorator to handle exceptions in API views and return JSON error response."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            print_debug(f"Error in {view_func.__name__}: {e}")
            return JsonResponse({"status": "error", "message": str(e), "error": str(e)}, status=500)
    return _wrapped_view


def handle_async_api_error(view_func):
    """Decorator to handle exceptions in Async API views."""
    @wraps(view_func)
    async def _wrapped_view(request, *args, **kwargs):
        try:
            return await view_func(request, *args, **kwargs)
        except Exception as e:
            print_debug(f"Error in {view_func.__name__}: {e}")
            return JsonResponse({"status": "error", "message": str(e), "error": str(e)}, status=500)
    return _wrapped_view


class TrialGuard:
    """
    Context manager to handle trial errors and update Redis status (Sync).
    Updates Django model and Redis cache on exception.
    """
    def __init__(self, trial):
        self.trial = trial

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            partial_trace = []
            try:
                from task_manager.utils import redis_client
                trace_json = redis_client.get(RedisKeys.trial_trace(self.trial.id))
                if trace_json:
                    partial_trace = json.loads(trace_json)
            except Exception:
                pass

            self.trial.status = 'error'
            self.trial.log = self.trial.log or {}
            if partial_trace:
                self.trial.log["trace"] = partial_trace
            self.trial.save()

            try:
                from task_manager.utils import redis_client
                redis_client.set(
                    RedisKeys.trial_status(self.trial.id),
                    json.dumps({"status": "error", "error": str(exc_val)}),
                    ex=RedisKeys.DEFAULT_TTL
                )
            except Exception as e:
                print_debug(f"TrialGuard Error: {e}")
            return False


class AsyncTrialGuard:
    """
    Context manager to handle trial errors and update Redis status (Async).
    Updates Django model and Redis cache on exception.
    """
    def __init__(self, trial):
        self.trial = trial

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            partial_trace = []
            try:
                from task_manager.utils import redis_client
                trace_json = await asyncio.to_thread(
                    redis_client.get, RedisKeys.trial_trace(self.trial.id)
                )
                if trace_json:
                    partial_trace = json.loads(trace_json)
            except Exception:
                pass

            self.trial.status = 'error'
            if not self.trial.log:
                self.trial.log = {}
            if partial_trace:
                self.trial.log["trace"] = partial_trace
            await sync_to_async(self.trial.save)()

            try:
                from task_manager.utils import redis_client
                await asyncio.to_thread(
                    redis_client.set,
                    RedisKeys.trial_status(self.trial.id),
                    json.dumps({"status": "error", "error": str(exc_val)}),
                    RedisKeys.DEFAULT_TTL
                )
            except Exception as e:
                print_debug(f"AsyncTrialGuard Error: {e}")
            return False
