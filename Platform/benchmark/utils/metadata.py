"""
Metadata formatting utilities for benchmark trial exports.

This module provides:
1. Pipeline type helpers (is_rag_pipeline, is_agent_pipeline, etc.)
2. Trial formatting for export (format_trial_for_export, apply_trial_metadata)
3. Session formatting for export (format_session_for_export)

Note: Metric calculations are in metrics.py (single source of truth).
"""

from typing import List, Dict, Any, Optional


# ============================================
# Pipeline Type Helpers
# ============================================

def get_pipeline_category(pipeline_type: str) -> str:
    """
    Determine the category of a pipeline type.

    Args:
        pipeline_type: The pipeline type string

    Returns:
        One of: 'rag', 'agent', 'vanilla', 'unknown'
    """
    pipeline_type = pipeline_type or ''
    if 'rag' in pipeline_type:
        return 'rag'
    elif 'agent' in pipeline_type:
        return 'agent'
    elif 'vanilla' in pipeline_type:
        return 'vanilla'
    return 'unknown'


def is_rag_pipeline(pipeline_type: str) -> bool:
    """Check if pipeline type is RAG-based."""
    return 'rag' in (pipeline_type or '')


def is_agent_pipeline(pipeline_type: str) -> bool:
    """Check if pipeline type is agent-based."""
    return 'agent' in (pipeline_type or '')


def is_vanilla_pipeline(pipeline_type: str) -> bool:
    """Check if pipeline type is vanilla LLM."""
    return 'vanilla' in (pipeline_type or '') and 'agent' not in (pipeline_type or '')


# ============================================
# Trial Formatting Helpers
# ============================================

def format_trial_for_export(trial: dict, log: dict, pipeline_type: str, include_system_prompt: bool = True) -> dict:
    """
    Format a trial dictionary for export, extracting and organizing all relevant data.

    Args:
        trial: The raw trial dictionary from DB query
        log: The trial log dictionary (extracted from trial)
        pipeline_type: The pipeline type string
        include_system_prompt: Whether to prepend system prompt to messages

    Returns:
        Formatted trial dict with messages and pipeline-specific metadata
    """
    # Handle created_at conversion if it's a datetime object
    created_at = trial.get('created_at')
    if created_at and hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()

    # Get messages, optionally with system prompt prepended
    messages = log.get('messages', [])
    if include_system_prompt:
        messages = _ensure_system_prompt_in_messages(messages, log.get('system_prompt'))

    formatted = {
        'trial_number': trial.get('trial_number'),
        'answer': trial.get('answer'),
        'feedback': trial.get('feedback'),
        'is_correct_llm': trial.get('is_correct_llm'),
        'is_correct_rule': trial.get('is_correct_rule'),
        'created_at': created_at,
        'messages': messages,
    }

    # Add pipeline-specific metadata
    apply_trial_metadata(formatted, log, pipeline_type)

    return formatted


def _ensure_system_prompt_in_messages(messages: list, system_prompt: str) -> list:
    """
    Ensure system prompt is prepended to messages if not already present.

    Args:
        messages: List of message dicts
        system_prompt: The system prompt string

    Returns:
        Messages with system prompt at the beginning if applicable
    """
    if not system_prompt or not messages:
        return messages

    # Check if first message is already a system message
    if messages and messages[0].get('role') == 'system':
        return messages

    # Prepend system prompt
    return [{'role': 'system', 'content': system_prompt}] + list(messages)


def format_trials_for_export(trials_qs, pipeline_type: str) -> List[dict]:
    """
    Format multiple trials for export.

    Args:
        trials_qs: QuerySet or list of trial dicts with 'log' field
        pipeline_type: The pipeline type string

    Returns:
        List of formatted trial dicts
    """
    formatted_trials = []
    for trial in trials_qs:
        log = trial.pop('log', {}) or {}
        formatted = format_trial_for_export(trial, log, pipeline_type)
        formatted_trials.append(formatted)
    return formatted_trials


def format_session_for_export(session, trials: list, settings_snapshot: dict) -> dict:
    """
    Format a session dictionary for export.

    Args:
        session: The MultiTurnSession model instance
        trials: List of formatted trial dictionaries
        settings_snapshot: The settings snapshot dict

    Returns:
        Formatted session dict for export
    """
    return {
        'session_id': session.id,
        'question': session.question,
        'ground_truths': session.ground_truths,
        'is_completed': session.is_completed,
        'pipeline_type': session.pipeline_type,
        'created_at': session.created_at.isoformat() if session.created_at else None,
        'settings': settings_snapshot,
        'trials': trials,
    }


# ============================================
# Pipeline-Specific Metadata Formatters
# ============================================

def format_rag_metadata(log: dict) -> dict:
    """
    Extract and format metadata for RAG pipeline trials.

    Args:
        log: The trial log dictionary

    Returns:
        dict with RAG-specific fields: search_results, search_query
    """
    meta = {}
    if log.get("search_results"):
        meta["search_results"] = log.get("search_results", [])
    if log.get("search_query"):
        meta["search_query"] = log.get("search_query")
    return meta


def format_agent_metadata(log: dict) -> dict:
    """
    Extract and format metadata for agent pipeline trials.

    Args:
        log: The trial log dictionary

    Returns:
        dict with agent-specific fields from log['meta']:
        - memory_type: Type of long-term memory used
        - memory_retrieved: Content retrieved from long-term memory
        - memory_recorded: Observations recorded to long-term memory
    """
    meta = {}
    if log.get("meta"):
        meta = log.get("meta", {})
    return meta


def format_vanilla_metadata(log: dict) -> dict:
    """
    Extract and format metadata for vanilla LLM pipeline trials.

    Args:
        log: The trial log dictionary

    Returns:
        dict (currently empty for vanilla pipelines)
    """
    return {}


def format_token_usage(log: dict) -> dict:
    """
    Extract and format token usage metadata from trial log.

    Args:
        log: The trial log dictionary

    Returns:
        dict with token usage fields if available:
        - input_tokens: Number of prompt tokens
        - output_tokens: Number of completion tokens
        - total_tokens: Total tokens used
        - call_count: Number of LLM calls in this trial
    """
    usage = log.get("token_usage", {})
    if not usage:
        return {}

    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "call_count": usage.get("call_count", 0),
    }


def format_trial_metadata(log: dict, pipeline_type: str) -> dict:
    """
    Router function to format trial metadata based on pipeline type.

    Args:
        log: The trial log dictionary
        pipeline_type: The pipeline type string (e.g., 'rag', 'vanilla_agent', 'browser_agent')

    Returns:
        dict with pipeline-specific metadata fields
    """
    if not log:
        return {}

    pipeline_type = pipeline_type or ''

    # Route to appropriate formatter based on pipeline type
    if 'rag' in pipeline_type:
        return format_rag_metadata(log)
    elif 'agent' in pipeline_type:
        return format_agent_metadata(log)
    elif 'vanilla' in pipeline_type:
        return format_vanilla_metadata(log)
    else:
        # Unknown pipeline type - return empty metadata
        return {}


def apply_trial_metadata(trial: dict, log: dict, pipeline_type: str) -> None:
    """
    Apply formatted metadata to a trial dictionary in-place.

    This is a convenience function that formats metadata and merges it
    into the trial dict, handling the common pattern of:
    1. Format metadata based on pipeline type
    2. Only add non-empty metadata to trial
    3. Add token usage for all pipeline types

    Args:
        trial: The trial dictionary to modify (in-place)
        log: The trial log dictionary
        pipeline_type: The pipeline type string
    """
    metadata = format_trial_metadata(log, pipeline_type)

    # For RAG, add search fields directly to trial
    if 'rag' in (pipeline_type or ''):
        if 'search_results' in metadata:
            trial['search_results'] = metadata['search_results']
        if 'search_query' in metadata:
            trial['search_query'] = metadata['search_query']
    # For agents, add meta dict if present
    elif 'agent' in (pipeline_type or ''):
        if metadata:
            trial['meta'] = metadata

    # Add token usage for all pipeline types
    token_usage = format_token_usage(log)
    if token_usage:
        trial['token_usage'] = token_usage


