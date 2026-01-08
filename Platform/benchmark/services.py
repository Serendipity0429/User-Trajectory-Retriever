import json
from core.utils import redis_client, print_debug
from .models import MultiTurnTrial
from .utils import RedisKeys, clear_trial_cache


class TrialService:
    @staticmethod
    def get_trace_data(trial_id, cursor=0):
        """
        Retrieve the real-time execution trace data.
        Optimized: Checks Redis for completion status first to avoid DB I/O loop.
        Includes validation to detect and clear stale Redis cache from reused trial IDs.
        """
        trace_key = RedisKeys.trial_trace(trial_id)
        status_key = RedisKeys.trial_status(trial_id)

        try:
            # 1. Try Fetching Cached Status from Redis (Fastest)
            cached_status = redis_client.get(status_key)
            trial_data = None
            use_redis_trace = True

            if cached_status:
                trial_data = json.loads(cached_status)

                # VALIDATION: Check if Redis status matches DB status to detect stale cache
                # This handles edge cases where clear_trial_cache wasn't called (e.g., direct DB insert)
                try:
                    db_trial = MultiTurnTrial.objects.get(pk=trial_id)
                    # If Redis says 'completed' but DB says 'processing', cache is stale
                    if trial_data.get("status") == "completed" and db_trial.status == "processing":
                        print_debug(f"Stale Redis cache detected for trial {trial_id}, clearing")
                        clear_trial_cache(trial_id)
                        use_redis_trace = False
                        trial_data = {
                            "id": db_trial.id,
                            "status": db_trial.status,
                            "answer": db_trial.answer,
                            "feedback": db_trial.feedback,
                            "is_correct": db_trial.is_correct_llm,
                            "is_correct_llm": db_trial.is_correct_llm,
                            "is_correct_rule": db_trial.is_correct_rule,
                            "full_response": db_trial.full_response if db_trial.status != 'processing' else None
                        }
                except MultiTurnTrial.DoesNotExist:
                    # Trial doesn't exist in DB but has Redis data - stale cache
                    print_debug(f"Trial {trial_id} not found in DB but has Redis data, clearing stale cache")
                    clear_trial_cache(trial_id)
                    trial_data = {"status": "error", "error": "Trial not found"}
                    use_redis_trace = False
            else:
                # 2. Fallback: Fetch Status/Results from DB (Slower, but necessary if not in Redis)
                try:
                    trial = MultiTurnTrial.objects.get(pk=trial_id)
                    trial_data = {
                        "id": trial.id,
                        "status": trial.status,
                        "answer": trial.answer,
                        "feedback": trial.feedback,
                        "is_correct": trial.is_correct_llm,
                        "is_correct_llm": trial.is_correct_llm,
                        "is_correct_rule": trial.is_correct_rule,
                        "full_response": trial.full_response if trial.status != 'processing' else None
                    }
                except MultiTurnTrial.DoesNotExist:
                    trial_data = {"status": "error", "error": "Trial not found"}

            # 3. Fetch Trace from Redis (only if not invalidated)
            response_data = {"trial": trial_data, "trace": [], "total_steps": 0}

            if use_redis_trace:
                trace_json = redis_client.get(trace_key)
                if trace_json:
                    full_trace = json.loads(trace_json)
                    response_data["total_steps"] = len(full_trace)

                    if cursor > 0:
                        if cursor < len(full_trace):
                            response_data["trace"] = full_trace[cursor:]
                    else:
                        response_data["trace"] = full_trace

            return response_data

        except Exception as e:
            print_debug(f"Error retrieving trace: {e}")
            return {"trace": [], "total_steps": 0, "error": str(e)}
