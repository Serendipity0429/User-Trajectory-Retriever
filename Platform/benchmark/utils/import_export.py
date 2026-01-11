"""
Import/Export utilities for benchmark pipeline results.

This module provides:
1. Checksum generation and validation for data integrity
2. Export enhancement with metadata (version, timestamps, checksums)
3. Import validation and execution for sessions and runs

Export format version history:
- v1.0: Initial format with checksum support
"""

import hashlib
import json
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from ..models import BenchmarkSettings, MultiTurnRun, MultiTurnSession, MultiTurnTrial

# Current export format version
EXPORT_VERSION = "1.0"


# ============================================
# Checksum Utilities
# ============================================

def _canonicalize_data(data: Any) -> str:
    """
    Convert data to canonical JSON string for consistent hashing.

    Ensures consistent ordering of keys and formatting for
    reproducible checksums across different Python versions.
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)


def generate_checksum(data: Dict[str, Any], exclude_keys: List[str] = None) -> str:
    """
    Generate SHA-256 checksum for export data.

    Args:
        data: The data dictionary to checksum
        exclude_keys: Keys to exclude from checksum calculation (e.g., 'checksum', 'export_metadata')

    Returns:
        Hex string of SHA-256 hash
    """
    exclude_keys = exclude_keys or ['checksum', 'export_metadata']

    # Create copy without excluded keys
    data_for_hash = {k: v for k, v in data.items() if k not in exclude_keys}

    # Canonicalize and hash
    canonical = _canonicalize_data(data_for_hash)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def validate_checksum(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate checksum of imported data.

    Args:
        data: The imported data dictionary with 'checksum' field in export_metadata

    Returns:
        Tuple of (is_valid, message)
    """
    export_metadata = data.get('export_metadata', {})
    stored_checksum = export_metadata.get('checksum')

    if not stored_checksum:
        return False, "No checksum found in export_metadata"

    calculated_checksum = generate_checksum(data)

    if calculated_checksum != stored_checksum:
        return False, f"Checksum mismatch: expected {stored_checksum[:16]}..., got {calculated_checksum[:16]}..."

    return True, "Checksum valid"


# ============================================
# Export Enhancement
# ============================================

def enhance_export_data(data: Dict[str, Any], export_type: str) -> Dict[str, Any]:
    """
    Enhance export data with metadata and checksum.

    Args:
        data: The original export data
        export_type: Either 'session' or 'run'

    Returns:
        Enhanced data with export_metadata including checksum
    """
    # Generate checksum before adding metadata
    checksum = generate_checksum(data)

    # Add export metadata
    data['export_metadata'] = {
        'version': EXPORT_VERSION,
        'export_type': export_type,
        'exported_at': datetime.now(dt_timezone.utc).isoformat().replace('+00:00', 'Z'),
        'checksum': checksum,
    }

    return data


# ============================================
# Import Validation
# ============================================

class ImportValidationError(Exception):
    """Custom exception for import validation errors."""
    pass


def validate_session_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate session export data structure.

    Args:
        data: The imported session data

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required fields
    required_fields = ['question', 'trials']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate trials structure
    trials = data.get('trials', [])
    if not isinstance(trials, list):
        errors.append("'trials' must be a list")
    else:
        for i, trial in enumerate(trials):
            if not isinstance(trial, dict):
                errors.append(f"Trial {i} must be a dictionary")
                continue

            # Check trial required fields
            if 'trial_number' not in trial:
                errors.append(f"Trial {i} missing 'trial_number'")

    # Validate pipeline_type if present
    valid_pipeline_types = ['vanilla_llm', 'rag', 'vanilla_agent', 'browser_agent']
    pipeline_type = data.get('pipeline_type')
    if pipeline_type and pipeline_type not in valid_pipeline_types:
        errors.append(f"Invalid pipeline_type: {pipeline_type}. Must be one of {valid_pipeline_types}")

    # Validate ground_truths if present
    ground_truths = data.get('ground_truths')
    if ground_truths is not None and not isinstance(ground_truths, list):
        errors.append("'ground_truths' must be a list")

    return len(errors) == 0, errors


def validate_run_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate run export data structure.

    Args:
        data: The imported run data

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required fields
    if 'sessions' not in data:
        errors.append("Missing required field: 'sessions'")
        return False, errors

    sessions = data.get('sessions', [])
    if not isinstance(sessions, list):
        errors.append("'sessions' must be a list")
        return False, errors

    # Validate each session
    for i, session in enumerate(sessions):
        if not isinstance(session, dict):
            errors.append(f"Session {i} must be a dictionary")
            continue

        is_valid, session_errors = validate_session_data(session)
        if not is_valid:
            errors.extend([f"Session {i}: {err}" for err in session_errors])

    return len(errors) == 0, errors


def validate_import_data(data: Dict[str, Any], expected_type: str = None) -> Tuple[bool, List[str]]:
    """
    Comprehensive validation of import data including checksum.

    Args:
        data: The imported data
        expected_type: Expected export type ('session' or 'run'), or None for auto-detect

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check for export metadata
    export_metadata = data.get('export_metadata', {})

    # Validate checksum if present
    if export_metadata.get('checksum'):
        is_valid, msg = validate_checksum(data)
        if not is_valid:
            errors.append(f"Checksum validation failed: {msg}")

    # Check version compatibility
    version = export_metadata.get('version', '0.0')
    major_version = version.split('.')[0] if version else '0'
    current_major = EXPORT_VERSION.split('.')[0]
    if major_version != current_major:
        errors.append(f"Incompatible export version: {version}. Current version: {EXPORT_VERSION}")

    # Auto-detect export type if not specified
    export_type = expected_type or export_metadata.get('export_type')
    if not export_type:
        # Auto-detect based on data structure
        if 'sessions' in data:
            export_type = 'run'
        elif 'trials' in data:
            export_type = 'session'
        else:
            errors.append("Cannot determine export type. Expected 'sessions' (for run) or 'trials' (for session)")
            return False, errors

    # Validate based on type
    if export_type == 'session':
        is_valid, type_errors = validate_session_data(data)
    elif export_type == 'run':
        is_valid, type_errors = validate_run_data(data)
    else:
        errors.append(f"Unknown export_type: {export_type}")
        return False, errors

    errors.extend(type_errors)

    return len(errors) == 0, errors


# ============================================
# Import Execution
# ============================================

def _reconstruct_trial_log(trial_data: Dict[str, Any], pipeline_type: str) -> Dict[str, Any]:
    """
    Reconstruct the trial log field from exported data.

    Args:
        trial_data: The trial dictionary from export
        pipeline_type: The pipeline type for proper metadata handling

    Returns:
        Reconstructed log dictionary
    """
    log = {}

    # Reconstruct messages
    if 'messages' in trial_data:
        messages = trial_data['messages']
        # Extract system prompt from first message if present
        if messages and messages[0].get('role') == 'system':
            log['system_prompt'] = messages[0].get('content', '')
            log['messages'] = messages[1:]  # Store messages without system prompt
        else:
            log['messages'] = messages

    # Reconstruct RAG-specific data
    if 'rag' in (pipeline_type or ''):
        if 'search_query' in trial_data:
            log['search_query'] = trial_data['search_query']
        if 'search_results' in trial_data:
            log['search_results'] = trial_data['search_results']

    # Reconstruct agent-specific data
    if 'agent' in (pipeline_type or ''):
        if 'meta' in trial_data:
            log['meta'] = trial_data['meta']

    # Reconstruct token usage
    if 'token_usage' in trial_data:
        log['token_usage'] = trial_data['token_usage']

    return log


def _create_settings_from_snapshot(snapshot: Dict[str, Any]) -> BenchmarkSettings:
    """
    Create BenchmarkSettings from snapshot dictionary.

    Args:
        snapshot: The settings snapshot from export

    Returns:
        New BenchmarkSettings instance (not saved)
    """
    settings = BenchmarkSettings(is_template=False)

    if not snapshot:
        return settings

    # LLM settings
    llm = snapshot.get('llm', {})
    settings.llm_base_url = llm.get('llm_base_url', '')
    settings.llm_model = llm.get('llm_model', '')
    settings.llm_judge_model = llm.get('llm_judge_model', '')
    settings.embedding_model = llm.get('embedding_model', '')
    settings.max_retries = llm.get('max_retries', 5)
    settings.allow_reasoning = llm.get('allow_reasoning', True)
    settings.temperature = llm.get('temperature', 0.0)
    settings.top_p = llm.get('top_p', 1.0)
    settings.max_tokens = llm.get('max_tokens')
    # Note: API keys are intentionally not imported for security

    # Search settings
    search = snapshot.get('search', {})
    settings.search_provider = search.get('search_provider', 'serper')
    settings.search_limit = search.get('search_limit', 5)
    settings.fetch_full_content = search.get('serper_fetch_full_content', True)

    # Agent settings
    agent = snapshot.get('agent', {})
    settings.memory_type = agent.get('memory_type', 'naive')
    settings.agent_max_iters = agent.get('max_iters', 30)

    return settings


@transaction.atomic
def import_session(data: Dict[str, Any], run: MultiTurnRun = None) -> Tuple[MultiTurnSession, Dict[str, Any]]:
    """
    Import a single session from export data.

    Args:
        data: The session export data
        run: Optional existing run to attach to, or None to create new run

    Returns:
        Tuple of (created session, import stats dict)

    Raises:
        ImportValidationError: If validation fails
    """
    # Validate first
    is_valid, errors = validate_import_data(data, expected_type='session')
    if not is_valid:
        raise ImportValidationError(f"Validation failed: {'; '.join(errors)}")

    stats = {
        'trials_imported': 0,
        'run_created': False,
        'settings_created': False,
    }

    # Create or use run
    if run is None:
        settings = None
        if data.get('settings'):
            settings = _create_settings_from_snapshot(data['settings'])
            settings.save()
            stats['settings_created'] = True

        run = MultiTurnRun.objects.create(
            name=f"Imported Session - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            settings=settings,
            is_ad_hoc=True,
        )
        stats['run_created'] = True

    # Create session
    pipeline_type = data.get('pipeline_type', 'vanilla_llm')
    session = MultiTurnSession.objects.create(
        run=run,
        question=data['question'],
        ground_truths=data.get('ground_truths', []),
        is_completed=data.get('is_completed', True),
        pipeline_type=pipeline_type,
    )

    # Create trials
    for trial_data in data.get('trials', []):
        log = _reconstruct_trial_log(trial_data, pipeline_type)

        MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_data['trial_number'],
            answer=trial_data.get('answer', ''),
            feedback=trial_data.get('feedback'),
            is_correct_llm=trial_data.get('is_correct_llm'),
            is_correct_rule=trial_data.get('is_correct_rule'),
            status='completed',
            log=log,
        )
        stats['trials_imported'] += 1

    return session, stats


@transaction.atomic
def import_run(data: Dict[str, Any]) -> Tuple[MultiTurnRun, Dict[str, Any]]:
    """
    Import a complete run with all sessions from export data.

    Args:
        data: The run export data

    Returns:
        Tuple of (created run, import stats dict)

    Raises:
        ImportValidationError: If validation fails
    """
    # Validate first
    is_valid, errors = validate_import_data(data, expected_type='run')
    if not is_valid:
        raise ImportValidationError(f"Validation failed: {'; '.join(errors)}")

    stats = {
        'sessions_imported': 0,
        'trials_imported': 0,
        'settings_created': False,
    }

    # Create settings from snapshot
    settings = None
    if data.get('settings'):
        settings = _create_settings_from_snapshot(data['settings'])
        settings.save()
        stats['settings_created'] = True

    # Create run
    group_name = data.get('group_name', f"Imported Run - {timezone.now().strftime('%Y-%m-%d %H:%M')}")
    run = MultiTurnRun.objects.create(
        name=group_name,
        settings=settings,
        is_ad_hoc=False,
    )

    # Create sessions and trials
    for session_data in data.get('sessions', []):
        pipeline_type = session_data.get('pipeline_type', 'vanilla_llm')

        session = MultiTurnSession.objects.create(
            run=run,
            question=session_data['question'],
            ground_truths=session_data.get('ground_truths', []),
            is_completed=session_data.get('is_completed', True),
            pipeline_type=pipeline_type,
        )
        stats['sessions_imported'] += 1

        # Create trials for this session
        for trial_data in session_data.get('trials', []):
            log = _reconstruct_trial_log(trial_data, pipeline_type)

            MultiTurnTrial.objects.create(
                session=session,
                trial_number=trial_data['trial_number'],
                answer=trial_data.get('answer', ''),
                feedback=trial_data.get('feedback'),
                is_correct_llm=trial_data.get('is_correct_llm'),
                is_correct_rule=trial_data.get('is_correct_rule'),
                status='completed',
                log=log,
            )
            stats['trials_imported'] += 1

    return run, stats


def auto_import(data: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    """
    Auto-detect export type and import accordingly.

    Args:
        data: The export data (either session or run)

    Returns:
        Tuple of (created object, import stats dict)

    Raises:
        ImportValidationError: If validation fails or type cannot be determined
    """
    export_metadata = data.get('export_metadata', {})
    export_type = export_metadata.get('export_type')

    # Auto-detect if not specified
    if not export_type:
        if 'sessions' in data:
            export_type = 'run'
        elif 'trials' in data:
            export_type = 'session'
        else:
            raise ImportValidationError("Cannot determine export type from data structure")

    if export_type == 'session':
        return import_session(data)
    elif export_type == 'run':
        return import_run(data)
    else:
        raise ImportValidationError(f"Unknown export type: {export_type}")
