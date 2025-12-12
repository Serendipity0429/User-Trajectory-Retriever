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