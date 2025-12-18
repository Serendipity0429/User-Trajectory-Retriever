import json
from core.utils import redis_client, print_debug
from .models import MultiTurnTrial

class TrialService:
    @staticmethod
    def get_trace_data(trial_id, cursor=0):
        """
        Retrieve the real-time execution trace data.
        Optimized: Checks Redis for completion status first to avoid DB I/O loop.
        """
        trace_key = f"trial_trace:{trial_id}"
        status_key = f"trial_status:{trial_id}"
        
        try:
            # 1. Try Fetching Cached Status from Redis (Fastest)
            cached_status = redis_client.get(status_key)
            
            if cached_status:
                trial_data = json.loads(cached_status)
            else:
                # 2. Fallback: Fetch Status/Results from DB (Slower, but necessary if not in Redis)
                try:
                    trial = MultiTurnTrial.objects.get(pk=trial_id)
                    trial_data = {
                        "id": trial.id,
                        "status": trial.status,
                        "answer": trial.answer,
                        "feedback": trial.feedback,
                        "is_correct": trial.is_correct,
                        "full_response": trial.full_response if trial.status != 'processing' else None
                    }
                except MultiTurnTrial.DoesNotExist:
                    trial_data = {"status": "error", "error": "Trial not found"}

            # 3. Fetch Trace from Redis
            trace_json = redis_client.get(trace_key)
            
            response_data = {"trial": trial_data, "trace": [], "total_steps": 0}

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
