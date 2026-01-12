"""
Success Pattern Analysis: Identifying What Makes Human Trajectories Valuable for Agent Training.

================================================================================
RESEARCH GAPS THIS ANALYSIS ADDRESSES
================================================================================

GAP 1: The Human-Agent Capability Transfer Problem
    Son et al. (2024, arXiv:2405.04497) identified THREE key human capabilities
    that current web agents LACK:

    1. KNOWLEDGE UPDATING: Humans modify their understanding based on what they
       observe during search. Agents don't.
    2. AMBIGUITY HANDLING: Humans explore and modify plans when facing unclear
       situations. Agents follow rigid plans.
    3. FAILURE INVESTIGATION: Humans investigate WHY something failed and adapt.
       Agents just retry or give up.

    >>> YOUR DATA CAN: Identify trajectories where users DEMONSTRATE these
        adaptive behaviors. Extract the behavioral signatures of knowledge
        updating (e.g., query pivots after reading content), ambiguity handling
        (e.g., exploratory detours), and failure recovery (e.g., backtrack +
        reformulation patterns).

GAP 2: The Quality-Over-Quantity Paradox
    Recent findings challenge the "more data is better" assumption:
    - PC Agent-E (He et al., 2025): 312 quality demos beat massive datasets
    - AdaptAgent (Verma et al., 2024): 1-2 demos = 21-65% relative improvement
    - GroundCUA (Feizi et al., 2025): <1/10 training data achieves SOTA

    BUT: What defines "quality"? Current work uses success labels, but this
    is insufficient—a lucky successful trajectory ≠ a skillful one.

    >>> YOUR DATA CAN: Define behavioral quality metrics beyond success/failure.
        Identify trajectories that succeed EFFICIENTLY (few queries, focused
        navigation) vs those that succeed ACCIDENTALLY (many queries, scattered).
        The former are better training data.

GAP 3: Automatic Trajectory Quality Assessment
    InSTA (Trabucco et al., 2025): LLM judges achieve 82.6% accuracy on
    trajectory success. But this is binary (success/fail).

    UNSOLVED: Multi-dimensional quality assessment. A trajectory can be:
    - Successful but inefficient (bad for training efficiency)
    - Unsuccessful but demonstrating good strategy (good for learning recovery)
    - Successful via shortcuts that don't generalize

    >>> YOUR DATA CAN: Develop a multi-dimensional quality taxonomy with
        behavioral features (efficiency, strategy coherence, recovery patterns)
        that goes beyond binary success labels.

GAP 4: When Do Humans Struggle? (Difficulty Detection)
    Agents need to recognize when they're struggling and adapt. Humans do this
    naturally. But we don't know: what behavioral signals indicate struggle
    that PRECEDE failure?

    >>> YOUR DATA CAN: Identify early-warning behavioral patterns (increased
        query rate, backtracking spikes, dwell time changes) that predict
        eventual failure. These signals could enable agent self-monitoring.

================================================================================
NOVEL RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: What behavioral signatures distinguish "skillful success" from "lucky success"?
    - Hypothesis: Skillful trajectories have lower query counts, more strategic
      reformulations (specialization > generalization), and coherent navigation.
    - Analysis: Compare behavioral profiles within successful trajectories.

Q2: Can we identify "recovery demonstrations" in unsuccessful trajectories?
    - Hypothesis: Some failed trajectories contain valuable recovery attempts
      that could teach agents failure-handling.
    - Analysis: Segment unsuccessful trajectories to find strategic pivots.

Q3: What behavioral features predict trajectory transferability to new domains?
    - Hypothesis: Trajectories with clear task decomposition patterns transfer
      better than domain-specific shortcuts.
    - Analysis: Cross-correlate features with task diversity.

Q4: How do expert vs novice users differ in information-seeking strategy?
    - Hölscher & Strube (2000) framework: expert patterns are more valuable.
    - Analysis: Cluster users by behavioral efficiency, compare strategies.

================================================================================
KEY DISCRIMINATING FEATURES (Ranked by Agent Training Value)
================================================================================

HIGH VALUE (directly trainable patterns):
1. Query refinement sequences (specialization vs generalization patterns)
2. Strategic backtracking (return to SERP with NEW query vs same query)
3. Information integration signals (dwell time on content → query change)

MEDIUM VALUE (filtering signals):
4. Query count efficiency (successful tasks with fewer queries)
5. Navigation coherence (low entropy = focused strategy)
6. SERP engagement depth (clicks per SERP visit)

DIAGNOSTIC VALUE (identify problematic trajectories):
7. Excessive repetition (same query, same pages)
8. Scattered navigation (high entropy without progress)
9. Abandonment patterns (task switching without resolution)

Usage:
    python manage.py analyze_success_patterns
    python manage.py analyze_success_patterns --format json
    python manage.py analyze_success_patterns --export-features features.csv
"""

import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from task_manager.models import Task, TaskTrial, Webpage


@dataclass
class TaskFeatures:
    """Behavioral features for a single task."""
    task_id: int
    user_id: int
    is_correct: Optional[bool]

    # Query behavior
    num_queries: int
    avg_query_length: float
    query_reformulations: int

    # Navigation efficiency
    num_pages: int
    num_unique_pages: int
    pages_per_query: float
    revisit_rate: float

    # Temporal patterns
    total_dwell_time: float
    avg_dwell_time: float
    dwell_time_cv: float  # coefficient of variation (std/mean)

    # SERP behavior
    serp_visits: int
    serp_return_rate: float  # how often returns to SERP after click
    clicks_per_serp: float

    # Exploration patterns
    num_unique_domains: int
    domain_concentration: float  # fraction of time on top domain
    max_depth: int
    backtrack_count: int

    # Efficiency score (composite)
    efficiency_score: float


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
    """Check if URL is a search engine results page."""
    return extract_query(url) is not None


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ''


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    try:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".lower().rstrip('/')
    except Exception:
        return url


def compute_task_features(task: Task, pages: list[Webpage], trials: list[TaskTrial]) -> Optional[TaskFeatures]:
    """Compute all behavioral features for a task."""
    if not pages:
        return None

    # Determine correctness
    is_correct = None
    if trials:
        final_trial = max(trials, key=lambda t: (t.num_trial, t.id))
        is_correct = final_trial.is_correct

    # Extract queries
    queries = []
    for p in pages:
        q = extract_query(p.url)
        if q and (not queries or queries[-1] != q):
            queries.append(q)

    num_queries = len(queries)
    avg_query_length = sum(len(q.split()) for q in queries) / len(queries) if queries else 0
    query_reformulations = max(0, num_queries - 1)

    # Navigation metrics
    num_pages = len(pages)
    normalized_urls = [normalize_url(p.url) for p in pages]
    unique_urls = set(normalized_urls)
    num_unique_pages = len(unique_urls)
    pages_per_query = num_pages / num_queries if num_queries > 0 else num_pages
    revisit_rate = 1 - (num_unique_pages / num_pages) if num_pages > 0 else 0

    # Temporal patterns
    dwell_times = [p.dwell_time / 1000.0 for p in pages if p.dwell_time]
    total_dwell_time = sum(dwell_times) if dwell_times else 0
    avg_dwell_time = statistics.mean(dwell_times) if dwell_times else 0
    dwell_time_cv = (
        statistics.stdev(dwell_times) / avg_dwell_time
        if len(dwell_times) > 1 and avg_dwell_time > 0
        else 0
    )

    # SERP behavior
    serp_visits = sum(1 for p in pages if is_serp(p.url))
    non_serp_after_serp = 0
    returns_to_serp = 0

    for i in range(len(pages) - 1):
        if is_serp(pages[i].url) and not is_serp(pages[i + 1].url):
            non_serp_after_serp += 1
        elif not is_serp(pages[i].url) and is_serp(pages[i + 1].url):
            returns_to_serp += 1

    serp_return_rate = returns_to_serp / non_serp_after_serp if non_serp_after_serp > 0 else 0
    clicks_per_serp = non_serp_after_serp / serp_visits if serp_visits > 0 else 0

    # Domain analysis
    domains = [get_domain(p.url) for p in pages if not is_serp(p.url)]
    unique_domains = set(d for d in domains if d)
    num_unique_domains = len(unique_domains)

    # Domain concentration (time on most visited domain)
    domain_counts = defaultdict(int)
    for d in domains:
        if d:
            domain_counts[d] += 1
    top_domain_count = max(domain_counts.values()) if domain_counts else 0
    domain_concentration = top_domain_count / len(domains) if domains else 0

    # Depth from SERP
    max_depth = 0
    current_depth = 0
    for p in pages:
        if is_serp(p.url):
            current_depth = 0
        else:
            current_depth += 1
            max_depth = max(max_depth, current_depth)

    # Backtracking (A->B->A patterns)
    backtrack_count = 0
    for i in range(len(normalized_urls) - 2):
        if normalized_urls[i] == normalized_urls[i + 2] and normalized_urls[i] != normalized_urls[i + 1]:
            backtrack_count += 1

    # Efficiency score (composite metric)
    # Based on literature: fewer queries, focused exploration, less backtracking
    efficiency_score = compute_efficiency_score(
        num_queries=num_queries,
        num_pages=num_pages,
        revisit_rate=revisit_rate,
        backtrack_count=backtrack_count,
        dwell_time_cv=dwell_time_cv,
        serp_return_rate=serp_return_rate,
    )

    return TaskFeatures(
        task_id=task.id,
        user_id=task.user_id,
        is_correct=is_correct,
        num_queries=num_queries,
        avg_query_length=avg_query_length,
        query_reformulations=query_reformulations,
        num_pages=num_pages,
        num_unique_pages=num_unique_pages,
        pages_per_query=pages_per_query,
        revisit_rate=revisit_rate,
        total_dwell_time=total_dwell_time,
        avg_dwell_time=avg_dwell_time,
        dwell_time_cv=dwell_time_cv,
        serp_visits=serp_visits,
        serp_return_rate=serp_return_rate,
        clicks_per_serp=clicks_per_serp,
        num_unique_domains=num_unique_domains,
        domain_concentration=domain_concentration,
        max_depth=max_depth,
        backtrack_count=backtrack_count,
        efficiency_score=efficiency_score,
    )


def compute_efficiency_score(
    num_queries: int,
    num_pages: int,
    revisit_rate: float,
    backtrack_count: int,
    dwell_time_cv: float,
    serp_return_rate: float,
) -> float:
    """
    Compute efficiency score based on literature findings.

    Literature benchmarks (successful vs unsuccessful):
    - Queries: 2.2 vs 5.1 (lower is better)
    - Fewer pages with higher precision
    - Less backtracking
    - Lower dwell time variance (focused attention)
    """
    score = 100.0

    # Query penalty (optimal ~2-3)
    if num_queries <= 3:
        pass  # no penalty
    elif num_queries <= 5:
        score -= 10
    else:
        score -= 20 + (num_queries - 5) * 3

    # Pages penalty (optimal varies, but 10+ suggests struggle)
    if num_pages <= 5:
        pass
    elif num_pages <= 10:
        score -= 5
    else:
        score -= 10 + (num_pages - 10) * 2

    # Revisit penalty (some revisiting is OK, excessive is bad)
    if revisit_rate > 0.3:
        score -= (revisit_rate - 0.3) * 30

    # Backtrack penalty
    score -= backtrack_count * 5

    # CV penalty (high variance = scattered attention)
    if dwell_time_cv > 1.5:
        score -= (dwell_time_cv - 1.5) * 10

    # SERP return rate (some return is OK, excessive is bad)
    if serp_return_rate > 0.5:
        score -= (serp_return_rate - 0.5) * 20

    return max(0, min(100, score))


def compare_groups(
    successful: list[TaskFeatures],
    unsuccessful: list[TaskFeatures],
    feature_name: str,
) -> dict:
    """Compare a feature between successful and unsuccessful groups."""
    succ_vals = [getattr(f, feature_name) for f in successful]
    fail_vals = [getattr(f, feature_name) for f in unsuccessful]

    succ_mean = statistics.mean(succ_vals) if succ_vals else 0
    fail_mean = statistics.mean(fail_vals) if fail_vals else 0

    diff = fail_mean - succ_mean
    effect_size = diff / statistics.stdev(succ_vals + fail_vals) if (succ_vals + fail_vals) and len(succ_vals + fail_vals) > 1 else 0

    return {
        'successful_mean': succ_mean,
        'unsuccessful_mean': fail_mean,
        'difference': diff,
        'effect_size': effect_size,  # Cohen's d approximation
        'direction': 'higher_is_worse' if diff > 0 else 'lower_is_worse' if diff < 0 else 'no_difference',
    }


class Command(BaseCommand):
    help = 'Analyzes behavioral differences between successful and unsuccessful search tasks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--export-features',
            type=str,
            default=None,
            help='Export per-task features to CSV file',
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
            default=2,
            help='Minimum pages per task (default: 2)',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        export_path = options['export_features']
        batch_size = options['batch_size']
        min_pages = options['min_pages']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Success Pattern Analysis: Identifying High-Value Training Trajectories'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. Human-Agent Capability Transfer (Son et al. 2024)')
            self.stdout.write('     - Humans: knowledge updating, ambiguity handling, failure investigation')
            self.stdout.write('     - Agents: LACK these capabilities')
            self.stdout.write('  2. Quality vs Quantity Paradox')
            self.stdout.write('     - 312 quality demos > massive noisy datasets (PC Agent-E)')
            self.stdout.write('     - 1-2 demos = 21-65% improvement (AdaptAgent)')
            self.stdout.write('  3. Automatic Quality Assessment')
            self.stdout.write('     - Current: Binary success/fail')
            self.stdout.write('     - Needed: Multi-dimensional quality metrics')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Define "skillful success" vs "lucky success"')
            self.stdout.write('               Extract behavioral signatures of human adaptive capabilities')
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

        all_features: list[TaskFeatures] = []

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

                features = compute_task_features(task, pages, trials)
                if features:
                    all_features.append(features)

        # Split by outcome
        successful = [f for f in all_features if f.is_correct is True]
        unsuccessful = [f for f in all_features if f.is_correct is False]
        unknown = [f for f in all_features if f.is_correct is None]

        if output_format == 'text':
            self.stdout.write(f'\nAnalyzed {len(all_features)} tasks.')
            self.stdout.write(f'  Successful: {len(successful)}')
            self.stdout.write(f'  Unsuccessful: {len(unsuccessful)}')
            self.stdout.write(f'  Unknown: {len(unknown)}')

        # Feature comparison
        features_to_compare = [
            ('num_queries', 'Number of Queries'),
            ('avg_query_length', 'Avg Query Length'),
            ('num_pages', 'Pages Visited'),
            ('pages_per_query', 'Pages per Query'),
            ('revisit_rate', 'Revisit Rate'),
            ('total_dwell_time', 'Total Dwell Time (s)'),
            ('dwell_time_cv', 'Dwell Time CV'),
            ('serp_visits', 'SERP Visits'),
            ('serp_return_rate', 'SERP Return Rate'),
            ('clicks_per_serp', 'Clicks per SERP'),
            ('num_unique_domains', 'Unique Domains'),
            ('domain_concentration', 'Domain Concentration'),
            ('max_depth', 'Max Depth from SERP'),
            ('backtrack_count', 'Backtrack Count'),
            ('efficiency_score', 'Efficiency Score'),
        ]

        comparisons = {}
        if successful and unsuccessful:
            for feature_name, label in features_to_compare:
                comparisons[feature_name] = {
                    'label': label,
                    **compare_groups(successful, unsuccessful, feature_name),
                }

        # Identify discriminating features (|effect size| > 0.3)
        discriminating = [
            (name, data) for name, data in comparisons.items()
            if abs(data.get('effect_size', 0)) > 0.3
        ]
        discriminating.sort(key=lambda x: abs(x[1]['effect_size']), reverse=True)

        # Build results
        results = {
            'total_tasks': len(all_features),
            'successful': len(successful),
            'unsuccessful': len(unsuccessful),
            'unknown': len(unknown),
            'feature_comparisons': comparisons,
            'discriminating_features': [
                {'feature': name, **data}
                for name, data in discriminating
            ],
            'agent_insights': self._generate_insights(comparisons, discriminating),
            'literature_benchmarks': {
                'queries_successful': 2.2,
                'queries_unsuccessful': 5.1,
                'source': 'Eye-tracking study (CHI proceedings)',
            },
        }

        # Export if requested
        if export_path:
            self._export_features(all_features, export_path)
            results['exported_to'] = export_path

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, comparisons, discriminating)

    def _generate_insights(self, comparisons: dict, discriminating: list) -> list[str]:
        """Generate research-focused insights on trajectory value for agent training."""
        insights = []

        # === NOVEL RESEARCH CONTRIBUTION: Skillful vs Lucky Success ===
        if 'efficiency_score' in comparisons and 'num_queries' in comparisons:
            eff_comp = comparisons['efficiency_score']
            query_comp = comparisons['num_queries']

            # Identify "skillful success" threshold
            skillful_threshold = eff_comp['successful_mean'] + 0.5 * (
                eff_comp['successful_mean'] - eff_comp['unsuccessful_mean']
            )
            insights.append(
                f"NOVEL METRIC - 'Skillful Success' threshold: efficiency > {skillful_threshold:.0f} "
                f"(above-average successful users). These trajectories demonstrate expert patterns."
            )

        # === RESEARCH GAP: Human-Agent Disparity Features ===
        if discriminating:
            top_features = [d[0] for d in discriminating[:3]]
            insights.append(
                f"TOP DISCRIMINATING FEATURES: {', '.join(top_features)}. "
                f"RESEARCH OPPORTUNITY: Do these features capture Son et al.'s (2024) human advantages "
                f"(knowledge updating, ambiguity handling)?"
            )

        # === ACTIONABLE: Trajectory Quality Filtering ===
        if 'backtrack_count' in comparisons:
            comp = comparisons['backtrack_count']
            if comp['difference'] > 0:
                direction = "more" if comp['difference'] > 0 else "less"
                insights.append(
                    f"BACKTRACKER ANALYSIS: Unsuccessful users backtrack {abs(comp['difference']):.1f} {direction}. "
                    f"NEXT STEP: Classify backtracks as strategic (new query) vs confused (same query) "
                    f"using analyze_query_evolution."
                )

        # === NOVEL: Efficiency as Quality Proxy ===
        if 'efficiency_score' in comparisons:
            comp = comparisons['efficiency_score']
            threshold = comp['successful_mean']
            gap = comp['successful_mean'] - comp['unsuccessful_mean']
            insights.append(
                f"QUALITY FILTER: efficiency_score >= {threshold:.0f} selects successful-like trajectories. "
                f"Gap = {gap:.1f} points (larger gap = more discriminative)."
            )

        # === RESEARCH IMPLICATION ===
        insights.append(
            "RESEARCH IMPLICATION: Use these features to define 'trajectory quality' beyond "
            "binary success. High efficiency + success = skillful demo. "
            "Low efficiency + success = lucky, less valuable for training."
        )

        # === CROSS-VALIDATION ===
        insights.append(
            "CROSS-VALIDATE: Compare with analyze_confidence (do well-calibrated users have higher efficiency?) "
            "and analyze_query_evolution (do efficient users have better reformulation patterns?)."
        )

        return insights

    def _export_features(self, features: list[TaskFeatures], path: str):
        """Export features to CSV."""
        if not features:
            return

        fieldnames = list(asdict(features[0]).keys())

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for feat in features:
                writer.writerow(asdict(feat))

    def _print_text_output(self, results: dict, comparisons: dict, discriminating: list):
        """Print formatted text output."""
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('FEATURE COMPARISON: SUCCESSFUL vs UNSUCCESSFUL'))
        self.stdout.write('=' * 70)

        if not comparisons:
            self.stdout.write('Insufficient data for comparison.')
            return

        # Literature comparison
        self.stdout.write('\nLiterature Benchmark (Eye-tracking study):')
        self.stdout.write('  Successful: 2.2 queries/session, Unsuccessful: 5.1 queries/session')

        if 'num_queries' in comparisons:
            comp = comparisons['num_queries']
            self.stdout.write(f'  Your data: Successful: {comp["successful_mean"]:.1f}, Unsuccessful: {comp["unsuccessful_mean"]:.1f}')

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(f"  {'Feature':<25} {'Successful':<12} {'Unsuccessful':<12} {'Diff':<10} {'Effect':<8}")
        self.stdout.write('-' * 70)

        for name, data in comparisons.items():
            label = data.get('label', name)[:25]
            succ = data['successful_mean']
            unsucc = data['unsuccessful_mean']
            diff = data['difference']
            effect = data['effect_size']

            # Format based on magnitude
            if abs(succ) < 10 and abs(unsucc) < 10:
                self.stdout.write(f"  {label:<25} {succ:<12.2f} {unsucc:<12.2f} {diff:+10.2f} {effect:+8.2f}")
            else:
                self.stdout.write(f"  {label:<25} {succ:<12.1f} {unsucc:<12.1f} {diff:+10.1f} {effect:+8.2f}")

        # Discriminating features
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('MOST DISCRIMINATING FEATURES (|effect| > 0.3)'))
        self.stdout.write('-' * 70)

        if discriminating:
            for name, data in discriminating:
                direction = '↑' if data['direction'] == 'higher_is_worse' else '↓'
                self.stdout.write(
                    f"  {direction} {data['label']}: effect size = {data['effect_size']:+.2f} "
                    f"({data['successful_mean']:.2f} vs {data['unsuccessful_mean']:.2f})"
                )
        else:
            self.stdout.write('  No strongly discriminating features found.')

        # Visual comparison
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('VISUAL: KEY METRICS (successful | unsuccessful)'))
        self.stdout.write('-' * 70)

        key_features = ['num_queries', 'num_pages', 'backtrack_count', 'efficiency_score']
        for feat in key_features:
            if feat in comparisons:
                data = comparisons[feat]
                succ_bar = '█' * int(min(20, data['successful_mean']))
                unsucc_bar = '█' * int(min(20, data['unsuccessful_mean']))
                self.stdout.write(f"  {data['label'][:20]:<20}")
                self.stdout.write(f"    Successful:   {succ_bar} ({data['successful_mean']:.1f})")
                self.stdout.write(f"    Unsuccessful: {unsucc_bar} ({data['unsuccessful_mean']:.1f})")

        # Agent insights
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGENT-ACTIONABLE INSIGHTS'))
        self.stdout.write('-' * 70)

        for insight in results.get('agent_insights', []):
            self.stdout.write(f"  - {insight}")

        if results.get('exported_to'):
            self.stdout.write(f"\n  Features exported to: {results['exported_to']}")

        self.stdout.write('\n' + '=' * 70)
