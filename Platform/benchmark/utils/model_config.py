"""
Model detection for thinking/reasoning models.
"""

# Models that use <think> tags in response content (DeepSeek, Qwen, etc.)
THINK_TAG_MODELS = ['qwen3', 'deepseek-r1']

# OpenAI reasoning models that use Responses API with reasoning.summary
# These models don't expose raw reasoning tokens, only summaries
# Includes o-series and gpt-5.x series
OPENAI_REASONING_MODELS = ['o1', 'o3', 'o4', 'gpt-5']


def has_builtin_thinking(model_name: str) -> bool:
    """Check if model has built-in reasoning/thinking capabilities.

    Returns True for:
    - Models that use <think> tags (Qwen, DeepSeek)
    - OpenAI reasoning models (o1, o3, gpt-5.x) that think internally

    Used to skip explicit CoT instructions in prompts.
    """
    model_lower = (model_name or '').lower()
    return (any(m in model_lower for m in THINK_TAG_MODELS) or
            any(m in model_lower for m in OPENAI_REASONING_MODELS))


def is_openai_reasoning_model(model_name: str) -> bool:
    """Check if model is an OpenAI reasoning model requiring Responses API."""
    model_lower = (model_name or '').lower()
    return any(m in model_lower for m in OPENAI_REASONING_MODELS)
