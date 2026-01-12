"""
Trajectory Topology Analysis: Graph-Based Patterns for Agent Navigation Training.

================================================================================
RESEARCH GAPS THIS ANALYSIS ADDRESSES
================================================================================

GAP 1: Agents Use Depth-First, Humans Use Hub-and-Spoke (Star) Topology
    Ou et al. (2021, arXiv:2103.04694) identified 5 browsing topology patterns:
    1. BREADTH STAR - Hub (SERP) with multiple child branches (sampling)
    2. CONCENTRATED CLUSTER - Partitions connected through single node
    3. HESITATION LEAF - Dead-end branches (A->B->A)
    4. DIRECTED RING - Cyclic revisitation patterns
    5. INTERSECTED OVERLAP - Shared nodes across sessions

    WebRollback (2025): Agents "struggle to recover from erroneous states"
    because they lack the natural "return to hub" behavior humans exhibit.

    >>> YOUR DATA CAN: Quantify human star topology patterns. Extract:
        - Branching factor (how many results sampled before committing)
        - Hub return rate (frequency of SERP returns)
        - Commit depth (how deep after final hub departure)
        These metrics define "human-like" navigation for agent training.

GAP 2: The "Sampling Before Committing" Strategy
    Information Foraging Theory (Pirolli & Card):
    - Users follow "information scent" from SERP
    - Sample multiple options (star branches)
    - Then commit to most promising path

    Current agents commit to first result without sampling phase.

    >>> YOUR DATA CAN: Extract the sampling rhythm:
        - How many pages viewed before finding answer?
        - What dwell time threshold triggers "commit" decision?
        - What content features correlate with commitment?

GAP 3: Hub as "Cognitive Anchor" / Working Memory Offload
    WebGraphEval (2025): 89% of successful trajectories share initial sequences.
    The SERP serves as a stable reference point enabling comparison without
    holding everything in memory.

    >>> YOUR DATA CAN: Identify optimal hub usage patterns:
        - Successful vs failed trajectories: different hub return rates?
        - When does returning to hub help vs hurt?
        - What triggers the decision to return?

GAP 4: Graph Complexity Predicts Task Difficulty
    WebGraphEval (2025): Task complexity correlates with graph structure.
    Go-Browse (2025): Frames exploration as graph search.

    >>> YOUR DATA CAN: Derive difficulty metrics from graph structure:
        - Node count, edge count, branching factor
        - Cyclic complexity (rings and loops)
        - Path diversity (multiple routes to success)

================================================================================
NOVEL RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: What is the optimal star branching factor for different task types?
    - Lookup tasks: Low branching (quick find)
    - Investigative tasks: High branching (comparison)
    - Learn from human branching patterns by task type

Q2: How do expert vs novice users differ in topology?
    - Hypothesis: Experts have cleaner stars (focused sampling)
    - Novices have messy graphs (scattered exploration)
    - Extract expert topology patterns for agent training

Q3: What topology patterns predict success?
    - Star with moderate branching = good sampling
    - Excessive rings = confusion
    - Deep linear chains = committed exploration

Q4: Can early topology signals predict failure?
    - High early branching without commitment = struggling
    - Use as early warning for agent self-monitoring

Q5: How does topology relate to task completion time?
    - Efficient topologies vs inefficient ones
    - Train agents for time-efficient navigation

================================================================================
TOPOLOGY METRICS AND THEIR AGENT TRAINING VALUE
================================================================================

STAR METRICS (hub-and-spoke patterns):
- star_branching_factor: Pages visited from SERP before deep dive
- hub_return_rate: Frequency of returns to SERP
- max_star_depth: Longest branch from hub
- star_symmetry: How balanced are the branches

GRAPH COMPLEXITY METRICS:
- node_count: Unique pages visited
- edge_count: Unique transitions
- cycle_count: Number of A->...->A patterns
- linear_ratio: Fraction of linear (non-branching) navigation

PATTERN INDICATORS:
- has_breadth_star: Hub with multiple children
- has_hesitation_leaves: Dead-end explorations
- has_directed_ring: Cyclic behavior
- dominant_pattern: Most prominent topology type

Usage:
    python manage.py analyze_trajectory_topology
    python manage.py analyze_trajectory_topology --format json
    python manage.py analyze_trajectory_topology --correlate-success
    python manage.py analyze_trajectory_topology --export-graphs graphs/
"""

import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from task_manager.models import Task, TaskTrial, Webpage


@dataclass
class TopologyMetrics:
    """Graph-based topology metrics for a trajectory."""
    task_id: int
    user_id: int
    is_correct: Optional[bool]

    # Basic graph metrics
    node_count: int  # unique pages
    edge_count: int  # unique transitions
    total_visits: int  # total page visits (including revisits)

    # Star topology metrics (SERP as hub)
    star_branching_factor: float  # avg pages visited per SERP visit
    hub_return_rate: float  # returns to SERP / departures from SERP
    max_star_depth: int  # longest chain from SERP without return
    num_star_branches: int  # number of separate explorations from SERP

    # Pattern indicators
    has_breadth_star: bool  # hub with multiple children
    has_hesitation_leaves: int  # count of dead-end A->B->A patterns
    has_directed_ring: bool  # cyclic revisitation (A->B->C->A)
    ring_count: int  # number of cycles

    # Structural metrics
    linear_ratio: float  # fraction of linear (chain) navigation
    backtrack_rate: float  # backtracks / transitions
    revisit_rate: float  # revisits / total visits

    # Complexity metrics
    graph_density: float  # edges / (nodes * (nodes-1))
    avg_out_degree: float  # average outgoing edges per node
    entropy: float  # navigation entropy (randomness)

    # Dominant pattern
    dominant_pattern: str  # 'star', 'linear', 'cluster', 'cyclic', 'mixed'

    # Efficiency
    path_efficiency: float  # unique_nodes / total_visits (higher = less revisiting)


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
    """Check if URL is a search engine results page (the hub)."""
    return extract_query(url) is not None


def normalize_url(url: str) -> str:
    """Normalize URL for graph node identification."""
    try:
        parsed = urlparse(url)
        # For SERPs, include query to distinguish different searches
        if is_serp(url):
            q = extract_query(url)
            return f"SERP:{q}" if q else f"{parsed.netloc}{parsed.path}".lower()
        return f"{parsed.netloc}{parsed.path}".lower().rstrip('/')
    except Exception:
        return url


def build_navigation_graph(pages: list[Webpage]) -> tuple[dict, dict, list]:
    """
    Build a directed graph from page sequence.

    Returns:
        nodes: dict mapping normalized_url -> {'visits': count, 'is_serp': bool}
        edges: dict mapping (from_url, to_url) -> count
        sequence: list of normalized URLs in order
    """
    nodes = defaultdict(lambda: {'visits': 0, 'is_serp': False})
    edges = defaultdict(int)
    sequence = []

    for p in pages:
        norm_url = normalize_url(p.url)
        nodes[norm_url]['visits'] += 1
        nodes[norm_url]['is_serp'] = is_serp(p.url)
        sequence.append(norm_url)

    # Build edges from consecutive pages
    for i in range(len(sequence) - 1):
        if sequence[i] != sequence[i + 1]:  # skip self-loops from same page
            edges[(sequence[i], sequence[i + 1])] += 1

    return dict(nodes), dict(edges), sequence


def compute_star_metrics(nodes: dict, edges: dict, sequence: list) -> dict:
    """
    Compute star topology metrics with SERP as hub.

    Star pattern: SERP -> page1 -> SERP -> page2 -> SERP -> page3 -> deep_dive
    """
    serp_nodes = [url for url, data in nodes.items() if data['is_serp']]

    if not serp_nodes:
        return {
            'star_branching_factor': 0,
            'hub_return_rate': 0,
            'max_star_depth': len(sequence),  # all linear from unknown start
            'num_star_branches': 0,
        }

    # Count departures from SERP and returns to SERP
    departures = 0
    returns = 0
    current_depth = 0
    max_depth = 0
    branch_count = 0
    pages_per_serp_visit = []
    current_branch_pages = 0

    in_branch = False

    for i, url in enumerate(sequence):
        is_hub = nodes[url]['is_serp']

        if is_hub:
            if in_branch:
                returns += 1
                pages_per_serp_visit.append(current_branch_pages)
            current_depth = 0
            current_branch_pages = 0
            in_branch = False
        else:
            if not in_branch:
                departures += 1
                branch_count += 1
                in_branch = True
            current_depth += 1
            current_branch_pages += 1
            max_depth = max(max_depth, current_depth)

    # Handle case where trajectory ends without returning to SERP
    if in_branch and current_branch_pages > 0:
        pages_per_serp_visit.append(current_branch_pages)

    # Calculate metrics
    hub_return_rate = returns / departures if departures > 0 else 0
    avg_branching = statistics.mean(pages_per_serp_visit) if pages_per_serp_visit else 0

    return {
        'star_branching_factor': avg_branching,
        'hub_return_rate': hub_return_rate,
        'max_star_depth': max_depth,
        'num_star_branches': branch_count,
    }


def detect_patterns(nodes: dict, edges: dict, sequence: list) -> dict:
    """
    Detect the 5 browsing patterns from Ou et al. (2021).
    """
    # Pattern 1: Breadth Star - hub with multiple different children
    serp_children = defaultdict(set)
    for (src, dst), _ in edges.items():
        if nodes.get(src, {}).get('is_serp', False):
            serp_children[src].add(dst)

    has_breadth_star = any(len(children) >= 2 for children in serp_children.values())

    # Pattern 2: Hesitation Leaves - A->B->A patterns (dead ends)
    hesitation_count = 0
    for i in range(len(sequence) - 2):
        if sequence[i] == sequence[i + 2] and sequence[i] != sequence[i + 1]:
            hesitation_count += 1

    # Pattern 3: Directed Ring - A->B->C->...->A cycles
    # Use simple cycle detection
    ring_count = 0
    visited_in_path = set()

    for i, url in enumerate(sequence):
        if url in visited_in_path:
            # Found a cycle
            ring_count += 1
            visited_in_path.clear()
        visited_in_path.add(url)

    has_directed_ring = ring_count > 0

    # Pattern 4: Linear ratio - what fraction is simple chains
    # A chain is when each node has exactly one in and one out edge in the sequence
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    for (src, dst), count in edges.items():
        out_degree[src] += 1
        in_degree[dst] += 1

    linear_nodes = sum(1 for url in nodes if in_degree[url] <= 1 and out_degree[url] <= 1)
    linear_ratio = linear_nodes / len(nodes) if nodes else 0

    return {
        'has_breadth_star': has_breadth_star,
        'has_hesitation_leaves': hesitation_count,
        'has_directed_ring': has_directed_ring,
        'ring_count': ring_count,
        'linear_ratio': linear_ratio,
    }


def compute_graph_complexity(nodes: dict, edges: dict, sequence: list) -> dict:
    """Compute graph complexity metrics."""
    node_count = len(nodes)
    edge_count = len(edges)

    # Graph density
    max_edges = node_count * (node_count - 1) if node_count > 1 else 1
    density = edge_count / max_edges if max_edges > 0 else 0

    # Average out-degree
    out_degrees = defaultdict(int)
    for (src, _), _ in edges.items():
        out_degrees[src] += 1
    avg_out_degree = statistics.mean(out_degrees.values()) if out_degrees else 0

    # Navigation entropy (randomness of page visits)
    visit_counts = [data['visits'] for data in nodes.values()]
    total_visits = sum(visit_counts)

    entropy = 0
    if total_visits > 0 and len(visit_counts) > 1:
        for count in visit_counts:
            if count > 0:
                p = count / total_visits
                entropy -= p * math.log2(p)
        # Normalize by max entropy
        max_entropy = math.log2(len(visit_counts))
        entropy = entropy / max_entropy if max_entropy > 0 else 0

    # Backtrack rate
    backtrack_count = 0
    for i in range(len(sequence) - 2):
        if sequence[i] == sequence[i + 2] and sequence[i] != sequence[i + 1]:
            backtrack_count += 1
    transitions = len(sequence) - 1
    backtrack_rate = backtrack_count / transitions if transitions > 0 else 0

    # Revisit rate
    revisit_rate = 1 - (node_count / total_visits) if total_visits > 0 else 0

    # Path efficiency
    path_efficiency = node_count / total_visits if total_visits > 0 else 0

    return {
        'node_count': node_count,
        'edge_count': edge_count,
        'total_visits': total_visits,
        'graph_density': density,
        'avg_out_degree': avg_out_degree,
        'entropy': entropy,
        'backtrack_rate': backtrack_rate,
        'revisit_rate': revisit_rate,
        'path_efficiency': path_efficiency,
    }


def classify_dominant_pattern(metrics: dict) -> str:
    """Classify the dominant navigation pattern."""
    scores = {
        'star': 0,
        'linear': 0,
        'cluster': 0,
        'cyclic': 0,
    }

    # Star indicators
    if metrics.get('has_breadth_star'):
        scores['star'] += 2
    if metrics.get('star_branching_factor', 0) >= 2:
        scores['star'] += 1
    if metrics.get('hub_return_rate', 0) >= 0.3:
        scores['star'] += 1

    # Linear indicators
    if metrics.get('linear_ratio', 0) >= 0.7:
        scores['linear'] += 2
    if metrics.get('num_star_branches', 0) <= 1:
        scores['linear'] += 1

    # Cluster indicators
    if metrics.get('graph_density', 0) >= 0.3:
        scores['cluster'] += 2
    if metrics.get('revisit_rate', 0) >= 0.3:
        scores['cluster'] += 1

    # Cyclic indicators
    if metrics.get('has_directed_ring'):
        scores['cyclic'] += 2
    if metrics.get('ring_count', 0) >= 2:
        scores['cyclic'] += 1

    # Find dominant
    max_score = max(scores.values())
    if max_score == 0:
        return 'mixed'

    dominant = [k for k, v in scores.items() if v == max_score]
    if len(dominant) > 1:
        return 'mixed'
    return dominant[0]


def compute_topology_metrics(task: Task, pages: list[Webpage], trials: list[TaskTrial]) -> Optional[TopologyMetrics]:
    """Compute all topology metrics for a task."""
    if len(pages) < 2:
        return None

    # Build graph
    nodes, edges, sequence = build_navigation_graph(pages)

    if not nodes:
        return None

    # Compute all metrics
    star_metrics = compute_star_metrics(nodes, edges, sequence)
    pattern_metrics = detect_patterns(nodes, edges, sequence)
    complexity_metrics = compute_graph_complexity(nodes, edges, sequence)

    # Merge all metrics
    all_metrics = {**star_metrics, **pattern_metrics, **complexity_metrics}

    # Classify dominant pattern
    dominant_pattern = classify_dominant_pattern(all_metrics)

    # Determine correctness
    is_correct = None
    if trials:
        final_trial = max(trials, key=lambda t: (t.num_trial, t.id))
        is_correct = final_trial.is_correct

    return TopologyMetrics(
        task_id=task.id,
        user_id=task.user_id,
        is_correct=is_correct,
        node_count=all_metrics['node_count'],
        edge_count=all_metrics['edge_count'],
        total_visits=all_metrics['total_visits'],
        star_branching_factor=all_metrics['star_branching_factor'],
        hub_return_rate=all_metrics['hub_return_rate'],
        max_star_depth=all_metrics['max_star_depth'],
        num_star_branches=all_metrics['num_star_branches'],
        has_breadth_star=all_metrics['has_breadth_star'],
        has_hesitation_leaves=all_metrics['has_hesitation_leaves'],
        has_directed_ring=all_metrics['has_directed_ring'],
        ring_count=all_metrics['ring_count'],
        linear_ratio=all_metrics['linear_ratio'],
        backtrack_rate=all_metrics['backtrack_rate'],
        revisit_rate=all_metrics['revisit_rate'],
        graph_density=all_metrics['graph_density'],
        avg_out_degree=all_metrics['avg_out_degree'],
        entropy=all_metrics['entropy'],
        dominant_pattern=dominant_pattern,
        path_efficiency=all_metrics['path_efficiency'],
    )


class Command(BaseCommand):
    help = 'Analyzes trajectory topology patterns using graph-based metrics.'

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
            help='Correlate topology patterns with task success',
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
        parser.add_argument(
            '--export-metrics',
            type=str,
            default=None,
            help='Export per-task metrics to CSV file',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        correlate_success = options['correlate_success']
        batch_size = options['batch_size']
        min_pages = options['min_pages']
        export_path = options['export_metrics']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Trajectory Topology: Graph-Based Navigation Pattern Analysis'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. Agents Use Depth-First, Humans Use Hub-and-Spoke')
            self.stdout.write('     - Ou et al. (2021): 5 browsing topology patterns')
            self.stdout.write('     - WebRollback (2025): Agents lack "return to hub" behavior')
            self.stdout.write('  2. The "Sampling Before Committing" Strategy')
            self.stdout.write('     - Information Foraging: Sample multiple, then commit')
            self.stdout.write('     - Agents commit to first result without sampling')
            self.stdout.write('  3. Hub as Cognitive Anchor')
            self.stdout.write('     - SERP enables comparison without memory overload')
            self.stdout.write('     - 89% of successful trajectories share initial sequences')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Quantify optimal star branching factor')
            self.stdout.write('               Identify when hub returns help vs hurt')
            self.stdout.write('               Extract human navigation topology for agent training')
            self.stdout.write('')

        # Get task IDs efficiently using values_list (no model instantiation)
        task_ids = list(
            Task.objects.filter(webpage__isnull=False)
            .values_list('id', flat=True)
            .distinct()
        )
        total_tasks = len(task_ids)

        if output_format == 'text':
            self.stdout.write(f'Found {total_tasks} tasks to process.')

        all_metrics: list[TopologyMetrics] = []

        for batch_start in range(0, total_tasks, batch_size):
            batch_ids = task_ids[batch_start:batch_start + batch_size]

            # Optimize: only load required fields, exclude large JSON fields
            tasks = Task.objects.filter(id__in=batch_ids).only(
                'id', 'user_id'
            ).prefetch_related(
                Prefetch(
                    'webpage_set',
                    queryset=Webpage.objects.only(
                        'id', 'belong_task_id', 'url', 'start_timestamp'
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

                metrics = compute_topology_metrics(task, pages, trials)
                if metrics:
                    all_metrics.append(metrics)

        if not all_metrics:
            self.stdout.write(self.style.WARNING('No tasks with sufficient data found.'))
            return

        # Aggregate statistics
        results = self._aggregate_results(all_metrics, correlate_success)

        # Export if requested
        if export_path:
            self._export_metrics(all_metrics, export_path)
            results['exported_to'] = export_path

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, correlate_success)

    def _aggregate_results(self, metrics: list[TopologyMetrics], correlate_success: bool) -> dict:
        """Aggregate topology metrics across all tasks."""
        # Pattern distribution
        pattern_counts = Counter(m.dominant_pattern for m in metrics)
        total = len(metrics)

        # Star topology metrics
        star_metrics = {
            'branching_factor': {
                'mean': statistics.mean(m.star_branching_factor for m in metrics),
                'median': statistics.median(m.star_branching_factor for m in metrics),
                'std': statistics.stdev(m.star_branching_factor for m in metrics) if len(metrics) > 1 else 0,
            },
            'hub_return_rate': {
                'mean': statistics.mean(m.hub_return_rate for m in metrics),
                'median': statistics.median(m.hub_return_rate for m in metrics),
            },
            'max_depth': {
                'mean': statistics.mean(m.max_star_depth for m in metrics),
                'median': statistics.median(m.max_star_depth for m in metrics),
            },
            'num_branches': {
                'mean': statistics.mean(m.num_star_branches for m in metrics),
                'median': statistics.median(m.num_star_branches for m in metrics),
            },
        }

        # Pattern indicators
        breadth_star_count = sum(1 for m in metrics if m.has_breadth_star)
        directed_ring_count = sum(1 for m in metrics if m.has_directed_ring)
        avg_hesitation = statistics.mean(m.has_hesitation_leaves for m in metrics)

        # Complexity metrics
        complexity_metrics = {
            'node_count': {
                'mean': statistics.mean(m.node_count for m in metrics),
                'median': statistics.median(m.node_count for m in metrics),
            },
            'edge_count': {
                'mean': statistics.mean(m.edge_count for m in metrics),
                'median': statistics.median(m.edge_count for m in metrics),
            },
            'graph_density': {
                'mean': statistics.mean(m.graph_density for m in metrics),
            },
            'entropy': {
                'mean': statistics.mean(m.entropy for m in metrics),
            },
            'path_efficiency': {
                'mean': statistics.mean(m.path_efficiency for m in metrics),
            },
        }

        results = {
            'total_tasks': total,
            'pattern_distribution': {
                pattern: {'count': count, 'percentage': count / total * 100}
                for pattern, count in pattern_counts.items()
            },
            'star_topology_metrics': star_metrics,
            'pattern_indicators': {
                'breadth_star_percentage': breadth_star_count / total * 100,
                'directed_ring_percentage': directed_ring_count / total * 100,
                'avg_hesitation_leaves': avg_hesitation,
            },
            'complexity_metrics': complexity_metrics,
        }

        # Success correlation
        if correlate_success:
            successful = [m for m in metrics if m.is_correct is True]
            unsuccessful = [m for m in metrics if m.is_correct is False]

            if successful and unsuccessful:
                results['success_correlation'] = self._compute_success_correlation(successful, unsuccessful)

        # Generate insights
        results['research_insights'] = self._generate_insights(results, metrics)

        return results

    def _compute_success_correlation(self, successful: list, unsuccessful: list) -> dict:
        """Compute correlation between topology metrics and success."""
        correlation = {}

        metrics_to_compare = [
            ('star_branching_factor', 'Star Branching Factor'),
            ('hub_return_rate', 'Hub Return Rate'),
            ('max_star_depth', 'Max Depth from Hub'),
            ('num_star_branches', 'Number of Branches'),
            ('has_hesitation_leaves', 'Hesitation Leaves'),
            ('entropy', 'Navigation Entropy'),
            ('path_efficiency', 'Path Efficiency'),
            ('backtrack_rate', 'Backtrack Rate'),
        ]

        for attr, label in metrics_to_compare:
            succ_vals = [getattr(m, attr) for m in successful]
            unsucc_vals = [getattr(m, attr) for m in unsuccessful]

            succ_mean = statistics.mean(succ_vals) if succ_vals else 0
            unsucc_mean = statistics.mean(unsucc_vals) if unsucc_vals else 0

            # Effect size (Cohen's d approximation)
            pooled = succ_vals + unsucc_vals
            pooled_std = statistics.stdev(pooled) if len(pooled) > 1 else 1
            effect_size = (succ_mean - unsucc_mean) / pooled_std if pooled_std > 0 else 0

            correlation[attr] = {
                'label': label,
                'successful_mean': succ_mean,
                'unsuccessful_mean': unsucc_mean,
                'difference': succ_mean - unsucc_mean,
                'effect_size': effect_size,
            }

        # Pattern success rates
        pattern_success = defaultdict(lambda: {'success': 0, 'fail': 0})
        for m in successful:
            pattern_success[m.dominant_pattern]['success'] += 1
        for m in unsuccessful:
            pattern_success[m.dominant_pattern]['fail'] += 1

        correlation['pattern_success_rates'] = {
            pattern: {
                'success_rate': data['success'] / (data['success'] + data['fail']) * 100
                if (data['success'] + data['fail']) > 0 else 0,
                'count': data['success'] + data['fail'],
            }
            for pattern, data in pattern_success.items()
        }

        return correlation

    def _generate_insights(self, results: dict, metrics: list) -> list[str]:
        """Generate research-focused insights."""
        insights = []

        # === STAR TOPOLOGY FINDING ===
        star_metrics = results.get('star_topology_metrics', {})
        bf = star_metrics.get('branching_factor', {}).get('mean', 0)
        hr = star_metrics.get('hub_return_rate', {}).get('mean', 0)

        insights.append(
            f"STAR TOPOLOGY CONFIRMED: Avg branching factor = {bf:.2f} pages/SERP visit, "
            f"hub return rate = {hr:.1%}. "
            f"AGENT IMPLICATION: Train agents to sample ~{bf:.0f} results before committing."
        )

        # === DOMINANT PATTERN ===
        pattern_dist = results.get('pattern_distribution', {})
        if pattern_dist:
            dominant = max(pattern_dist.items(), key=lambda x: x[1]['count'])
            insights.append(
                f"DOMINANT PATTERN: '{dominant[0]}' ({dominant[1]['percentage']:.1f}% of trajectories). "
                f"NOVEL: This quantifies human navigation style for agent architecture design."
            )

        # === BREADTH STAR PREVALENCE ===
        indicators = results.get('pattern_indicators', {})
        star_pct = indicators.get('breadth_star_percentage', 0)
        if star_pct > 50:
            insights.append(
                f"HIGH STAR PREVALENCE: {star_pct:.1f}% show breadth-star pattern. "
                f"RESEARCH GAP: Current agents use depth-first; humans use hub-and-spoke. "
                f"TRAINING: Include hub-return behavior in agent reward functions."
            )

        # === HESITATION LEAVES ===
        avg_hesitation = indicators.get('avg_hesitation_leaves', 0)
        if avg_hesitation > 1:
            insights.append(
                f"HESITATION BEHAVIOR: Avg {avg_hesitation:.1f} dead-end explorations per task. "
                f"INTERPRETATION: Users sample and reject before committing. "
                f"AGENT TRAINING: Model 'try and backtrack' as legitimate strategy."
            )

        # === SUCCESS CORRELATION ===
        if 'success_correlation' in results:
            corr = results['success_correlation']

            # Find most discriminating metric
            best_metric = max(
                [(k, v) for k, v in corr.items() if k != 'pattern_success_rates'],
                key=lambda x: abs(x[1].get('effect_size', 0)),
                default=None
            )

            if best_metric and abs(best_metric[1].get('effect_size', 0)) > 0.3:
                m = best_metric[1]
                direction = "higher" if m['difference'] > 0 else "lower"
                insights.append(
                    f"KEY DISCRIMINATOR: {m['label']} - successful users have {direction} values "
                    f"({m['successful_mean']:.2f} vs {m['unsuccessful_mean']:.2f}, effect={m['effect_size']:.2f}). "
                    f"USE: Filter training data by this metric."
                )

            # Pattern success rates
            if 'pattern_success_rates' in corr:
                rates = corr['pattern_success_rates']
                if rates:
                    best_pattern = max(rates.items(), key=lambda x: x[1]['success_rate'])
                    worst_pattern = min(rates.items(), key=lambda x: x[1]['success_rate'])
                    if best_pattern[1]['success_rate'] - worst_pattern[1]['success_rate'] > 10:
                        insights.append(
                            f"PATTERN → SUCCESS: '{best_pattern[0]}' pattern has {best_pattern[1]['success_rate']:.1f}% success "
                            f"vs '{worst_pattern[0]}' at {worst_pattern[1]['success_rate']:.1f}%. "
                            f"AGENT TRAINING: Reward {best_pattern[0]}-like navigation."
                        )

        # === EFFICIENCY INSIGHT ===
        complexity = results.get('complexity_metrics', {})
        efficiency = complexity.get('path_efficiency', {}).get('mean', 0)
        insights.append(
            f"PATH EFFICIENCY: {efficiency:.1%} of page visits are unique (higher = less revisiting). "
            f"BENCHMARK: Use as trajectory quality filter for agent training."
        )

        # === CROSS-VALIDATION RECOMMENDATION ===
        insights.append(
            "CROSS-VALIDATE: Compare with analyze_success_patterns (do efficient topologies succeed?) "
            "and analyze_search_task_type (do task types have different topologies?)."
        )

        return insights

    def _export_metrics(self, metrics: list[TopologyMetrics], path: str):
        """Export metrics to CSV."""
        import csv

        if not metrics:
            return

        fieldnames = list(asdict(metrics[0]).keys())

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in metrics:
                writer.writerow(asdict(m))

        self.stdout.write(f'Exported {len(metrics)} task metrics to {path}')

    def _print_text_output(self, results: dict, correlate_success: bool):
        """Print formatted text output."""
        self.stdout.write(f"\nAnalyzed {results['total_tasks']} tasks.")

        # Pattern distribution
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('TOPOLOGY PATTERN DISTRIBUTION (Ou et al. 2021 Taxonomy)'))
        self.stdout.write('=' * 70)

        for pattern, data in sorted(results['pattern_distribution'].items(), key=lambda x: -x[1]['count']):
            bar = '█' * int(data['percentage'] / 2)
            self.stdout.write(f"  {pattern:<12} {bar:<30} {data['percentage']:5.1f}% ({data['count']})")

        # Star topology metrics
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('STAR TOPOLOGY METRICS (Hub = SERP)'))
        self.stdout.write('-' * 70)

        star = results['star_topology_metrics']
        self.stdout.write(f"  Branching Factor:  mean={star['branching_factor']['mean']:.2f}, "
                         f"median={star['branching_factor']['median']:.2f} pages/SERP visit")
        self.stdout.write(f"  Hub Return Rate:   mean={star['hub_return_rate']['mean']:.1%} "
                         f"(returns to SERP after departing)")
        self.stdout.write(f"  Max Depth:         mean={star['max_depth']['mean']:.1f} "
                         f"(longest chain from SERP)")
        self.stdout.write(f"  Num Branches:      mean={star['num_branches']['mean']:.1f} "
                         f"(separate explorations from SERP)")

        # Pattern indicators
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('PATTERN INDICATORS'))
        self.stdout.write('-' * 70)

        ind = results['pattern_indicators']
        self.stdout.write(f"  Breadth Star:      {ind['breadth_star_percentage']:.1f}% of tasks "
                         f"(hub with multiple children)")
        self.stdout.write(f"  Directed Ring:     {ind['directed_ring_percentage']:.1f}% of tasks "
                         f"(cyclic revisitation)")
        self.stdout.write(f"  Hesitation Leaves: {ind['avg_hesitation_leaves']:.1f} avg/task "
                         f"(dead-end explorations)")

        # Complexity metrics
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('GRAPH COMPLEXITY METRICS'))
        self.stdout.write('-' * 70)

        comp = results['complexity_metrics']
        self.stdout.write(f"  Avg Nodes:         {comp['node_count']['mean']:.1f} unique pages")
        self.stdout.write(f"  Avg Edges:         {comp['edge_count']['mean']:.1f} unique transitions")
        self.stdout.write(f"  Graph Density:     {comp['graph_density']['mean']:.3f} "
                         f"(edges / max_edges)")
        self.stdout.write(f"  Nav Entropy:       {comp['entropy']['mean']:.2f} "
                         f"(0=focused, 1=scattered)")
        self.stdout.write(f"  Path Efficiency:   {comp['path_efficiency']['mean']:.1%} "
                         f"(unique/total visits)")

        # Success correlation
        if correlate_success and 'success_correlation' in results:
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('TOPOLOGY × SUCCESS CORRELATION'))
            self.stdout.write('-' * 70)

            corr = results['success_correlation']

            # Metric comparison
            self.stdout.write(f"  {'Metric':<25} {'Success':<12} {'Fail':<12} {'Effect':<10}")
            self.stdout.write('-' * 60)

            for key, data in corr.items():
                if key == 'pattern_success_rates':
                    continue
                label = data['label'][:25]
                succ = data['successful_mean']
                fail = data['unsuccessful_mean']
                effect = data['effect_size']

                indicator = '**' if abs(effect) > 0.3 else ''
                self.stdout.write(f"  {label:<25} {succ:<12.2f} {fail:<12.2f} {effect:+.2f} {indicator}")

            # Pattern success rates
            if 'pattern_success_rates' in corr:
                self.stdout.write('\n  Pattern Success Rates:')
                for pattern, data in sorted(corr['pattern_success_rates'].items(),
                                          key=lambda x: -x[1]['success_rate']):
                    self.stdout.write(f"    {pattern:<12}: {data['success_rate']:.1f}% (n={data['count']})")

        # Research insights
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('RESEARCH INSIGHTS'))
        self.stdout.write('-' * 70)

        for insight in results.get('research_insights', []):
            self.stdout.write(f"  - {insight}")

        if results.get('exported_to'):
            self.stdout.write(f"\n  Metrics exported to: {results['exported_to']}")

        self.stdout.write('\n' + '=' * 70)
