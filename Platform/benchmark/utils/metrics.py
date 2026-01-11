"""
Metrics calculation module for benchmark results.

This module is the single source of truth for all metric calculations:
1. Per-Session Extraction: Extract metrics from trials within a session
2. Cross-Session Aggregation: Aggregate metrics across multiple sessions

Architecture:
- extract_session_metrics(session) → Dict with per-session metrics
- calculate_aggregate_metrics(results) → Dict with aggregated metrics for display

Each metric has its own calculation function for better maintainability.
Groups and priorities are defined here to ensure frontend consistency.
"""

import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher


# ==========================================
# Color Mapping System (Continuous HSL)
# ==========================================

# Fixed colors for semantic metrics (success/failure/error)
FIXED_COLORS = {
    "correct_count": {"name": "emerald", "border": "#059669", "text": "#047857", "bg": "#ecfdf5"},
    "incorrect_count": {"name": "rose", "border": "#e11d48", "text": "#be123c", "bg": "#fff1f2"},
    "error_count": {"name": "amber", "border": "#d97706", "text": "#b45309", "bg": "#fffbeb"},
}


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple:
    """
    Convert HSL to RGB.
    h: 0-360, s: 0-1, l: 0-1
    Returns: (r, g, b) each 0-255
    """
    h = h / 360.0
    if s == 0:
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

    return (int(r * 255), int(g * 255), int(b * 255))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def _generate_color_from_hash(metric_name: str, saturation: float, lightness: float) -> str:
    """
    Generate a color from metric name using continuous HSL space.

    Uses MD5 hash to map the metric name to a hue value (0-360),
    then converts to RGB with given saturation and lightness.
    """
    hash_value = int(hashlib.md5(metric_name.encode()).hexdigest(), 16)
    # Map hash to hue (0-360)
    hue = hash_value % 360
    r, g, b = _hsl_to_rgb(hue, saturation, lightness)
    return _rgb_to_hex(r, g, b)


def get_metric_color(metric_name: str) -> Dict[str, str]:
    """
    Generate a consistent color for a metric based on its name.

    Uses continuous HSL color space mapping:
    - Hue: derived from hash of metric name (0-360)
    - Saturation: moderate (0.55) for border, darker for text
    - Lightness: varies for different use cases

    Color constraints:
    - Not too light (text must be readable)
    - Not too vivid (professional appearance)
    """
    # Check for fixed semantic colors first
    if metric_name in FIXED_COLORS:
        return FIXED_COLORS[metric_name]

    # Generate colors using continuous HSL mapping
    hash_value = int(hashlib.md5(metric_name.encode()).hexdigest(), 16)
    hue = hash_value % 360

    # Border color: moderate saturation, medium lightness
    border = _rgb_to_hex(*_hsl_to_rgb(hue, 0.55, 0.45))

    # Text color: same hue, darker for readability
    text = _rgb_to_hex(*_hsl_to_rgb(hue, 0.50, 0.30))

    # Background color: same hue, very light and low saturation
    bg = _rgb_to_hex(*_hsl_to_rgb(hue, 0.30, 0.96))

    # Generate a name from the hue for reference
    hue_names = [
        "red", "orange", "yellow", "lime", "green", "teal",
        "cyan", "sky", "blue", "indigo", "violet", "pink"
    ]
    name_index = int(hue / 30) % 12
    name = hue_names[name_index]

    return {
        "name": name,
        "border": border,
        "text": text,
        "bg": bg,
        "hue": hue,  # Include hue for debugging/reference
    }


# ==========================================
# Pipeline -> Metric Groups Mapping
# ==========================================

PIPELINE_METRIC_GROUPS: Dict[str, List[str]] = {
    "vanilla_llm": ["core", "outcome", "efficiency", "behavioral", "dynamics", "token_usage"],
    "rag": ["core", "outcome", "efficiency", "behavioral", "search", "dynamics", "token_usage"],
    "vanilla_agent": ["core", "outcome", "efficiency", "behavioral", "search", "dynamics", "token_usage"],
    "browser_agent": ["core", "outcome", "efficiency", "behavioral", "search", "dynamics", "token_usage"],
}


# ==========================================
# Metric & Group Definitions
# ==========================================

@dataclass
class MetricGroup:
    """Definition of a metric group with display properties and priority."""
    key: str
    label: str
    priority: int  # Lower number = higher priority (displayed first)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "priority": self.priority,
            "description": self.description,
        }


@dataclass
class MetricDefinition:
    """Definition of a metric including display properties and group assignment."""
    key: str
    label: str
    description: str
    group: str  # Key of the MetricGroup this metric belongs to
    format_type: str = "percentage"  # percentage, number, count
    precision: int = 2
    prefix: str = ""
    is_conditional: bool = False  # If True, metric may not always be present
    priority: int = 0  # Priority within group (lower = higher priority)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "group": self.group,
            "format_type": self.format_type,
            "precision": self.precision,
            "prefix": self.prefix,
            "is_conditional": self.is_conditional,
            "priority": self.priority,
        }


# ==========================================
# Group Definitions (ordered by priority)
# ==========================================

METRIC_GROUPS: Dict[str, MetricGroup] = {
    "core": MetricGroup(
        key="core",
        label="Core Performance",
        priority=1,
        description="Primary accuracy and agreement metrics"
    ),
    "outcome": MetricGroup(
        key="outcome",
        label="Outcome Distribution",
        priority=2,
        description="Session outcome counts"
    ),
    "efficiency": MetricGroup(
        key="efficiency",
        label="Efficiency",
        priority=3,
        description="Trial efficiency metrics"
    ),
    "behavioral": MetricGroup(
        key="behavioral",
        label="Behavioral Analysis",
        priority=4,
        description="Multi-turn behavior patterns"
    ),
    "search": MetricGroup(
        key="search",
        label="Search & Retrieval",
        priority=5,
        description="RAG and Agent search metrics"
    ),
    "dynamics": MetricGroup(
        key="dynamics",
        label="Multi-Turn Dynamics",
        priority=6,
        description="Answer stability and recovery patterns"
    ),
    "token_usage": MetricGroup(
        key="token_usage",
        label="Token Usage",
        priority=7,
        description="LLM token consumption metrics"
    ),
}


# ==========================================
# Metric Definitions (with group assignments)
# ==========================================

METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    # Core Performance Group
    "accuracy": MetricDefinition(
        key="accuracy",
        label="Accuracy (LLM Judge)",
        description="Primary success metric",
        group="core",
        priority=1,
    ),
    "rule_accuracy": MetricDefinition(
        key="rule_accuracy",
        label="Rule-Based Accuracy",
        description="Alternative evaluation",
        group="core",
        priority=2,
    ),
    "coherence": MetricDefinition(
        key="coherence",
        label="Coherence",
        description="LLM vs Rule agreement",
        group="core",
        priority=3,
    ),

    # Outcome Distribution Group
    "correct_count": MetricDefinition(
        key="correct_count",
        label="Correct",
        description="Successful sessions",
        group="outcome",
        format_type="count",
        priority=1,
    ),
    "incorrect_count": MetricDefinition(
        key="incorrect_count",
        label="Incorrect",
        description="Failed sessions",
        group="outcome",
        format_type="count",
        priority=2,
    ),
    "error_count": MetricDefinition(
        key="error_count",
        label="Error",
        description="Error sessions",
        group="outcome",
        format_type="count",
        priority=3,
    ),

    # Efficiency Group
    "avg_trials": MetricDefinition(
        key="avg_trials",
        label="Avg. Turns",
        description="Average turns to solve",
        group="efficiency",
        format_type="number",
        priority=1,
    ),
    "avg_success_trials": MetricDefinition(
        key="avg_success_trials",
        label="Success Avg. Turns",
        description="Avg. turns for successful sessions",
        group="efficiency",
        format_type="number",
        priority=2,
    ),

    # Behavioral Analysis Group
    "first_try_rate": MetricDefinition(
        key="first_try_rate",
        label="One-Shot Success",
        description="Solved on Turn 1",
        group="behavioral",
        priority=1,
    ),
    "recovery_rate": MetricDefinition(
        key="recovery_rate",
        label="Recovery Rate",
        description="Failures fixed later",
        group="behavioral",
        priority=2,
    ),
    "stubbornness": MetricDefinition(
        key="stubbornness",
        label="Stubbornness Index",
        description="Repetition on failure",
        group="behavioral",
        is_conditional=True,
        priority=3,
    ),
    "correction_gain": MetricDefinition(
        key="correction_gain",
        label="Correction Gain",
        description="Multi-turn lift",
        group="behavioral",
        prefix="+",
        priority=4,
    ),
    "give_up_rate": MetricDefinition(
        key="give_up_rate",
        label="Give-Up Rate",
        description="Sessions that failed all retries",
        group="behavioral",
        priority=5,
    ),
    "error_rate": MetricDefinition(
        key="error_rate",
        label="Error Rate",
        description="Sessions with errors",
        group="behavioral",
        priority=6,
    ),

    # Search & Retrieval Group (conditional - only for RAG/Agent)
    "search_count": MetricDefinition(
        key="search_count",
        label="Search Queries",
        description="Avg. queries per session",
        group="search",
        format_type="number",
        is_conditional=True,
        priority=1,
    ),
    "query_diversity": MetricDefinition(
        key="query_diversity",
        label="Query Diversity",
        description="Avg. query shift distance",
        group="search",
        format_type="number",
        precision=3,
        is_conditional=True,
        priority=2,
    ),

    # Tier 1 - Essential Query Diversity Metrics
    "query_uniqueness": MetricDefinition(
        key="query_uniqueness",
        label="Query Uniqueness",
        description="Ratio of unique queries (100% = no duplicates)",
        group="search",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=3,
    ),
    "query_repetition": MetricDefinition(
        key="query_repetition",
        label="Query Repetition",
        description="Total duplicate queries",
        group="search",
        format_type="count",
        is_conditional=True,
        priority=4,
    ),
    "avg_query_length": MetricDefinition(
        key="avg_query_length",
        label="Avg Query Length",
        description="Mean words per query",
        group="search",
        format_type="number",
        precision=1,
        is_conditional=True,
        priority=5,
    ),
    "first_query_success": MetricDefinition(
        key="first_query_success",
        label="First Query Success",
        description="Sessions where first query was sufficient",
        group="search",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=6,
    ),

    # Tier 2 - Analytical Query Metrics
    "query_drift": MetricDefinition(
        key="query_drift",
        label="Query Drift",
        description="Avg deviation from original question (0=on-topic)",
        group="search",
        format_type="number",
        precision=3,
        is_conditional=True,
        priority=7,
    ),
    "query_convergence": MetricDefinition(
        key="query_convergence",
        label="Query Convergence",
        description="Diversity trend (negative = converging)",
        group="search",
        format_type="number",
        precision=3,
        is_conditional=True,
        priority=8,
    ),

    # Multi-Turn Dynamics Group
    "oscillation_rate": MetricDefinition(
        key="oscillation_rate",
        label="Answer Oscillation",
        description="Rate of A→B→A flip-flopping patterns",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=1,
    ),
    "near_miss_rate": MetricDefinition(
        key="near_miss_rate",
        label="Near-Miss Rate",
        description="Wrong answers >50% similar to ground truth",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=2,
    ),
    "recovery_stuck": MetricDefinition(
        key="recovery_stuck",
        label="Stuck Rate",
        description="Same query & answer after failure",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=3,
    ),
    "recovery_wasted": MetricDefinition(
        key="recovery_wasted",
        label="Wasted Query Rate",
        description="Changed query but same answer",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=4,
    ),
    "recovery_random": MetricDefinition(
        key="recovery_random",
        label="Random Answer Rate",
        description="Same query but different answer",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=5,
    ),
    "recovery_effective": MetricDefinition(
        key="recovery_effective",
        label="Effective Recovery Rate",
        description="Changed both query and answer",
        group="dynamics",
        format_type="percentage",
        precision=1,
        is_conditional=True,
        priority=6,
    ),
    # Token Usage Group
    "total_input_tokens": MetricDefinition(
        key="total_input_tokens",
        label="Total Input Tokens",
        description="Total prompt tokens across all trials",
        group="token_usage",
        format_type="count",
        priority=1,
    ),
    "total_output_tokens": MetricDefinition(
        key="total_output_tokens",
        label="Total Output Tokens",
        description="Total completion tokens across all trials",
        group="token_usage",
        format_type="count",
        priority=2,
    ),
    "total_tokens": MetricDefinition(
        key="total_tokens",
        label="Total Tokens",
        description="Total tokens (input + output)",
        group="token_usage",
        format_type="count",
        priority=3,
    ),
    "avg_tokens_per_trial": MetricDefinition(
        key="avg_tokens_per_trial",
        label="Avg Tokens/Trial",
        description="Average tokens consumed per trial",
        group="token_usage",
        format_type="number",
        precision=0,
        priority=4,
    ),
}


# ==========================================
# Metric Building Helper
# ==========================================

def _build_metric(definition: MetricDefinition, value: float) -> Dict[str, Any]:
    """Build a metric dict with value, formatted value, color, and metadata."""
    color = get_metric_color(definition.key)

    if definition.format_type == "percentage":
        formatted = f"{definition.prefix}{value:.{definition.precision}f}%"
    elif definition.format_type == "count":
        formatted = str(int(value))
    else:  # number
        formatted = f"{definition.prefix}{value:.{definition.precision}f}"

    return {
        "key": definition.key,
        "value": value,
        "formatted": formatted,
        "label": definition.label,
        "description": definition.description,
        "format_type": definition.format_type,
        "group": definition.group,
        "priority": definition.priority,
        "color": color,
    }


# ==========================================
# Per-Session Metric Extraction
# ==========================================
# These functions extract metrics from trials within a single session.
# They are called by extract_session_metrics() to build per-session data.

def _session_aggregate_token_usage(trials: list) -> Dict[str, int]:
    """Aggregate token usage across all trials in a session."""
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "call_count": 0,
    }
    for trial in trials:
        log = trial.log if hasattr(trial, 'log') else trial.get('log', {})
        if not log:
            continue
        trial_usage = log.get('token_usage', {})
        usage["input_tokens"] += trial_usage.get("input_tokens", 0)
        usage["output_tokens"] += trial_usage.get("output_tokens", 0)
        usage["total_tokens"] += trial_usage.get("total_tokens", 0)
        usage["call_count"] += trial_usage.get("call_count", 0)
    return usage


def _session_extract_search_metrics(result: Dict, trials: list, original_question: str = None) -> None:
    """
    Extract search/query metrics from trial logs within a session.
    Mutates `result` dict to add search-related fields.
    """
    all_queries = []

    for i, trial in enumerate(trials):
        log = trial.log if hasattr(trial, 'log') else trial.get('log', {})
        if not log:
            continue

        # Agent pipelines store queries in search_queries
        if 'search_queries' in log:
            all_queries.extend(log.get('search_queries', []))
        # RAG pipelines store single query in search_query
        elif 'search_query' in log:
            q = log.get('search_query')
            if q:
                all_queries.append(q)

    if not all_queries:
        return

    # Basic metrics
    unique_queries = set(all_queries)
    result['search_count'] = len(all_queries)
    result['query_uniqueness'] = len(unique_queries) / len(all_queries)
    result['query_repetition'] = len(all_queries) - len(unique_queries)
    result['avg_query_length'] = sum(len(q.split()) for q in all_queries) / len(all_queries)

    # First query success (did first trial succeed?)
    if trials and hasattr(trials[0], 'is_correct_llm'):
        first_correct = trials[0].is_correct_llm
    else:
        first_correct = trials[0].get('is_correct_llm') if trials else None
    if first_correct is not None:
        result['first_query_success'] = 1 if first_correct else 0

    # Query drift from original question
    if original_question and all_queries:
        total_drift = sum(
            1.0 - SequenceMatcher(None, original_question.lower(), q.lower()).ratio()
            for q in all_queries
        )
        result['query_drift'] = total_drift / len(all_queries)

    # Query shift (consecutive query diversity)
    if len(all_queries) > 1:
        shifts = []
        for i in range(len(all_queries) - 1):
            sim = SequenceMatcher(None, all_queries[i], all_queries[i + 1]).ratio()
            shifts.append(1.0 - sim)
        result['query_shift'] = sum(shifts) / len(shifts)

    # Query convergence (diversity trend)
    if len(all_queries) >= 3:
        mid = len(all_queries) // 2
        first_half_shifts = []
        second_half_shifts = []
        for i in range(len(all_queries) - 1):
            sim = SequenceMatcher(None, all_queries[i], all_queries[i + 1]).ratio()
            shift = 1.0 - sim
            if i < mid:
                first_half_shifts.append(shift)
            else:
                second_half_shifts.append(shift)
        if first_half_shifts and second_half_shifts:
            first_avg = sum(first_half_shifts) / len(first_half_shifts)
            second_avg = sum(second_half_shifts) / len(second_half_shifts)
            result['query_convergence'] = second_avg - first_avg


def _session_extract_dynamics_metrics(result: Dict, trials: list, ground_truths: list = None) -> None:
    """
    Extract multi-turn dynamics metrics from trials within a session.
    Mutates `result` dict to add dynamics-related fields.
    """
    if len(trials) < 2:
        return

    # Helper to get trial attributes
    def get_attr(trial, attr):
        return getattr(trial, attr, None) if hasattr(trial, attr) else trial.get(attr)

    answers = [get_attr(t, 'answer') for t in trials if get_attr(t, 'answer')]

    # Oscillation detection (A→B→A patterns)
    if len(answers) >= 3:
        oscillation_count = 0
        oscillation_opportunities = len(answers) - 2
        for i in range(2, len(answers)):
            sim_prev = SequenceMatcher(None, answers[i], answers[i - 1]).ratio()
            sim_two_back = SequenceMatcher(None, answers[i], answers[i - 2]).ratio()
            if sim_two_back > 0.6 and sim_prev < 0.4:
                oscillation_count += 1
        result['oscillation_count'] = oscillation_count
        result['oscillation_opportunities'] = oscillation_opportunities

    # Near-miss detection and stubbornness
    if ground_truths:
        near_miss_count = 0
        incorrect_count = 0
        stubborn_transitions = 0
        stubborn_total = 0.0

        for i, trial in enumerate(trials):
            is_correct = get_attr(trial, 'is_correct_llm')
            answer = get_attr(trial, 'answer')

            if is_correct is False and answer:
                incorrect_count += 1
                # Near-miss: >50% similar to any ground truth
                max_sim = max(
                    SequenceMatcher(None, answer.lower().strip(), gt.lower()).ratio()
                    for gt in ground_truths
                ) if ground_truths else 0
                if max_sim > 0.5:
                    near_miss_count += 1

                # Stubbornness: similarity to next answer after failure
                if i < len(trials) - 1:
                    next_answer = get_attr(trials[i + 1], 'answer') or ""
                    if next_answer:
                        stubborn_total += SequenceMatcher(None, answer, next_answer).ratio()
                        stubborn_transitions += 1

        result['near_miss_count'] = near_miss_count
        result['incorrect_count'] = incorrect_count
        if stubborn_transitions > 0:
            result['stubborn_score'] = stubborn_total / stubborn_transitions

    # Recovery strategy analysis
    recovery_total = 0
    recovery_stuck = 0
    recovery_wasted = 0
    recovery_random = 0
    recovery_effective = 0

    for i in range(len(trials) - 1):
        t1, t2 = trials[i], trials[i + 1]
        if get_attr(t1, 'is_correct_llm') is not False:
            continue  # Only analyze after failures

        a1 = get_attr(t1, 'answer') or ""
        a2 = get_attr(t2, 'answer') or ""
        log1 = get_attr(t1, 'log') or {}
        log2 = get_attr(t2, 'log') or {}

        # Get queries
        q1 = " ".join(log1.get("search_queries", [])) or log1.get("search_query", "")
        q2 = " ".join(log2.get("search_queries", [])) or log2.get("search_query", "")

        if a1 and a2 and q1 and q2:
            recovery_total += 1
            query_change = 1 - SequenceMatcher(None, q1, q2).ratio()
            answer_change = 1 - SequenceMatcher(None, a1, a2).ratio()

            if query_change < 0.3 and answer_change < 0.3:
                recovery_stuck += 1
            elif query_change >= 0.3 and answer_change < 0.3:
                recovery_wasted += 1
            elif query_change < 0.3 and answer_change >= 0.3:
                recovery_random += 1
            else:
                recovery_effective += 1

    if recovery_total > 0:
        result['recovery_total'] = recovery_total
        result['recovery_stuck'] = recovery_stuck
        result['recovery_wasted'] = recovery_wasted
        result['recovery_random'] = recovery_random
        result['recovery_effective'] = recovery_effective


def extract_session_metrics(session) -> Dict[str, Any]:
    """
    Extract all metrics for a single session from its trials.

    This is the main entry point for per-session metric extraction.
    Returns a dict with all session-level metrics ready for aggregation.
    """
    # Helper to get attributes from ORM objects or dicts
    def get_attr(obj, attr):
        return getattr(obj, attr, None) if hasattr(obj, attr) else obj.get(attr) if isinstance(obj, dict) else None

    # Get trials (handle both ORM objects and dicts)
    if hasattr(session, 'trials'):
        trials = list(session.trials.all().order_by('trial_number'))
    else:
        trials = session.get('trials', [])

    if not trials:
        return {
            'session_id': get_attr(session, 'id'),
            'question': get_attr(session, 'question'),
            'ground_truths': get_attr(session, 'ground_truths'),
            'trials': 0,
        }

    first_trial = trials[0]
    last_trial = trials[-1]

    result = {
        'session_id': get_attr(session, 'id'),
        'question': get_attr(session, 'question'),
        'ground_truths': get_attr(session, 'ground_truths'),
        'trials': len(trials),
        'correct': get_attr(last_trial, 'is_correct_llm'),
        'is_correct_llm': get_attr(last_trial, 'is_correct_llm'),
        'is_correct_rule': get_attr(last_trial, 'is_correct_rule'),
        'final_answer': get_attr(last_trial, 'answer'),
        'initial_correct': get_attr(first_trial, 'is_correct_llm'),
        'initial_correct_rule': get_attr(first_trial, 'is_correct_rule'),
    }

    # Calculate coherence (LLM vs Rule agreement)
    completed_trials = [t for t in trials if get_attr(t, 'is_correct_llm') is not None]
    if completed_trials:
        matches = sum(
            1 for t in completed_trials
            if get_attr(t, 'is_correct_llm') == get_attr(t, 'is_correct_rule')
        )
        result['coherence'] = matches / len(completed_trials)

    # Token usage
    token_usage = _session_aggregate_token_usage(trials)
    if token_usage.get('total_tokens', 0) > 0:
        result['token_usage'] = token_usage

    # Search/query metrics
    question = get_attr(session, 'question')
    _session_extract_search_metrics(result, trials, original_question=question)

    # Dynamics metrics
    ground_truths = get_attr(session, 'ground_truths')
    _session_extract_dynamics_metrics(result, trials, ground_truths=ground_truths)

    return result


def extract_sessions_metrics(sessions) -> List[Dict[str, Any]]:
    """
    Extract metrics for multiple sessions.
    Convenience wrapper around extract_session_metrics().
    """
    return [extract_session_metrics(session) for session in sessions]


# ==========================================
# Cross-Session Aggregate Calculation
# ==========================================
# These functions aggregate metrics across multiple sessions.
# They take a list of session results (from extract_session_metrics)
# and compute run-level statistics.

def calculate_accuracy(results: List[Dict]) -> Dict[str, Any]:
    """Calculate accuracy based on LLM judge results."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["accuracy"], 0.0)

    correct = sum(1 for r in results if r.get("correct") is True)
    accuracy = (correct / total) * 100
    return _build_metric(METRIC_DEFINITIONS["accuracy"], accuracy)


def calculate_rule_accuracy(results: List[Dict]) -> Dict[str, Any]:
    """Calculate accuracy based on rule-based evaluation."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["rule_accuracy"], 0.0)

    correct_rule = sum(1 for r in results if r.get("is_correct_rule") is True)
    rule_accuracy = (correct_rule / total) * 100
    return _build_metric(METRIC_DEFINITIONS["rule_accuracy"], rule_accuracy)


def calculate_coherence(results: List[Dict]) -> Dict[str, Any]:
    """Calculate average coherence (LLM vs Rule agreement)."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["coherence"], 0.0)

    coherence_sum = sum(r.get("coherence", 0) or 0 for r in results)
    avg_coherence = (coherence_sum / total) * 100
    return _build_metric(METRIC_DEFINITIONS["coherence"], avg_coherence)


def calculate_correct_count(results: List[Dict]) -> Dict[str, Any]:
    """Calculate count of correct sessions."""
    correct = sum(1 for r in results if r.get("correct") is True)
    return _build_metric(METRIC_DEFINITIONS["correct_count"], correct)


def calculate_incorrect_count(results: List[Dict]) -> Dict[str, Any]:
    """Calculate count of incorrect sessions."""
    incorrect = sum(1 for r in results if r.get("correct") is False)
    return _build_metric(METRIC_DEFINITIONS["incorrect_count"], incorrect)


def calculate_error_count(results: List[Dict]) -> Dict[str, Any]:
    """Calculate count of error sessions."""
    error = sum(1 for r in results if r.get("correct") not in (True, False))
    return _build_metric(METRIC_DEFINITIONS["error_count"], error)


def calculate_avg_trials(results: List[Dict]) -> Dict[str, Any]:
    """Calculate average number of trials across all sessions."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["avg_trials"], 0.0)

    total_trials = sum(r.get("trials", 0) or 0 for r in results)
    avg_trials = total_trials / total
    return _build_metric(METRIC_DEFINITIONS["avg_trials"], avg_trials)


def calculate_avg_success_trials(results: List[Dict]) -> Dict[str, Any]:
    """Calculate average number of trials for successful sessions."""
    success_results = [r for r in results if r.get("correct") is True]
    if not success_results:
        return _build_metric(METRIC_DEFINITIONS["avg_success_trials"], 0.0)

    success_trials = sum(r.get("trials", 0) or 0 for r in success_results)
    avg_success_trials = success_trials / len(success_results)
    return _build_metric(METRIC_DEFINITIONS["avg_success_trials"], avg_success_trials)


def calculate_first_try_rate(results: List[Dict]) -> Dict[str, Any]:
    """Calculate first try (one-shot) success rate."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["first_try_rate"], 0.0)

    first_try_success = sum(1 for r in results if r.get("initial_correct") is True)
    first_try_rate = (first_try_success / total) * 100
    return _build_metric(METRIC_DEFINITIONS["first_try_rate"], first_try_rate)


def calculate_recovery_rate(results: List[Dict]) -> Dict[str, Any]:
    """Calculate self-correction / recovery rate."""
    initial_failures = [r for r in results if r.get("initial_correct") is False]
    if not initial_failures:
        return _build_metric(METRIC_DEFINITIONS["recovery_rate"], 0.0)

    self_corrected = [r for r in initial_failures if r.get("correct") is True]
    recovery_rate = (len(self_corrected) / len(initial_failures)) * 100
    return _build_metric(METRIC_DEFINITIONS["recovery_rate"], recovery_rate)


def calculate_correction_gain(results: List[Dict]) -> Dict[str, Any]:
    """Calculate correction gain (final accuracy - first try accuracy)."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["correction_gain"], 0.0)

    correct = sum(1 for r in results if r.get("correct") is True)
    accuracy = (correct / total) * 100

    first_try_success = sum(1 for r in results if r.get("initial_correct") is True)
    first_try_rate = (first_try_success / total) * 100

    correction_gain = accuracy - first_try_rate
    return _build_metric(METRIC_DEFINITIONS["correction_gain"], correction_gain)


def calculate_give_up_rate(results: List[Dict]) -> Dict[str, Any]:
    """Calculate give-up rate (sessions that failed all retries)."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["give_up_rate"], 0.0)

    incorrect = sum(1 for r in results if r.get("correct") is False)
    give_up_rate = (incorrect / total) * 100
    return _build_metric(METRIC_DEFINITIONS["give_up_rate"], give_up_rate)


def calculate_error_rate(results: List[Dict]) -> Dict[str, Any]:
    """Calculate error rate."""
    total = len(results)
    if total == 0:
        return _build_metric(METRIC_DEFINITIONS["error_rate"], 0.0)

    error = sum(1 for r in results if r.get("correct") not in (True, False))
    error_rate = (error / total) * 100
    return _build_metric(METRIC_DEFINITIONS["error_rate"], error_rate)


def calculate_stubbornness(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate stubbornness index. Returns None if no data."""
    stubborn_sessions = [
        r for r in results
        if r.get("stubborn_score") is not None and r.get("stubborn_score", 0) > 0
    ]

    if not stubborn_sessions:
        return None

    stubbornness = (
        sum(r.get("stubborn_score", 0) for r in stubborn_sessions)
        / len(stubborn_sessions)
    ) * 100
    return _build_metric(METRIC_DEFINITIONS["stubbornness"], stubbornness)


def calculate_search_count(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average search query count. Returns None if no data."""
    search_count_sessions = [r for r in results if r.get("search_count") is not None]

    if not search_count_sessions:
        return None

    avg_search_count = (
        sum(r.get("search_count", 0) for r in search_count_sessions)
        / len(search_count_sessions)
    )
    return _build_metric(METRIC_DEFINITIONS["search_count"], avg_search_count)


def calculate_query_diversity(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average query diversity. Returns None if no data."""
    shift_sessions = [r for r in results if r.get("query_shift") is not None]

    if not shift_sessions:
        return None

    avg_query_shift = sum(r.get("query_shift", 0) for r in shift_sessions) / len(shift_sessions)
    return _build_metric(METRIC_DEFINITIONS["query_diversity"], avg_query_shift)


def calculate_query_uniqueness(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average query uniqueness ratio. Returns None if no data."""
    sessions = [r for r in results if r.get("query_uniqueness") is not None]
    if not sessions:
        return None
    avg = sum(r.get("query_uniqueness", 0) for r in sessions) / len(sessions) * 100
    return _build_metric(METRIC_DEFINITIONS["query_uniqueness"], avg)


def calculate_query_repetition(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate total duplicate query count. Returns None if no data."""
    sessions = [r for r in results if r.get("query_repetition") is not None]
    if not sessions:
        return None
    total = sum(r.get("query_repetition", 0) for r in sessions)
    return _build_metric(METRIC_DEFINITIONS["query_repetition"], total)


def calculate_avg_query_length(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average query length in words. Returns None if no data."""
    sessions = [r for r in results if r.get("avg_query_length") is not None]
    if not sessions:
        return None
    avg = sum(r.get("avg_query_length", 0) for r in sessions) / len(sessions)
    return _build_metric(METRIC_DEFINITIONS["avg_query_length"], avg)


def calculate_first_query_success(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate first query success rate. Returns None if no data."""
    sessions = [r for r in results if r.get("first_query_success") is not None]
    if not sessions:
        return None
    rate = sum(r.get("first_query_success", 0) for r in sessions) / len(sessions) * 100
    return _build_metric(METRIC_DEFINITIONS["first_query_success"], rate)


def calculate_query_drift(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average query drift from original question. Returns None if no data."""
    sessions = [r for r in results if r.get("query_drift") is not None]
    if not sessions:
        return None
    avg = sum(r.get("query_drift", 0) for r in sessions) / len(sessions)
    return _build_metric(METRIC_DEFINITIONS["query_drift"], avg)


def calculate_query_convergence(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average query convergence trend. Returns None if no data."""
    sessions = [r for r in results if r.get("query_convergence") is not None]
    if not sessions:
        return None
    avg = sum(r.get("query_convergence", 0) for r in sessions) / len(sessions)
    return _build_metric(METRIC_DEFINITIONS["query_convergence"], avg)


# ==========================================
# Multi-Turn Dynamics Metrics
# ==========================================

def calculate_oscillation_rate(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    Calculate answer oscillation rate (A→B→A patterns).
    Returns None if no multi-trial sessions.
    """
    total_oscillations = 0
    total_opportunities = 0

    for r in results:
        oscillations = r.get("oscillation_count", 0)
        opportunities = r.get("oscillation_opportunities", 0)
        if opportunities is not None and opportunities > 0:
            total_oscillations += oscillations or 0
            total_opportunities += opportunities

    if total_opportunities == 0:
        return None

    rate = (total_oscillations / total_opportunities) * 100
    return _build_metric(METRIC_DEFINITIONS["oscillation_rate"], rate)


def calculate_near_miss_rate(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    Calculate near-miss rate (incorrect answers >50% similar to ground truth).
    Returns None if no incorrect answers.
    """
    total_near_misses = 0
    total_incorrect = 0

    for r in results:
        near_misses = r.get("near_miss_count", 0)
        incorrect = r.get("incorrect_count", 0)
        if incorrect is not None and incorrect > 0:
            total_near_misses += near_misses or 0
            total_incorrect += incorrect

    if total_incorrect == 0:
        return None

    rate = (total_near_misses / total_incorrect) * 100
    return _build_metric(METRIC_DEFINITIONS["near_miss_rate"], rate)


def calculate_recovery_stuck(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate stuck rate (same query & answer after failure)."""
    total = sum(r.get("recovery_total", 0) or 0 for r in results)
    if total == 0:
        return None
    stuck = sum(r.get("recovery_stuck", 0) or 0 for r in results)
    return _build_metric(METRIC_DEFINITIONS["recovery_stuck"], (stuck / total) * 100)


def calculate_recovery_wasted(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate wasted query rate (changed query but same answer)."""
    total = sum(r.get("recovery_total", 0) or 0 for r in results)
    if total == 0:
        return None
    wasted = sum(r.get("recovery_wasted", 0) or 0 for r in results)
    return _build_metric(METRIC_DEFINITIONS["recovery_wasted"], (wasted / total) * 100)


def calculate_recovery_random(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate random answer rate (same query but different answer)."""
    total = sum(r.get("recovery_total", 0) or 0 for r in results)
    if total == 0:
        return None
    random_ans = sum(r.get("recovery_random", 0) or 0 for r in results)
    return _build_metric(METRIC_DEFINITIONS["recovery_random"], (random_ans / total) * 100)


def calculate_recovery_effective(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate effective recovery rate (changed both query and answer)."""
    total = sum(r.get("recovery_total", 0) or 0 for r in results)
    if total == 0:
        return None
    effective = sum(r.get("recovery_effective", 0) or 0 for r in results)
    return _build_metric(METRIC_DEFINITIONS["recovery_effective"], (effective / total) * 100)


# ==========================================
# Token Usage Calculation Functions
# ==========================================

def calculate_total_input_tokens(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate total input tokens across all sessions."""
    total = sum(r.get("token_usage", {}).get("input_tokens", 0) for r in results)
    if total == 0:
        return None
    return _build_metric(METRIC_DEFINITIONS["total_input_tokens"], total)


def calculate_total_output_tokens(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate total output tokens across all sessions."""
    total = sum(r.get("token_usage", {}).get("output_tokens", 0) for r in results)
    if total == 0:
        return None
    return _build_metric(METRIC_DEFINITIONS["total_output_tokens"], total)


def calculate_total_tokens(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate total tokens across all sessions."""
    total = sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results)
    if total == 0:
        return None
    return _build_metric(METRIC_DEFINITIONS["total_tokens"], total)


def calculate_avg_tokens_per_trial(results: List[Dict]) -> Optional[Dict[str, Any]]:
    """Calculate average tokens per trial across all sessions."""
    total_tokens = sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results)
    total_trials = sum(r.get("trials", 0) for r in results)
    if total_trials == 0:
        return None
    avg = total_tokens / total_trials
    return _build_metric(METRIC_DEFINITIONS["avg_tokens_per_trial"], avg)


# ==========================================
# Aggregate Metrics Calculation
# ==========================================

def calculate_aggregate_metrics(results: List[Dict[str, Any]], pipeline_type: str = None) -> Dict[str, Any]:
    """
    Calculate all aggregate metrics from a list of session results.

    Args:
        results: List of session result dicts
        pipeline_type: Pipeline type to filter applicable groups (vanilla_llm, rag, etc.)

    Returns metrics organized by groups with proper ordering, filtered by pipeline_type.
    """
    # Get applicable groups for this pipeline
    applicable_groups = PIPELINE_METRIC_GROUPS.get(pipeline_type, list(METRIC_GROUPS.keys()))

    total = len(results)
    if total == 0:
        return {
            "metrics": {},
            "groups": get_metric_groups(pipeline_type),
            "total": 0,
            "summary": {}
        }

    metrics = {}

    # Core accuracy metrics
    if "core" in applicable_groups:
        metrics["accuracy"] = calculate_accuracy(results)
        metrics["rule_accuracy"] = calculate_rule_accuracy(results)
        metrics["coherence"] = calculate_coherence(results)

    # Outcome metrics
    if "outcome" in applicable_groups:
        metrics["correct_count"] = calculate_correct_count(results)
        metrics["incorrect_count"] = calculate_incorrect_count(results)
        metrics["error_count"] = calculate_error_count(results)

    # Efficiency metrics
    if "efficiency" in applicable_groups:
        metrics["avg_trials"] = calculate_avg_trials(results)
        metrics["avg_success_trials"] = calculate_avg_success_trials(results)

    # Behavioral metrics
    if "behavioral" in applicable_groups:
        metrics["first_try_rate"] = calculate_first_try_rate(results)
        metrics["recovery_rate"] = calculate_recovery_rate(results)
        metrics["correction_gain"] = calculate_correction_gain(results)
        metrics["give_up_rate"] = calculate_give_up_rate(results)
        metrics["error_rate"] = calculate_error_rate(results)
        stubbornness = calculate_stubbornness(results)
        if stubbornness:
            metrics["stubbornness"] = stubbornness

    # Search metrics (only for pipelines with search group)
    if "search" in applicable_groups:
        search_count = calculate_search_count(results)
        if search_count:
            metrics["search_count"] = search_count
        query_diversity = calculate_query_diversity(results)
        if query_diversity:
            metrics["query_diversity"] = query_diversity

        # Tier 1 - Essential Query Diversity Metrics
        query_uniqueness = calculate_query_uniqueness(results)
        if query_uniqueness:
            metrics["query_uniqueness"] = query_uniqueness
        query_repetition = calculate_query_repetition(results)
        if query_repetition:
            metrics["query_repetition"] = query_repetition
        avg_query_length = calculate_avg_query_length(results)
        if avg_query_length:
            metrics["avg_query_length"] = avg_query_length
        first_query_success = calculate_first_query_success(results)
        if first_query_success:
            metrics["first_query_success"] = first_query_success

        # Tier 2 - Analytical Query Metrics
        query_drift = calculate_query_drift(results)
        if query_drift:
            metrics["query_drift"] = query_drift
        query_convergence = calculate_query_convergence(results)
        if query_convergence:
            metrics["query_convergence"] = query_convergence

    # Multi-Turn Dynamics metrics
    if "dynamics" in applicable_groups:
        oscillation_rate = calculate_oscillation_rate(results)
        if oscillation_rate:
            metrics["oscillation_rate"] = oscillation_rate
        near_miss_rate = calculate_near_miss_rate(results)
        if near_miss_rate:
            metrics["near_miss_rate"] = near_miss_rate
        recovery_stuck = calculate_recovery_stuck(results)
        if recovery_stuck:
            metrics["recovery_stuck"] = recovery_stuck
        recovery_wasted = calculate_recovery_wasted(results)
        if recovery_wasted:
            metrics["recovery_wasted"] = recovery_wasted
        recovery_random = calculate_recovery_random(results)
        if recovery_random:
            metrics["recovery_random"] = recovery_random
        recovery_effective = calculate_recovery_effective(results)
        if recovery_effective:
            metrics["recovery_effective"] = recovery_effective

    # Token Usage metrics (all pipelines)
    if "token_usage" in applicable_groups:
        total_input = calculate_total_input_tokens(results)
        if total_input:
            metrics["total_input_tokens"] = total_input
        total_output = calculate_total_output_tokens(results)
        if total_output:
            metrics["total_output_tokens"] = total_output
        total_tokens = calculate_total_tokens(results)
        if total_tokens:
            metrics["total_tokens"] = total_tokens
        avg_tokens = calculate_avg_tokens_per_trial(results)
        if avg_tokens:
            metrics["avg_tokens_per_trial"] = avg_tokens

    # Build summary
    summary = {
        "total_sessions": total,
        "correct": int(metrics.get("correct_count", {}).get("value", 0)),
        "incorrect": int(metrics.get("incorrect_count", {}).get("value", 0)),
        "error": int(metrics.get("error_count", {}).get("value", 0)),
    }

    return {
        "metrics": metrics,
        "groups": get_metric_groups(pipeline_type),
        "definitions": get_metric_definitions(pipeline_type),
        "total": total,
        "summary": summary
    }


def get_metric_groups(pipeline_type: str = None) -> List[Dict[str, Any]]:
    """Get metric groups sorted by priority, filtered by pipeline_type."""
    applicable_keys = PIPELINE_METRIC_GROUPS.get(pipeline_type, list(METRIC_GROUPS.keys()))
    groups = [
        group.to_dict() for group in METRIC_GROUPS.values()
        if group.key in applicable_keys
    ]
    return sorted(groups, key=lambda g: g["priority"])


def get_metric_definitions(pipeline_type: str = None) -> Dict[str, Dict[str, Any]]:
    """Get metric definitions as dicts, filtered by pipeline_type."""
    applicable_groups = PIPELINE_METRIC_GROUPS.get(pipeline_type, list(METRIC_GROUPS.keys()))
    return {
        key: defn.to_dict() for key, defn in METRIC_DEFINITIONS.items()
        if defn.group in applicable_groups
    }


def get_all_metric_colors() -> Dict[str, Dict[str, str]]:
    """Get a mapping of all metric keys to their colors."""
    return {key: get_metric_color(key) for key in METRIC_DEFINITIONS.keys()}


def get_metrics_by_group() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get metric definitions organized by group.

    Returns a dict where keys are group keys and values are lists of
    metric definitions sorted by priority within the group.
    """
    by_group: Dict[str, List[MetricDefinition]] = {}

    for defn in METRIC_DEFINITIONS.values():
        if defn.group not in by_group:
            by_group[defn.group] = []
        by_group[defn.group].append(defn)

    # Sort each group by priority
    result = {}
    for group_key, metrics in by_group.items():
        sorted_metrics = sorted(metrics, key=lambda m: m.priority)
        result[group_key] = [m.to_dict() for m in sorted_metrics]

    return result
