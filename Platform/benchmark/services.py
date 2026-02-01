import json
from core.utils import redis_client, print_debug
from .models import MultiTurnTrial
from .utils import RedisKeys, clear_trial_cache, TraceFormatter, SimpleMsg


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
        db_trial = None  # Track the DB trial for search_results extraction

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
                    db_trial = MultiTurnTrial.objects.get(pk=trial_id)
                    trial_data = {
                        "id": db_trial.id,
                        "status": db_trial.status,
                        "answer": db_trial.answer,
                        "feedback": db_trial.feedback,
                        "is_correct_llm": db_trial.is_correct_llm,
                        "is_correct_rule": db_trial.is_correct_rule,
                        "full_response": db_trial.full_response if db_trial.status != 'processing' else None
                    }
                    # Include error message if trial has error status
                    if db_trial.status == 'error' and db_trial.log:
                        trial_data["error"] = db_trial.log.get('error', 'Unknown error')
                        trial_data["error_type"] = db_trial.log.get('error_type', 'Unknown')
                except MultiTurnTrial.DoesNotExist:
                    trial_data = {"status": "error", "error": "Trial not found"}

            # 3. Fetch Trace
            response_data = {"trial": trial_data, "trace": [], "total_steps": 0}
            full_trace = None

            # Try Redis first if not invalidated
            if use_redis_trace:
                trace_json = redis_client.get(trace_key)
                if trace_json:
                    full_trace = json.loads(trace_json)

            # DATABASE FALLBACK: Redis expired/invalidated or empty, reconstruct from database
            if not full_trace:
                full_trace = TrialService._reconstruct_trace_from_db(trial_id)

            # Apply cursor and return
            if full_trace:
                response_data["total_steps"] = len(full_trace)
                if cursor > 0 and cursor < len(full_trace):
                    response_data["trace"] = full_trace[cursor:]
                else:
                    response_data["trace"] = full_trace

            # 4. Include search_results from trial log for RAG pipelines
            # This provides the full content data that's more reliable than parsing from source tags
            if db_trial and db_trial.log:
                search_results = db_trial.log.get('search_results')
                if search_results:
                    response_data["search_results"] = search_results

            return response_data

        except Exception as e:
            print_debug(f"Error retrieving trace: {e}")
            return {"trace": [], "total_steps": 0, "error": str(e)}

    @staticmethod
    def _reconstruct_trace_from_db(trial_id):
        """
        Reconstructs trace from database when Redis cache expires.

        Priority order:
        1. trial.log['trace'] - Pre-formatted trace saved during error recovery or completion
        2. trial.log['messages'] + trial.log['system_prompt'] - Raw messages to reconstruct
        """
        try:
            trial = MultiTurnTrial.objects.get(pk=trial_id)
            if not trial.log:
                return []

            # PRIORITY 1: Check for pre-saved trace (saved during error recovery by AsyncTrialGuard)
            saved_trace = trial.log.get('trace')
            if saved_trace and isinstance(saved_trace, list) and len(saved_trace) > 0:
                print_debug(f"Using pre-saved trace for trial {trial_id} ({len(saved_trace)} steps)")
                return saved_trace

            # PRIORITY 2: Reconstruct from raw messages
            messages = trial.log.get('messages', [])
            if not messages:
                return []

            # Try to get system prompt from stored value or first message
            system_prompt = trial.log.get('system_prompt')
            if not system_prompt and messages and isinstance(messages[0], dict):
                if messages[0].get('role') == 'system':
                    system_prompt = messages[0].get('content', '')

            # Convert messages to SimpleMsg objects for TraceFormatter
            simple_msgs = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    simple_msgs.append(SimpleMsg(role, content))

            # Serialize using TraceFormatter
            trace_data, _ = TraceFormatter.serialize(simple_msgs)

            # Ensure system prompt is at the top of trace (if we have one and it's not already there)
            if system_prompt and (not trace_data or trace_data[0].get('role') != 'system'):
                system_prompt_step = {"role": "system", "content": system_prompt, "step_type": "text"}
                trace_data = [system_prompt_step] + trace_data

            return trace_data

        except MultiTurnTrial.DoesNotExist:
            print_debug(f"Trial {trial_id} not found for trace reconstruction")
            return []
        except Exception as e:
            print_debug(f"Error reconstructing trace from DB: {e}")
            return []
