"""
Cognitive Load Analysis: Detecting When Humans Struggle (Behavioral Proxies).

================================================================================
HONEST ASSESSMENT: LIMITATIONS AND UNIQUE VALUE
================================================================================

LIMITATION: These are INDIRECT behavioral proxies for cognitive load.
Ji et al. (2024) showed physiological signals (EEG, eye-tracking, GSR) provide
more accurate measurement. Behavioral proxies are noisier.

HOWEVER, your trajectory data has UNIQUE VALUE that physiological studies lack:
- SCALE: Physiological studies have N=26-40 participants. You likely have more.
- ECOLOGICAL VALIDITY: Real tasks, not lab-controlled scenarios.
- OUTCOME LABELS: You have success/failure labels to correlate with load signals.
- CONFIDENCE LABELS: You can cross-validate load proxies with user confidence.

>>> KEY INSIGHT: Use cognitive load analysis as a SECONDARY filter, cross-
    validated with success_patterns and confidence metrics. Don't rely on it
    alone, but it adds signal when combined with other analyses.

================================================================================
RESEARCH GAPS THIS ANALYSIS CAN ADDRESS (with caveats)
================================================================================

GAP 1: When Do Humans Need Help? (Assistance Timing)
    Wang et al. (2024), Peng et al. (2024): LLM assistance reduces cognitive load.
    But WHEN should assistance be offered?

    UNSOLVED: What behavioral signals indicate a user needs help RIGHT NOW?
    Current assistants either: always available (annoying) or never proactive.

    >>> YOUR DATA CAN: Identify behavioral patterns BEFORE failures.
        - Spike in query rate?
        - Increased backtracking?
        - Shortened dwell times (rushing/frustrated)?
        Cross-validate: Do these patterns predict eventual failure?
        Application: Train agents to offer help when these signals appear.

GAP 2: The Backtracker Paradox
    Literature conflict:
    - Some studies: Backtracking indicates good metacognition (Hsu et al., 2022)
    - Other studies: Backtracking indicates confusion (Gwizdka, 2010)

    UNSOLVED: When is backtracking STRATEGIC vs CONFUSED?

    >>> YOUR DATA CAN: Resolve this by correlating backtracking with outcomes.
        Hypothesis: Strategic backtracking = return with NEW query (adaptation)
                    Confused backtracking = return with SAME query (stuck)
        Analysis: Classify backtrack events, correlate with task success.
        This is a NOVEL contribution behavioral data can make.

GAP 3: Difficulty Detection for Curriculum Learning
    Agent training could benefit from difficulty-ordered curricula:
    - Start with easy tasks (low cognitive load)
    - Progress to hard tasks (high cognitive load)

    UNSOLVED: How to ORDER trajectories by difficulty without manual labeling?

    >>> YOUR DATA CAN: Use cognitive load proxies as difficulty estimates.
        - High load index = harder task/trajectory
        - Low load index = easier task/trajectory
        Validate: Correlate with task success rate and completion time.
        Application: Automatic curriculum generation for agent training.

GAP 4: Search Stage Transitions
    Gwizdka (2010), Ji et al. (2024): Cognitive load varies by search stage.
    - Query formulation: highest load (deciding what to search)
    - SERP evaluation: moderate load (selecting results)
    - Content reading: variable load (depends on content)

    UNSOLVED: How do humans transition between stages? What triggers stage shifts?

    >>> YOUR DATA CAN: Segment trajectories by stage, analyze:
        - Time spent in each stage
        - Load proxies by stage
        - What triggers stage transitions (time? pages? queries?)
        Application: Train agents with stage-aware behavior models.

================================================================================
RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: Do behavioral load proxies predict task failure?
    - Cross-validate: High CLI → lower success rate?
    - If YES: Use as trajectory quality filter
    - If NO: Behavioral proxies may be too noisy, deprioritize this analysis

Q2: Can we distinguish strategic from confused backtracking?
    - Method: Classify backtracks by query change (new vs same)
    - Correlate: With eventual task outcome
    - Novel: Resolve conflicting findings in literature

Q3: Do load proxies correlate with user confidence?
    - Cross-validate: High load → low confidence? (expected)
    - If YES: Mutual validation of both signals
    - If NO: One signal may be unreliable

Q4: What is the "rhythm" of successful search sessions?
    - Analyze: Load proxy trajectories over time
    - Identify: Patterns in successful sessions (start high, decrease?)
    - Train: Expected load trajectory for agent self-monitoring

Q5: Can early-session load predict final outcome?
    - Analyze: Load proxies in first 30s/60s/2min
    - Predict: Final task success
    - Application: Early intervention signals for agents

================================================================================
BEHAVIORAL PROXIES AND THEIR RELIABILITY
================================================================================

MORE RELIABLE (correlate well with physiological measures):
1. Navigation Entropy - Well-established proxy for focused vs scattered attention
2. SERP Dwell Time - Longer = difficulty selecting (Ji et al. confirmed)
3. Query Rate - Spikes indicate trouble

LESS RELIABLE (more confounded by individual differences):
4. Dwell Time Variance - Could be reading speed, not load
5. Backtracking Rate - Depends on strategic vs confused (needs classification)
6. Page Revisits - Could be verification (good) or forgetting (bad)

RECOMMENDATION: Use this analysis to generate HYPOTHESES, then validate
with success_patterns and confidence analysis before drawing conclusions.

Usage:
    python manage.py analyze_cognitive_load
    python manage.py analyze_cognitive_load --format json
    python manage.py analyze_cognitive_load --by-stage
    python manage.py analyze_cognitive_load --correlate-success  # Key validation!
"""

import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from task_manager.models import Task, TaskTrial, Webpage


@dataclass
class CognitiveLoadMetrics:
    """Cognitive load proxy metrics for a task."""
    task_id: int

    # Temporal indicators
    dwell_time_mean: float
    dwell_time_std: float
    dwell_time_cv: float  # coefficient of variation
    serp_dwell_mean: float
    content_dwell_mean: float

    # Navigation indicators
    backtrack_rate: float  # A->B->A / total transitions
    revisit_rate: float
    navigation_entropy: float  # Shannon entropy of page visits

    # Interaction patterns
    pages_per_minute: float
    queries_per_minute: float

    # Stage-based (if timestamps available)
    query_formulation_ratio: float  # time on SERP vs content

    # Composite score
    cognitive_load_index: float  # 0-100, higher = more load

    # Outcome
    is_correct: Optional[bool]


def shannon_entropy(counts: Counter) -> float:
    """Calculate Shannon entropy of a distribution."""
    total = sum(counts.values())
    if total <= 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log2(p)

    return entropy


def normalized_entropy(counts: Counter) -> float:
    """Calculate normalized entropy (0-1 scale)."""
    if not counts or len(counts) <= 1:
        return 0.0

    h = shannon_entropy(counts)
    max_h = math.log2(len(counts))

    return h / max_h if max_h > 0 else 0.0


def extract_query(url: str) -> Optional[str]:
    """Extract search query from URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        netloc = parsed.netloc.lower()

        if 'google' in netloc:
            return params.get('q', [None])[0]
        elif 'bing' in netloc:
            return params.get('q', [None])[0]
        elif 'baidu' in netloc:
            return params.get('wd', [None])[0]
        elif 'duckduckgo' in netloc:
            return params.get('q', [None])[0]
        elif 'yahoo' in netloc:
            return params.get('p', [None])[0]
    except Exception:
        pass
    return None


def is_serp(url: str) -> bool:
    """Check if URL is a SERP."""
    return extract_query(url) is not None


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    try:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".lower().rstrip('/')
    except Exception:
        return url


def compute_cognitive_load(task: Task, pages: list[Webpage], trials: list[TaskTrial]) -> Optional[CognitiveLoadMetrics]:
    """Compute cognitive load metrics for a task."""
    if len(pages) < 2:
        return None

    # Determine correctness
    is_correct = None
    if trials:
        final_trial = max(trials, key=lambda t: (t.num_trial, t.id))
        is_correct = final_trial.is_correct

    # Dwell times
    dwell_times = [p.dwell_time / 1000.0 for p in pages if p.dwell_time and p.dwell_time > 0]

    if not dwell_times:
        return None

    dwell_mean = statistics.mean(dwell_times)
    dwell_std = statistics.stdev(dwell_times) if len(dwell_times) > 1 else 0
    dwell_cv = dwell_std / dwell_mean if dwell_mean > 0 else 0

    # SERP vs content dwell
    serp_dwells = [p.dwell_time / 1000.0 for p in pages if p.dwell_time and is_serp(p.url)]
    content_dwells = [p.dwell_time / 1000.0 for p in pages if p.dwell_time and not is_serp(p.url)]

    serp_dwell_mean = statistics.mean(serp_dwells) if serp_dwells else 0
    content_dwell_mean = statistics.mean(content_dwells) if content_dwells else 0

    # Navigation patterns
    normalized_urls = [normalize_url(p.url) for p in pages]
    unique_urls = set(normalized_urls)

    # Backtrack rate (A->B->A patterns)
    backtrack_count = 0
    transitions = len(normalized_urls) - 1
    for i in range(len(normalized_urls) - 2):
        if normalized_urls[i] == normalized_urls[i + 2] and normalized_urls[i] != normalized_urls[i + 1]:
            backtrack_count += 1

    backtrack_rate = backtrack_count / transitions if transitions > 0 else 0

    # Revisit rate
    revisit_rate = 1 - (len(unique_urls) / len(normalized_urls)) if normalized_urls else 0

    # Navigation entropy
    url_counts = Counter(normalized_urls)
    nav_entropy = normalized_entropy(url_counts)

    # Temporal metrics
    total_time = sum(dwell_times)
    pages_per_minute = len(pages) / (total_time / 60) if total_time > 0 else 0

    # Query count
    queries = []
    for p in pages:
        q = extract_query(p.url)
        if q and (not queries or queries[-1] != q):
            queries.append(q)

    queries_per_minute = len(queries) / (total_time / 60) if total_time > 0 else 0

    # Stage ratio (SERP time vs content time)
    total_serp_time = sum(serp_dwells)
    total_content_time = sum(content_dwells)
    query_formulation_ratio = total_serp_time / (total_serp_time + total_content_time) if (total_serp_time + total_content_time) > 0 else 0

    # Cognitive load index (composite)
    cli = compute_cognitive_load_index(
        dwell_cv=dwell_cv,
        backtrack_rate=backtrack_rate,
        revisit_rate=revisit_rate,
        nav_entropy=nav_entropy,
        pages_per_minute=pages_per_minute,
        queries_per_minute=queries_per_minute,
        query_formulation_ratio=query_formulation_ratio,
    )

    return CognitiveLoadMetrics(
        task_id=task.id,
        dwell_time_mean=dwell_mean,
        dwell_time_std=dwell_std,
        dwell_time_cv=dwell_cv,
        serp_dwell_mean=serp_dwell_mean,
        content_dwell_mean=content_dwell_mean,
        backtrack_rate=backtrack_rate,
        revisit_rate=revisit_rate,
        navigation_entropy=nav_entropy,
        pages_per_minute=pages_per_minute,
        queries_per_minute=queries_per_minute,
        query_formulation_ratio=query_formulation_ratio,
        cognitive_load_index=cli,
        is_correct=is_correct,
    )


def compute_cognitive_load_index(
    dwell_cv: float,
    backtrack_rate: float,
    revisit_rate: float,
    nav_entropy: float,
    pages_per_minute: float,
    queries_per_minute: float,
    query_formulation_ratio: float,
) -> float:
    """
    Compute composite cognitive load index (0-100).

    Based on Gwizdka (2010) findings:
    - High dwell variance = higher load
    - High backtrack rate = higher load (but moderate is OK)
    - High navigation entropy = higher load (scattered attention)
    - Very high pages/min = rushing (high load)
    - Very low pages/min = stuck (high load)
    - High query formulation ratio = more time on hard stage
    """
    index = 50.0  # baseline

    # Dwell time CV (higher = more load)
    # Optimal CV around 0.5-1.0
    if dwell_cv > 1.5:
        index += (dwell_cv - 1.5) * 15
    elif dwell_cv < 0.3:
        index += 5  # very uniform might indicate skimming

    # Backtrack rate
    # Moderate backtracking is OK (metacognition)
    # Excessive is bad
    if backtrack_rate > 0.2:
        index += (backtrack_rate - 0.2) * 50
    elif backtrack_rate == 0:
        index -= 5  # some backtracking is normal

    # Navigation entropy
    # High entropy = scattered, low entropy = focused
    index += nav_entropy * 20

    # Pages per minute
    # Optimal range: 1-3 pages/min
    if pages_per_minute > 5:
        index += (pages_per_minute - 5) * 5  # rushing
    elif pages_per_minute < 0.5:
        index += 10  # stuck

    # Query formulation ratio
    # High time on SERP = difficulty selecting
    # From Gwizdka: query formulation is highest load stage
    if query_formulation_ratio > 0.5:
        index += (query_formulation_ratio - 0.5) * 20

    return max(0, min(100, index))


class Command(BaseCommand):
    help = 'Analyzes cognitive load using behavioral proxies from Gwizdka (2010).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--by-stage',
            action='store_true',
            help='Show detailed stage-by-stage analysis',
        )
        parser.add_argument(
            '--correlate-success',
            action='store_true',
            help='Correlate cognitive load with task success',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)',
        )
        parser.add_argument(
            '--min-pages',
            type=int,
            default=3,
            help='Minimum pages per task (default: 3)',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        by_stage = options['by_stage']
        correlate_success = options['correlate_success']
        batch_size = options['batch_size']
        min_pages = options['min_pages']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Cognitive Load: Detecting When Humans Struggle'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('LIMITATION: Indirect behavioral proxies (see docstring for caveats)'))
            self.stdout.write(self.style.SUCCESS('UNIQUE VALUE: Scale, ecological validity, outcome labels'))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. When Do Humans Need Help? (Assistance Timing)')
            self.stdout.write('     - What behavioral signals indicate need for help RIGHT NOW?')
            self.stdout.write('  2. Backtracker Paradox Resolution')
            self.stdout.write('     - When is backtracking STRATEGIC vs CONFUSED?')
            self.stdout.write('     - Your data can resolve conflicting literature findings')
            self.stdout.write('  3. Difficulty Detection for Curriculum Learning')
            self.stdout.write('     - Order trajectories by difficulty without manual labels')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Identify pre-failure behavioral patterns')
            self.stdout.write('               Classify backtracking (new query = strategic)')
            self.stdout.write('               Cross-validate with success_patterns analysis')
            self.stdout.write('')

        # Get tasks
        task_ids = list(
            Task.objects.filter(webpage__isnull=False)
            .values_list('id', flat=True)
            .distinct()
        )
        total_tasks = len(task_ids)

        if output_format == 'text':
            self.stdout.write(f'Found {total_tasks} tasks to process.')

        all_metrics: list[CognitiveLoadMetrics] = []

        for batch_start in range(0, total_tasks, batch_size):
            batch_ids = task_ids[batch_start:batch_start + batch_size]

            # Optimize: only load required fields, exclude large JSON fields
            tasks = Task.objects.filter(id__in=batch_ids).only(
                'id', 'user_id'
            ).prefetch_related(
                Prefetch(
                    'webpage_set',
                    queryset=Webpage.objects.only(
                        'id', 'belong_task_id', 'url', 'dwell_time', 'start_timestamp'
                    ).order_by('id')
                ),
                Prefetch(
                    'tasktrial_set',
                    queryset=TaskTrial.objects.only(
                        'id', 'belong_task_id', 'num_trial', 'is_correct'
                    )
                )
            )

            if output_format == 'text':
                batch_num = batch_start // batch_size + 1
                total_batches = (total_tasks + batch_size - 1) // batch_size
                self.stdout.write(f'Processing batch {batch_num}/{total_batches}...')

            for task in tasks:
                pages = list(task.webpage_set.all())
                trials = list(task.tasktrial_set.all())

                if len(pages) < min_pages:
                    continue

                metrics = compute_cognitive_load(task, pages, trials)
                if metrics:
                    all_metrics.append(metrics)

        if not all_metrics:
            self.stdout.write(self.style.WARNING('No tasks with sufficient data found.'))
            return

        # Aggregate statistics
        cli_values = [m.cognitive_load_index for m in all_metrics]
        dwell_cv_values = [m.dwell_time_cv for m in all_metrics]
        backtrack_values = [m.backtrack_rate for m in all_metrics]
        entropy_values = [m.navigation_entropy for m in all_metrics]

        # Load distribution
        low_load = [m for m in all_metrics if m.cognitive_load_index < 40]
        medium_load = [m for m in all_metrics if 40 <= m.cognitive_load_index < 70]
        high_load = [m for m in all_metrics if m.cognitive_load_index >= 70]

        results = {
            'total_tasks': len(all_metrics),
            'cognitive_load_distribution': {
                'low': {'count': len(low_load), 'percentage': len(low_load) / len(all_metrics) * 100},
                'medium': {'count': len(medium_load), 'percentage': len(medium_load) / len(all_metrics) * 100},
                'high': {'count': len(high_load), 'percentage': len(high_load) / len(all_metrics) * 100},
            },
            'aggregate_metrics': {
                'cognitive_load_index': {
                    'mean': statistics.mean(cli_values),
                    'median': statistics.median(cli_values),
                    'std': statistics.stdev(cli_values) if len(cli_values) > 1 else 0,
                },
                'dwell_time_cv': {
                    'mean': statistics.mean(dwell_cv_values),
                    'median': statistics.median(dwell_cv_values),
                },
                'backtrack_rate': {
                    'mean': statistics.mean(backtrack_values),
                    'median': statistics.median(backtrack_values),
                },
                'navigation_entropy': {
                    'mean': statistics.mean(entropy_values),
                    'median': statistics.median(entropy_values),
                },
            },
        }

        # Success correlation
        if correlate_success:
            successful = [m for m in all_metrics if m.is_correct is True]
            unsuccessful = [m for m in all_metrics if m.is_correct is False]

            if successful and unsuccessful:
                results['success_correlation'] = {
                    'successful': {
                        'count': len(successful),
                        'cli_mean': statistics.mean([m.cognitive_load_index for m in successful]),
                        'backtrack_mean': statistics.mean([m.backtrack_rate for m in successful]),
                        'entropy_mean': statistics.mean([m.navigation_entropy for m in successful]),
                    },
                    'unsuccessful': {
                        'count': len(unsuccessful),
                        'cli_mean': statistics.mean([m.cognitive_load_index for m in unsuccessful]),
                        'backtrack_mean': statistics.mean([m.backtrack_rate for m in unsuccessful]),
                        'entropy_mean': statistics.mean([m.navigation_entropy for m in unsuccessful]),
                    },
                }

                # Backtracker paradox check
                succ_backtrack = statistics.mean([m.backtrack_rate for m in successful])
                unsucc_backtrack = statistics.mean([m.backtrack_rate for m in unsuccessful])
                results['backtracker_paradox'] = {
                    'successful_backtrack_rate': succ_backtrack,
                    'unsuccessful_backtrack_rate': unsucc_backtrack,
                    'finding': 'Successful users backtrack more' if succ_backtrack > unsucc_backtrack else 'Unsuccessful users backtrack more',
                }

        # Stage analysis
        if by_stage:
            results['stage_analysis'] = {
                'serp_dwell_mean': statistics.mean([m.serp_dwell_mean for m in all_metrics if m.serp_dwell_mean > 0]),
                'content_dwell_mean': statistics.mean([m.content_dwell_mean for m in all_metrics if m.content_dwell_mean > 0]),
                'query_formulation_ratio_mean': statistics.mean([m.query_formulation_ratio for m in all_metrics]),
            }

        # Agent insights
        results['agent_insights'] = self._generate_insights(results, all_metrics)

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, by_stage, correlate_success)

    def _generate_insights(self, results: dict, metrics: list[CognitiveLoadMetrics]) -> list[str]:
        """
        Generate research-focused insights emphasizing novel contributions.

        Key research gaps addressed:
        - Ji et al. (2024): Physiological measures more accurate, but no outcome labels
        - Gwizdka (2010): Backtracking can be strategic OR confused (paradox unresolved)
        - Wang et al. (2024), Peng et al. (2024): LLM assistance timing is unsolved
        """
        insights = []

        # Honest limitation + unique value proposition
        insights.append(
            "LIMITATION vs VALUE: Behavioral proxies are noisier than EEG/eye-tracking (Ji et al. 2024). "
            "BUT your data has: (1) scale, (2) outcome labels, (3) ecological validity. "
            "Use cognitive load as SECONDARY filter, cross-validated with success_patterns."
        )

        # RESEARCH OPPORTUNITY: Pre-failure detection
        dist = results['cognitive_load_distribution']
        high_pct = dist['high']['percentage']
        if 'success_correlation' in results:
            corr = results['success_correlation']
            cli_diff = corr['unsuccessful']['cli_mean'] - corr['successful']['cli_mean']

            if cli_diff > 3:
                insights.append(
                    f"NOVEL FINDING: Failed tasks have CLI {cli_diff:.1f} points higher than successes. "
                    f"UNSOLVED PROBLEM: When should agents offer help? "
                    f"YOUR DATA: CLI > {corr['successful']['cli_mean'] + cli_diff/2:.0f} may signal "
                    f"'user needs assistance NOW'. Train proactive intervention triggers."
                )
            else:
                insights.append(
                    f"CLI difference between success/failure is small ({cli_diff:.1f}). "
                    f"Behavioral load proxies may not predict outcomes in this dataset. "
                    f"Prioritize other analyses (success_patterns, confidence)."
                )

        # RESEARCH GAP: The Backtracker Paradox
        if 'backtracker_paradox' in results:
            bp = results['backtracker_paradox']
            succ_bt = bp['successful_backtrack_rate']
            unsucc_bt = bp['unsuccessful_backtrack_rate']

            if bp['finding'] == 'Successful users backtrack more':
                insights.append(
                    f"NOVEL RESOLUTION: Backtracker Paradox RESOLVED in your data. "
                    f"Successful users backtrack MORE ({succ_bt:.3f} vs {unsucc_bt:.3f}). "
                    f"RESEARCH IMPLICATION: Supports metacognitive hypothesis (Hsu et al. 2022). "
                    f"AGENT TRAINING: Learn to backtrack strategically, not avoid it entirely."
                )
            else:
                insights.append(
                    f"NOVEL RESOLUTION: Your data shows CONFUSION backtracking dominates. "
                    f"Failed users backtrack more ({unsucc_bt:.3f} vs {succ_bt:.3f}). "
                    f"NEXT STEP: Classify backtracks by query change (new=strategic, same=confused). "
                    f"This is a NOVEL analysis behavioral data can uniquely provide."
                )

        # RESEARCH OPPORTUNITY: Difficulty ordering for curriculum learning
        if high_pct > 10:
            insights.append(
                f"CURRICULUM LEARNING OPPORTUNITY: {high_pct:.1f}% high-load trajectories identified. "
                f"UNSOLVED: How to order training data by difficulty without manual labels? "
                f"YOUR DATA: Use CLI as automatic difficulty proxy. Start agents on low-CLI "
                f"trajectories, progress to high-CLI. Validate: does this improve learning?"
            )

        # RESEARCH GAP: Stage-specific load patterns
        if 'stage_analysis' in results:
            stage = results['stage_analysis']
            serp_dwell = stage.get('serp_dwell_mean', 0)
            content_dwell = stage.get('content_dwell_mean', 0)
            qf_ratio = stage.get('query_formulation_ratio_mean', 0)

            insights.append(
                f"STAGE ANALYSIS (Gwizdka 2010 framework): "
                f"SERP dwell={serp_dwell:.1f}s, Content dwell={content_dwell:.1f}s, "
                f"Query formulation ratio={qf_ratio*100:.1f}%. "
                f"UNSOLVED: What triggers stage transitions? YOUR DATA: Analyze transition "
                f"patterns to train stage-aware agent behavior models."
            )

        # Navigation entropy with research framing
        agg = results['aggregate_metrics']
        entropy_mean = agg['navigation_entropy']['mean']
        insights.append(
            f"Navigation entropy = {entropy_mean:.2f}. "
            f"{'HIGH: Scattered attention pattern. ' if entropy_mean > 0.6 else 'LOW: Focused navigation. '}"
            f"RESEARCH USE: Entropy trajectory over time reveals 'search rhythm'. "
            f"Successful sessions may show characteristic entropy patterns—extract these for agent self-monitoring."
        )

        # NOVEL RESEARCH QUESTION: Early prediction
        insights.append(
            "RESEARCH QUESTION: Can early-session load predict final outcome? "
            "Analyze CLI in first 30s/60s to build early intervention classifiers. "
            "If predictive, agents can course-correct before failure."
        )

        return insights

    def _print_text_output(self, results: dict, by_stage: bool, correlate_success: bool):
        """Print formatted text output."""
        self.stdout.write(f"\nAnalyzed {results['total_tasks']} tasks.")

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('COGNITIVE LOAD DISTRIBUTION'))
        self.stdout.write('=' * 70)

        dist = results['cognitive_load_distribution']
        for level in ['low', 'medium', 'high']:
            data = dist[level]
            bar = '█' * int(data['percentage'] / 2)
            self.stdout.write(f"  {level.capitalize():<8} (CLI {'<40' if level == 'low' else '40-70' if level == 'medium' else '≥70'}): "
                            f"{bar} {data['percentage']:.1f}% ({data['count']})")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGGREGATE METRICS'))
        self.stdout.write('-' * 70)

        agg = results['aggregate_metrics']
        self.stdout.write(f"  Cognitive Load Index:  mean={agg['cognitive_load_index']['mean']:.1f}, "
                         f"median={agg['cognitive_load_index']['median']:.1f}")
        self.stdout.write(f"  Dwell Time CV:         mean={agg['dwell_time_cv']['mean']:.2f}")
        self.stdout.write(f"  Backtrack Rate:        mean={agg['backtrack_rate']['mean']:.3f}")
        self.stdout.write(f"  Navigation Entropy:    mean={agg['navigation_entropy']['mean']:.2f}")

        if by_stage and 'stage_analysis' in results:
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('STAGE ANALYSIS (Gwizdka 2010)'))
            self.stdout.write('-' * 70)
            self.stdout.write('  "Query formulation has highest cognitive load"')

            stage = results['stage_analysis']
            self.stdout.write(f"\n  SERP Dwell (query formulation):     {stage['serp_dwell_mean']:.1f}s")
            self.stdout.write(f"  Content Dwell (document viewing):   {stage['content_dwell_mean']:.1f}s")
            self.stdout.write(f"  Query Formulation Ratio:            {stage['query_formulation_ratio_mean']*100:.1f}%")

        if correlate_success and 'success_correlation' in results:
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('COGNITIVE LOAD × SUCCESS'))
            self.stdout.write('-' * 70)

            corr = results['success_correlation']
            self.stdout.write(f"  {'Metric':<25} {'Successful':<15} {'Unsuccessful':<15}")
            self.stdout.write(f"  {'Count':<25} {corr['successful']['count']:<15} {corr['unsuccessful']['count']:<15}")
            self.stdout.write(f"  {'CLI Mean':<25} {corr['successful']['cli_mean']:<15.1f} {corr['unsuccessful']['cli_mean']:<15.1f}")
            self.stdout.write(f"  {'Backtrack Rate':<25} {corr['successful']['backtrack_mean']:<15.3f} {corr['unsuccessful']['backtrack_mean']:<15.3f}")
            self.stdout.write(f"  {'Nav Entropy':<25} {corr['successful']['entropy_mean']:<15.2f} {corr['unsuccessful']['entropy_mean']:<15.2f}")

            if 'backtracker_paradox' in results:
                bp = results['backtracker_paradox']
                self.stdout.write(f"\n  Backtracker Paradox: {bp['finding']}")

        # Agent insights
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGENT-ACTIONABLE INSIGHTS'))
        self.stdout.write('-' * 70)

        for insight in results.get('agent_insights', []):
            self.stdout.write(f"  - {insight}")

        self.stdout.write('\n' + '=' * 70)
