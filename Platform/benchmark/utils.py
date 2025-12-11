import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def print_debug(*args, **kwargs):
    if settings.DEBUG:
        message = " ".join(map(str, args)) + " ".join(
            f"{k}={v}" for k, v in kwargs.items()
        )
        logger.info(message)

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
    Robustly extracts the final answer from an LLM response.
    It looks for 'Final Answer:' (case-insensitive, optional bolding) and returns the text following it.
    If the marker is not found, it returns the last non-empty line.
    """
    if not text:
        return ""
        
    # Regex to match 'Final Answer' with optional markdown (** or __), optional colon, case insensitive
    # Matches: "Final Answer:", "**Final Answer**:", "Final Answer", "Final answer :"
    pattern = r"(?:\*\*|__)?Final\s+Answer(?:\*\*|__)?\s*:?\s*"
    
    # split by the pattern
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    
    if len(parts) > 1:
        # Return the last part, stripped of whitespace
        return parts[-1].strip()
    else:
        # Fallback: return the last non-empty line
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            return lines[-1]
        return text.strip()