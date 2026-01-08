"""
Configuration dataclasses for the benchmark module.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PipelineConfig:
    """
    Configuration object for pipeline initialization.
    Replaces the 7-parameter constructor pattern across all pipelines.
    """
    base_url: str
    api_key: str
    model: str
    max_retries: int
    pipeline_id: Optional[int] = None
    dataset_id: Optional[int] = None
    group_id: Optional[int] = None
