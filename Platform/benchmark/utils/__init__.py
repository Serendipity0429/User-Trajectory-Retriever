"""
Benchmark utilities module.
Consolidates all utility functions and classes for the benchmark app.
"""

# Re-export from submodules for convenient imports
from .redis import RedisKeys, PipelinePrefix, clear_trial_cache
from .config import PipelineConfig
from .trace_formatter import TraceFormatter, SimpleMsg
from .prompts import PROMPTS
from .text import count_questions_in_file, extract_final_answer, extract_query, ensure_system_prompt
from .django import (
    handle_api_error,
    handle_async_api_error,
    TrialGuard,
    AsyncTrialGuard,
    get_session_settings,
)
from .search import get_search_engine, WebCrawler
from .agent import VanillaAgentFactory, BrowserAgentFactory
from .metadata import (
    get_pipeline_category,
    is_rag_pipeline,
    is_agent_pipeline,
    is_vanilla_pipeline,
    format_trial_for_export,
    format_session_for_export,
    format_trial_metadata,
    apply_trial_metadata,
)

# Re-export print_debug for convenience
from core.utils import print_debug

__all__ = [
    # Redis
    'RedisKeys',
    'PipelinePrefix',
    'clear_trial_cache',
    # Config
    'PipelineConfig',
    # Trace
    'TraceFormatter',
    'SimpleMsg',
    # Prompts
    'PROMPTS',
    # Text processing
    'count_questions_in_file',
    'extract_final_answer',
    'extract_query',
    'ensure_system_prompt',
    # Django utilities
    'handle_api_error',
    'handle_async_api_error',
    'TrialGuard',
    'AsyncTrialGuard',
    'get_session_settings',
    # Search
    'get_search_engine',
    'WebCrawler',
    # Agent
    'VanillaAgentFactory',
    'BrowserAgentFactory',
    # Metadata
    'get_pipeline_category',
    'is_rag_pipeline',
    'is_agent_pipeline',
    'is_vanilla_pipeline',
    'format_trial_for_export',
    'format_session_for_export',
    'format_trial_metadata',
    'apply_trial_metadata',
    # Debug
    'print_debug',
]
