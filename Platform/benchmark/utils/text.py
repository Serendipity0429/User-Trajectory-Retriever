"""
Text processing utilities for LLM responses.
"""

import re
from core.utils import print_debug


def count_questions_in_file(file_path):
    """Count non-empty lines in a file."""
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

    text = re.sub(r'(?s)<think>.*?</think>', '', text).strip()
    pattern = r"(?i)(\*\*|#+\s*)?(Final Answer|Answer)(\*\*)?:?"

    matches = list(re.finditer(pattern, text))
    if matches:
        last_match = matches[-1]
        return text[last_match.end():].lower().strip()
    else:
        return text.lower().strip()


def extract_query(text):
    """
    Extracts the query from an LLM response.
    1. Handles <think>...</think> blocks by removing them.
    2. Looks for "Search Query:".
    """
    if not text:
        return ""

    text = re.sub(r'(?s)<think>.*?</think>', '', text).strip()
    pattern = r"(?i)(\*\*|#+\s*)?Query(\*\*)?:?"

    matches = list(re.finditer(pattern, text))
    if matches:
        last_match = matches[-1]
        return text[last_match.end():].strip().strip('"').strip("'")
    else:
        return text.strip().strip('"').strip("'")
