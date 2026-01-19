"""
Model detection for thinking/reasoning models.
"""

# Models with built-in thinking/reasoning capabilities
THINKING_MODELS = ['qwen3', 'deepseek-r1', 'o1']

def has_builtin_thinking(model_name: str) -> bool:
    """Check if model has built-in thinking capabilities."""
    model_lower = (model_name or '').lower()
    return any(m in model_lower for m in THINKING_MODELS)
