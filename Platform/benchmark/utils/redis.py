"""
Centralized Redis key management for the benchmark module.
All Redis keys should be generated through these classes to ensure consistency.
"""


class RedisKeys:
    """
    Static methods for generating Redis keys.
    Ensures consistent key naming across the entire benchmark module.
    """
    # Default TTL for Redis keys (1 hour)
    DEFAULT_TTL = 3600

    # Trial keys
    @staticmethod
    def trial_trace(trial_id: int) -> str:
        """Key for storing trial execution trace."""
        return f"trial_trace:{trial_id}"

    @staticmethod
    def trial_status(trial_id: int) -> str:
        """Key for storing trial status and results."""
        return f"trial_status:{trial_id}"

    # Pipeline active keys
    @staticmethod
    def pipeline_active(prefix: str, pipeline_id: int) -> str:
        """Key for tracking active pipeline status."""
        return f"{prefix}:{pipeline_id}"

    # Session history key (for RAG pipeline)
    @staticmethod
    def session_history(prefix: str, session_id: int) -> str:
        """Key for storing RAG conversation history."""
        return f"{prefix}:history:{session_id}"


class PipelinePrefix:
    """Constants for pipeline Redis prefixes."""
    ACTIVE = "pipeline_active"
    MULTI_TURN = "multi_turn_pipeline_active"
    VANILLA = "vanilla_llm_pipeline_active"
    RAG = "rag_pipeline_active"
    VANILLA_AGENT = "vanilla_agent_pipeline_active"
    BROWSER_AGENT = "browser_agent_pipeline_active"


def clear_trial_cache(trial_id: int) -> None:
    """
    Clear any stale Redis cache for a trial ID.

    This should be called after creating a new trial to ensure no stale data
    from a potentially reused trial ID (e.g., after database reset) is served.
    """
    from core.utils import redis_client
    try:
        redis_client.delete(RedisKeys.trial_trace(trial_id))
        redis_client.delete(RedisKeys.trial_status(trial_id))
    except Exception:
        # Silently ignore Redis errors during cleanup
        pass
