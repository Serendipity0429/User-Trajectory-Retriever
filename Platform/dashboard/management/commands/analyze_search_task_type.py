"""
Search Task Type Analysis: Understanding When Agents Need Different Strategies.

================================================================================
RESEARCH GAPS THIS ANALYSIS ADDRESSES
================================================================================

GAP 1: One-Size-Fits-All Agent Strategies
    Current web agents use the same strategy regardless of task type:
    - Same query generation approach
    - Same result evaluation criteria
    - Same stopping conditions

    But Marchionini (2006) showed fundamentally different information needs:
    - LOOKUP: Find specific fact → precision matters
    - LEARN: Understand topic → coverage matters
    - INVESTIGATE: Compare/synthesize → multiple sources matter

    UNSOLVED: How should agents ADAPT their strategy based on task type?

    >>> YOUR DATA CAN: Extract task-type-specific behavioral patterns.
        What query styles, navigation patterns, and stopping behaviors
        characterize each task type? Train task-adaptive agent policies.

GAP 2: The Exploratory Search Problem
    Medlar et al. (2023, arXiv:2312.13695) reviewed exploratory search studies:
    - 77% focus on SYSTEM evaluation, not USER behavior
    - Limited task diversity (mostly scientific literature)
    - Methodologies inconsistent

    Kaushik & Jones (2023): Standard digital assistants FAIL at exploratory
    search—they're designed for lookup only.

    UNSOLVED: What human behaviors enable successful exploratory search?
    Current agents lack exploratory capabilities because we don't understand
    what "good exploration" looks like behaviorally.

    >>> YOUR DATA CAN: Characterize exploratory search behavior in detail.
        What distinguishes successful exploration from aimless wandering?
        When do humans decide they've "learned enough"? What triggers the
        shift from exploration to exploitation?

GAP 3: Task Type Recognition from Behavior
    Agents need to INFER task type from user behavior to adapt strategy.
    Athukorala et al. (2016) identified indicators: query length, scroll depth,
    completion time.

    UNSOLVED: Can we build real-time task type classifiers from behavioral
    streams? Current work uses post-hoc analysis, not online prediction.

    >>> YOUR DATA CAN: Train task type classifiers from early-session behavior.
        Can task type be predicted from first 1-2 queries? First 30 seconds?
        This enables agents to adapt strategy before it's too late.

GAP 4: Cross-Session Task Continuity
    Hoeber et al. (2025): Users struggle to resume exploratory tasks across
    sessions. Timeline visualization helps.

    UNSOLVED: How do humans maintain context across sessions? What information
    do they re-access when resuming?

    >>> YOUR DATA CAN: If you have multi-session data, analyze:
        - What pages are revisited when resuming?
        - Do queries change between sessions?
        - What "warm-up" behavior precedes productive searching?
        This informs agent memory design for long-term tasks.

GAP 5: The Investigation Task Challenge
    Investigation tasks (compare, synthesize, decide) are hardest for agents:
    - Require holding multiple sources in "memory"
    - Require comparison across sources
    - Require synthesis into coherent conclusion

    UNSOLVED: What behavioral patterns enable human synthesis?

    >>> YOUR DATA CAN: Analyze investigation task trajectories:
        - How many sources do humans consult before deciding?
        - What revisitation patterns indicate comparison behavior?
        - How do humans signal they've reached a conclusion?

================================================================================
NOVEL RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: Can task type be predicted from initial query alone?
    - Features: query length, question words, specificity markers
    - Application: Immediate strategy selection for agents
    - Baseline: Athukorala's behavioral indicators

Q2: What behavioral signatures indicate task type transitions?
    - Sometimes tasks EVOLVE: lookup → learn (found fact, want context)
                              learn → investigate (understood topic, need to decide)
    - Identify: Behavioral markers of these transitions
    - Train: Agents to recognize and adapt to task evolution

Q3: What makes exploration "successful" vs "aimless"?
    - Contrast: Successful exploratory sessions vs abandoned ones
    - Features: Query diversity, navigation structure, dwell patterns
    - Define: Behavioral quality metrics for exploration

Q4: How do experts handle investigation tasks differently?
    - Hypothesis: Experts use systematic comparison patterns
    - Analyze: Navigation structure in investigation tasks by user expertise
    - Train: Expert investigation strategies into agents

Q5: What stopping criteria do humans use for each task type?
    - Lookup: Found specific answer (identifiable moment)
    - Learn: Saturated learning (diminishing returns behavior)
    - Investigate: Decision made (comparison completed)
    - Train: Task-type-specific stopping conditions

================================================================================
TASK TYPE PROFILES AND AGENT STRATEGY IMPLICATIONS
================================================================================

LOOKUP Tasks:
    Human behavior: Short queries, direct navigation, quick dwell, early stop
    Agent strategy: Prioritize precision, use answer extraction, stop on match
    Training focus: Answer identification, confidence in single source

LEARN Tasks:
    Human behavior: Evolving queries, breadth-first navigation, varied dwell
    Agent strategy: Prioritize coverage, track concepts learned, stop on saturation
    Training focus: Topic modeling, knowledge gap detection

INVESTIGATE Tasks:
    Human behavior: Multiple sources, comparison revisits, long dwell, late stop
    Agent strategy: Systematic comparison, evidence aggregation, synthesis
    Training focus: Multi-document reasoning, comparison frameworks

Usage:
    python manage.py analyze_search_task_type
    python manage.py analyze_search_task_type --format json
    python manage.py analyze_search_task_type --correlate-success
"""

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from task_manager.models import Task, TaskTrial, Webpage


@dataclass
class TaskBehaviorMetrics:
    """Behavioral metrics for task type classification."""
    task_id: int
    # Query metrics
    num_queries: int
    avg_query_length: float  # words per query
    query_reformulations: int

    # Navigation metrics
    num_pages: int
    num_unique_domains: int
    revisit_rate: float
    backtrack_count: int  # A->B->A patterns

    # Temporal metrics
    total_dwell_time: float  # seconds
    avg_dwell_time: float
    dwell_time_variance: float

    # Depth metrics
    max_depth: int  # from SERP
    serp_returns: int  # times returned to SERP

    # Classification
    task_type: str
    confidence_score: float


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


def classify_task_type(metrics: dict) -> tuple[str, float]:
    """
    Classify task type using Marchionini's framework.

    Based on behavioral indicators from Athukorala et al. (2016):
    - Query length, pages visited, dwell time, revisit rate
    """
    scores = {'lookup': 0.0, 'learn': 0.0, 'investigate': 0.0}

    # Query length (words) - lookup tends to be shorter
    avg_query_len = metrics.get('avg_query_length', 0)
    if avg_query_len <= 3:
        scores['lookup'] += 2.0
    elif avg_query_len <= 5:
        scores['learn'] += 1.0
    else:
        scores['investigate'] += 1.5

    # Number of pages - lookup is fewer
    num_pages = metrics.get('num_pages', 0)
    if num_pages <= 3:
        scores['lookup'] += 2.0
    elif num_pages <= 8:
        scores['learn'] += 1.5
    else:
        scores['investigate'] += 2.0

    # Revisit rate - investigate has more revisits
    revisit_rate = metrics.get('revisit_rate', 0)
    if revisit_rate <= 0.1:
        scores['lookup'] += 1.0
    elif revisit_rate <= 0.25:
        scores['learn'] += 1.0
    else:
        scores['investigate'] += 2.0

    # Total dwell time - lookup is quick
    total_dwell = metrics.get('total_dwell_time', 0)
    if total_dwell <= 60:  # < 1 minute
        scores['lookup'] += 2.0
    elif total_dwell <= 300:  # < 5 minutes
        scores['learn'] += 1.5
    else:
        scores['investigate'] += 2.0

    # Number of unique domains - more diversity = more exploratory
    num_domains = metrics.get('num_unique_domains', 0)
    if num_domains <= 2:
        scores['lookup'] += 1.0
    elif num_domains <= 5:
        scores['learn'] += 1.5
    else:
        scores['investigate'] += 2.0

    # SERP returns - more returns = exploratory
    serp_returns = metrics.get('serp_returns', 0)
    if serp_returns <= 1:
        scores['lookup'] += 1.0
    elif serp_returns <= 3:
        scores['learn'] += 1.5
    else:
        scores['investigate'] += 2.0

    # Number of query reformulations
    reformulations = metrics.get('query_reformulations', 0)
    if reformulations == 0:
        scores['lookup'] += 1.5
    elif reformulations <= 2:
        scores['learn'] += 1.0
    else:
        scores['investigate'] += 1.5

    # Backtrack count (A->B->A patterns)
    backtracks = metrics.get('backtrack_count', 0)
    if backtracks == 0:
        scores['lookup'] += 0.5
    elif backtracks <= 2:
        scores['learn'] += 0.5
    else:
        scores['investigate'] += 1.5

    # Determine winner
    total = sum(scores.values())
    if total == 0:
        return 'unknown', 0.0

    max_type = max(scores, key=scores.get)
    confidence = scores[max_type] / total

    return max_type, confidence


def analyze_task(task: Task, pages: list[Webpage]) -> Optional[TaskBehaviorMetrics]:
    """Analyze a single task and compute behavioral metrics."""
    if not pages:
        return None

    # Extract queries
    queries = []
    for p in pages:
        q = extract_query(p.url)
        if q and (not queries or queries[-1] != q):
            queries.append(q)

    # Calculate query metrics
    num_queries = len(queries)
    avg_query_length = (
        sum(len(q.split()) for q in queries) / len(queries)
        if queries else 0
    )
    query_reformulations = max(0, num_queries - 1)

    # Navigation metrics
    num_pages = len(pages)
    domains = [get_domain(p.url) for p in pages]
    unique_domains = set(d for d in domains if d)
    num_unique_domains = len(unique_domains)

    # URL-based revisit tracking
    urls_normalized = []
    for p in pages:
        try:
            parsed = urlparse(p.url)
            normalized = f"{parsed.netloc}{parsed.path}".lower()
            urls_normalized.append(normalized)
        except Exception:
            urls_normalized.append(p.url)

    unique_urls = set(urls_normalized)
    revisit_rate = 1 - (len(unique_urls) / len(urls_normalized)) if urls_normalized else 0

    # Backtrack patterns (A->B->A)
    backtrack_count = 0
    for i in range(len(urls_normalized) - 2):
        if urls_normalized[i] == urls_normalized[i + 2] and urls_normalized[i] != urls_normalized[i + 1]:
            backtrack_count += 1

    # Temporal metrics
    dwell_times = [p.dwell_time / 1000.0 for p in pages if p.dwell_time]  # ms to seconds
    total_dwell_time = sum(dwell_times) if dwell_times else 0
    avg_dwell_time = statistics.mean(dwell_times) if dwell_times else 0
    dwell_time_variance = statistics.variance(dwell_times) if len(dwell_times) > 1 else 0

    # SERP analysis
    serp_indices = [i for i, p in enumerate(pages) if is_serp(p.url)]
    serp_returns = len(serp_indices) - 1 if serp_indices else 0  # -1 for initial SERP

    # Calculate max depth from SERP
    max_depth = 0
    current_depth = 0
    for p in pages:
        if is_serp(p.url):
            current_depth = 0
        else:
            current_depth += 1
            max_depth = max(max_depth, current_depth)

    # Build metrics dict for classification
    metrics_dict = {
        'avg_query_length': avg_query_length,
        'num_pages': num_pages,
        'revisit_rate': revisit_rate,
        'total_dwell_time': total_dwell_time,
        'num_unique_domains': num_unique_domains,
        'serp_returns': serp_returns,
        'query_reformulations': query_reformulations,
        'backtrack_count': backtrack_count,
    }

    task_type, confidence = classify_task_type(metrics_dict)

    return TaskBehaviorMetrics(
        task_id=task.id,
        num_queries=num_queries,
        avg_query_length=avg_query_length,
        query_reformulations=query_reformulations,
        num_pages=num_pages,
        num_unique_domains=num_unique_domains,
        revisit_rate=revisit_rate,
        backtrack_count=backtrack_count,
        total_dwell_time=total_dwell_time,
        avg_dwell_time=avg_dwell_time,
        dwell_time_variance=dwell_time_variance,
        max_depth=max_depth,
        serp_returns=serp_returns,
        task_type=task_type,
        confidence_score=confidence,
    )


class Command(BaseCommand):
    help = "Classifies search tasks using Marchionini's (2006) lookup/learn/investigate taxonomy."

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--correlate-success',
            action='store_true',
            help='Correlate task type with success rate',
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
        correlate_success = options['correlate_success']
        batch_size = options['batch_size']
        min_pages = options['min_pages']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS("Search Task Type: When Agents Need Different Strategies"))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. One-Size-Fits-All Agent Strategies')
            self.stdout.write('     - Current agents: same strategy regardless of task type')
            self.stdout.write('     - Needed: LOOKUP=precision, LEARN=coverage, INVESTIGATE=synthesis')
            self.stdout.write('  2. Exploratory Search Failure (Medlar 2023, Kaushik 2023)')
            self.stdout.write('     - 77% of studies focus on systems, not user behavior')
            self.stdout.write('     - Digital assistants FAIL at exploratory search')
            self.stdout.write('  3. Real-time Task Type Recognition')
            self.stdout.write('     - Agents need to INFER task type to adapt')
            self.stdout.write('     - Current: post-hoc analysis, not online prediction')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Train task-type classifiers from early behavior')
            self.stdout.write('               Characterize what makes exploration "successful"')
            self.stdout.write('               Extract task-type-specific stopping criteria')
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

        # Results storage
        all_metrics: list[TaskBehaviorMetrics] = []
        type_counts = Counter()
        type_success = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'unknown': 0})

        # Aggregated metrics by type
        type_aggregates = defaultdict(lambda: {
            'num_queries': [],
            'avg_query_length': [],
            'num_pages': [],
            'total_dwell_time': [],
            'revisit_rate': [],
            'num_unique_domains': [],
            'max_depth': [],
            'serp_returns': [],
        })

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

                if len(pages) < min_pages:
                    continue

                metrics = analyze_task(task, pages)
                if not metrics:
                    continue

                all_metrics.append(metrics)
                type_counts[metrics.task_type] += 1

                # Aggregate metrics by type
                agg = type_aggregates[metrics.task_type]
                agg['num_queries'].append(metrics.num_queries)
                agg['avg_query_length'].append(metrics.avg_query_length)
                agg['num_pages'].append(metrics.num_pages)
                agg['total_dwell_time'].append(metrics.total_dwell_time)
                agg['revisit_rate'].append(metrics.revisit_rate)
                agg['num_unique_domains'].append(metrics.num_unique_domains)
                agg['max_depth'].append(metrics.max_depth)
                agg['serp_returns'].append(metrics.serp_returns)

                # Success correlation
                if correlate_success:
                    trials = list(task.tasktrial_set.all())
                    if trials:
                        final_trial = max(trials, key=lambda t: (t.num_trial, t.id))
                        if final_trial.is_correct is True:
                            type_success[metrics.task_type]['correct'] += 1
                        elif final_trial.is_correct is False:
                            type_success[metrics.task_type]['incorrect'] += 1
                        else:
                            type_success[metrics.task_type]['unknown'] += 1
                    else:
                        type_success[metrics.task_type]['unknown'] += 1

        # Build results
        total_classified = len(all_metrics)
        results = {
            'total_tasks': total_classified,
            'type_distribution': {},
            'type_profiles': {},
            'agent_insights': {},
        }

        for task_type in ['lookup', 'learn', 'investigate', 'unknown']:
            count = type_counts.get(task_type, 0)
            pct = count / total_classified * 100 if total_classified > 0 else 0
            results['type_distribution'][task_type] = {
                'count': count,
                'percentage': pct,
            }

            # Compute profile statistics
            if task_type in type_aggregates and type_aggregates[task_type]['num_pages']:
                agg = type_aggregates[task_type]
                results['type_profiles'][task_type] = {
                    'avg_queries': statistics.mean(agg['num_queries']) if agg['num_queries'] else 0,
                    'avg_query_length': statistics.mean(agg['avg_query_length']) if agg['avg_query_length'] else 0,
                    'avg_pages': statistics.mean(agg['num_pages']) if agg['num_pages'] else 0,
                    'avg_dwell_time': statistics.mean(agg['total_dwell_time']) if agg['total_dwell_time'] else 0,
                    'avg_revisit_rate': statistics.mean(agg['revisit_rate']) if agg['revisit_rate'] else 0,
                    'avg_domains': statistics.mean(agg['num_unique_domains']) if agg['num_unique_domains'] else 0,
                    'avg_max_depth': statistics.mean(agg['max_depth']) if agg['max_depth'] else 0,
                    'avg_serp_returns': statistics.mean(agg['serp_returns']) if agg['serp_returns'] else 0,
                }

        # Success correlation
        if correlate_success:
            results['success_by_type'] = {}
            for task_type, outcomes in type_success.items():
                known = outcomes['correct'] + outcomes['incorrect']
                accuracy = outcomes['correct'] / known * 100 if known > 0 else None
                results['success_by_type'][task_type] = {
                    'correct': outcomes['correct'],
                    'incorrect': outcomes['incorrect'],
                    'unknown': outcomes['unknown'],
                    'accuracy_when_known': accuracy,
                }

        # Agent insights
        results['agent_insights'] = self._generate_insights(results, type_counts, total_classified)

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, correlate_success)

    def _generate_insights(self, results, type_counts, total):
        """
        Generate research-focused insights emphasizing novel contributions.

        Key research gaps addressed:
        - Medlar et al. (2023): 77% of exploratory search studies focus on systems, not user behavior
        - Kaushik & Jones (2023): Digital assistants FAIL at exploratory search
        - Athukorala et al. (2016): Task type indicators exist but no real-time classifiers
        """
        insights = []

        lookup_pct = type_counts.get('lookup', 0) / total * 100 if total > 0 else 0
        learn_pct = type_counts.get('learn', 0) / total * 100 if total > 0 else 0
        investigate_pct = type_counts.get('investigate', 0) / total * 100 if total > 0 else 0

        # NOVEL CONTRIBUTION: Task type behavioral signatures
        insights.append(
            f"NOVEL DATA: Behavioral task type distribution (n={total}): "
            f"Lookup={lookup_pct:.1f}%, Learn={learn_pct:.1f}%, Investigate={investigate_pct:.1f}%. "
            f"Medlar et al. (2023) notes 77% of studies lack this behavioral-level analysis."
        )

        # Profile-based insights with research framing
        profiles = results.get('type_profiles', {})

        # RESEARCH OPPORTUNITY: Task-type-specific stopping criteria
        if 'lookup' in profiles and 'investigate' in profiles:
            lookup_dwell = profiles['lookup'].get('avg_dwell_time', 0)
            investigate_dwell = profiles['investigate'].get('avg_dwell_time', 0)
            lookup_pages = profiles['lookup'].get('avg_pages', 0)
            investigate_pages = profiles['investigate'].get('avg_pages', 0)

            if investigate_dwell > lookup_dwell:
                insights.append(
                    f"UNSOLVED PROBLEM: Task-specific stopping criteria. "
                    f"Lookup: {lookup_dwell:.0f}s/{lookup_pages:.1f} pages vs "
                    f"Investigate: {investigate_dwell:.0f}s/{investigate_pages:.1f} pages. "
                    f"AGENT TRAINING: These ratios define type-specific termination thresholds."
                )

        # RESEARCH GAP: Exploratory search failure
        if learn_pct + investigate_pct > 30:
            insights.append(
                f"RESEARCH GAP: {learn_pct + investigate_pct:.1f}% exploratory tasks (learn+investigate). "
                f"Kaushik & Jones (2023): Standard digital assistants FAIL at exploratory search. "
                f"YOUR DATA: Extract what behavioral patterns ENABLE successful exploration."
            )

        # NOVEL METRIC: Query evolution by task type
        if 'lookup' in profiles and 'learn' in profiles:
            lookup_reformulations = profiles.get('lookup', {}).get('avg_queries', 1) - 1
            learn_reformulations = profiles.get('learn', {}).get('avg_queries', 1) - 1

            if learn_reformulations > lookup_reformulations:
                insights.append(
                    f"NOVEL FINDING: Learn tasks have {learn_reformulations:.1f} reformulations vs "
                    f"Lookup's {lookup_reformulations:.1f}. AGENT TRAINING: Use reformulation count "
                    f"as online task-type classifier (Athukorala et al. indicator)."
                )

        # Success correlation with research implications
        success = results.get('success_by_type', {})
        if success:
            accuracies = {
                k: v['accuracy_when_known']
                for k, v in success.items()
                if v.get('accuracy_when_known') is not None
            }
            if accuracies and len(accuracies) > 1:
                best_type = max(accuracies, key=accuracies.get)
                worst_type = min(accuracies, key=accuracies.get)
                gap = accuracies[best_type] - accuracies[worst_type]

                if gap > 10:
                    insights.append(
                        f"RESEARCH OPPORTUNITY: '{worst_type}' tasks at {accuracies[worst_type]:.1f}% "
                        f"vs '{best_type}' at {accuracies[best_type]:.1f}% ({gap:.1f}% gap). "
                        f"UNSOLVED: Why do agents struggle with {worst_type} tasks? "
                        f"YOUR DATA: Extract {worst_type}-specific failure patterns for targeted improvement."
                    )
                else:
                    insights.append(
                        f"Task type has modest success impact ({gap:.1f}% spread). "
                        f"Other factors (query quality, domain) may be more predictive."
                    )

        # RESEARCH GAP: Real-time task classification
        insights.append(
            "UNSOLVED PROBLEM: Real-time task type recognition. "
            "Current methods use post-hoc analysis. YOUR DATA CAN: Train classifiers from "
            "first query features (length, question words) for immediate strategy selection."
        )

        # Investigation task challenge
        if investigate_pct > 15:
            insights.append(
                f"HARDEST CHALLENGE: Investigation tasks ({investigate_pct:.1f}%) require "
                f"multi-source synthesis. Agents lack: (1) working memory for comparison, "
                f"(2) evidence aggregation, (3) synthesis stopping criteria. "
                f"YOUR DATA: How many sources do humans consult before deciding?"
            )

        return insights

    def _print_text_output(self, results, correlate_success):
        """Print formatted text output."""
        self.stdout.write(f"\nClassified {results['total_tasks']} tasks.")

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('TASK TYPE DISTRIBUTION'))
        self.stdout.write('=' * 70)

        for task_type in ['lookup', 'learn', 'investigate', 'unknown']:
            data = results['type_distribution'].get(task_type, {})
            count = data.get('count', 0)
            pct = data.get('percentage', 0)
            bar = '█' * int(pct / 2) + '░' * (50 - int(pct / 2))
            self.stdout.write(f"  {task_type:<12} {bar[:30]} {pct:5.1f}% ({count})")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('BEHAVIORAL PROFILES BY TYPE'))
        self.stdout.write('-' * 70)

        header = f"  {'Type':<12} {'Queries':<8} {'Q.Len':<8} {'Pages':<8} {'Dwell(s)':<10} {'Revisit':<8} {'Domains':<8}"
        self.stdout.write(header)

        for task_type in ['lookup', 'learn', 'investigate']:
            profile = results['type_profiles'].get(task_type, {})
            self.stdout.write(
                f"  {task_type:<12} "
                f"{profile.get('avg_queries', 0):<8.1f} "
                f"{profile.get('avg_query_length', 0):<8.1f} "
                f"{profile.get('avg_pages', 0):<8.1f} "
                f"{profile.get('avg_dwell_time', 0):<10.1f} "
                f"{profile.get('avg_revisit_rate', 0):<8.2f} "
                f"{profile.get('avg_domains', 0):<8.1f}"
            )

        if correlate_success and results.get('success_by_type'):
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('SUCCESS RATE BY TASK TYPE'))
            self.stdout.write('-' * 70)
            self.stdout.write(f"  {'Type':<12} {'Accuracy':<10} {'Correct':<10} {'Incorrect':<10}")

            for task_type in ['lookup', 'learn', 'investigate']:
                data = results['success_by_type'].get(task_type, {})
                acc = data.get('accuracy_when_known')
                acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
                self.stdout.write(
                    f"  {task_type:<12} {acc_str:<10} "
                    f"{data.get('correct', 0):<10} {data.get('incorrect', 0):<10}"
                )

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGENT-ACTIONABLE INSIGHTS'))
        self.stdout.write('-' * 70)

        for insight in results.get('agent_insights', []):
            self.stdout.write(f"  - {insight}")

        self.stdout.write('\n' + '=' * 70)
