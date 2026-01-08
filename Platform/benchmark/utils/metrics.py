"""
Metrics calculation module for benchmark results.

This module centralizes all metrics calculations that were previously done in the frontend,
providing a consistent API for computing and styling benchmark metrics.

Each metric has its own calculation function for better maintainability.
Groups and priorities are defined here to ensure frontend consistency.
"""

import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


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
# Individual Metric Calculation Functions
# ==========================================

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


# ==========================================
# Aggregate Metrics Calculation
# ==========================================

def calculate_aggregate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate all aggregate metrics from a list of session results.

    Returns metrics organized by groups with proper ordering.
    """
    total = len(results)
    if total == 0:
        return {
            "metrics": {},
            "groups": get_metric_groups(),
            "total": 0,
            "summary": {}
        }

    metrics = {}

    # Core accuracy metrics
    metrics["accuracy"] = calculate_accuracy(results)
    metrics["rule_accuracy"] = calculate_rule_accuracy(results)
    metrics["coherence"] = calculate_coherence(results)

    # Count metrics
    metrics["correct_count"] = calculate_correct_count(results)
    metrics["incorrect_count"] = calculate_incorrect_count(results)
    metrics["error_count"] = calculate_error_count(results)

    # Efficiency metrics
    metrics["avg_trials"] = calculate_avg_trials(results)
    metrics["avg_success_trials"] = calculate_avg_success_trials(results)

    # Behavioral metrics
    metrics["first_try_rate"] = calculate_first_try_rate(results)
    metrics["recovery_rate"] = calculate_recovery_rate(results)
    metrics["correction_gain"] = calculate_correction_gain(results)
    metrics["give_up_rate"] = calculate_give_up_rate(results)
    metrics["error_rate"] = calculate_error_rate(results)

    # Conditional metrics
    stubbornness = calculate_stubbornness(results)
    if stubbornness:
        metrics["stubbornness"] = stubbornness

    search_count = calculate_search_count(results)
    if search_count:
        metrics["search_count"] = search_count

    query_diversity = calculate_query_diversity(results)
    if query_diversity:
        metrics["query_diversity"] = query_diversity

    # Build summary
    summary = {
        "total_sessions": total,
        "correct": int(metrics["correct_count"]["value"]),
        "incorrect": int(metrics["incorrect_count"]["value"]),
        "error": int(metrics["error_count"]["value"]),
        "has_search_metrics": search_count is not None,
        "has_stubbornness": stubbornness is not None,
    }

    return {
        "metrics": metrics,
        "groups": get_metric_groups(),
        "definitions": get_metric_definitions(),
        "total": total,
        "summary": summary
    }


def get_metric_groups() -> List[Dict[str, Any]]:
    """Get all metric groups sorted by priority."""
    groups = [group.to_dict() for group in METRIC_GROUPS.values()]
    return sorted(groups, key=lambda g: g["priority"])


def get_metric_definitions() -> Dict[str, Dict[str, Any]]:
    """Get all metric definitions as dicts."""
    return {key: defn.to_dict() for key, defn in METRIC_DEFINITIONS.items()}


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
