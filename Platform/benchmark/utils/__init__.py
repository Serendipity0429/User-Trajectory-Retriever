"""
Benchmark utilities module.
Consolidates all utility functions and classes for the benchmark app.
"""

# Re-export from submodules for convenient imports
from .redis import RedisKeys, PipelinePrefix
from .config import PipelineConfig
from .trace_formatter import TraceFormatter, SimpleMsg
from .prompts import PROMPTS
from .text import count_questions_in_file, extract_final_answer, extract_query
from .django import (
    handle_api_error,
    handle_async_api_error,
    TrialGuard,
    AsyncTrialGuard,
)
from .search import get_search_engine, WebCrawler
from .agent import VanillaAgentFactory, BrowserAgentFactory

# Re-export print_debug for convenience
from core.utils import print_debug

__all__ = [
    # Redis
    'RedisKeys',
    'PipelinePrefix',
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
    # Django utilities
    'handle_api_error',
    'handle_async_api_error',
    'TrialGuard',
    'AsyncTrialGuard',
    # Search
    'get_search_engine',
    'WebCrawler',
    # Agent
    'VanillaAgentFactory',
    'BrowserAgentFactory',
    # Debug
    'print_debug',
]
