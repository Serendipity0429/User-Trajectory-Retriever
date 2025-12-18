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
    Strictly extracts the final answer from an LLM response by looking for "Final Answer:".
    If the marker is not found, it returns an empty string, indicating parsing failure.
    """
    if not text:
        return ""
        
    # Strictly look for "Final Answer:"
    marker = "Final Answer:"
    
    if marker in text:
        # Return the text after the marker, stripped of leading/trailing whitespace
        # Splitting by marker and taking the last part allows for robustness if "Final Answer:" appears multiple times (unlikely but safe)
        return text.split(marker)[-1].strip()
    else:
        # If the marker is not found, return an empty string
        return text