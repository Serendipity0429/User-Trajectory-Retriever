"""
Controlled Comparison Analysis: Removing Task Difficulty Confounds.

================================================================================
WHY THIS ANALYSIS EXISTS
================================================================================

PROBLEM: Naive success/failure comparisons conflate:
  1. User skill (what we want to measure)
  2. Task difficulty (systematic confound)

A trajectory with many queries and backtracks might reflect:
  - A struggling user (skill issue) OR
  - A hard question (difficulty issue)

SOLUTION: Two controlled comparison approaches:

1. WITHIN-TASK COMPARISON
   - Same question, different users
   - Compare successful vs unsuccessful attempts ON THE SAME TASK
   - Task difficulty is perfectly controlled

2. USER-LEVEL ANALYSIS
   - Aggregate by user across all their tasks
   - Identify consistently skilled vs struggling users
   - Compare behavioral patterns between user groups

3. TASK DIFFICULTY ESTIMATION
   - Use per-task success rate as difficulty proxy
   - Stratify analysis by difficulty level

================================================================================
RESEARCH VALUE
================================================================================

This analysis provides:
- Unconfounded behavioral signatures of user skill
- Task difficulty distribution in your dataset
- User expertise clustering
- Proper baselines for agent training data curation

Usage:
    python manage.py analyze_controlled_comparison
    python manage.py analyze_controlled_comparison --format json
    python manage.py analyze_controlled_comparison --min-users-per-task 3
"""

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Prefetch

from task_manager.models import Task, TaskTrial, TaskDatasetEntry, Webpage


@dataclass
class TaskMetrics:
    """Behavioral metrics for a single task attempt."""
    task_id: int
    user_id: int
    question_id: int  # TaskDatasetEntry.id
    is_correct: Optional[bool]

    # Core metrics
    num_queries: int
    num_pages: int
    total_dwell_time: float
    backtrack_count: int
    revisit_rate: float
    num_unique_domains: int


@dataclass
class UserProfile:
    """Aggregated profile for a user."""
    user_id: int
    num_tasks: int
    success_rate: float

    # Averaged metrics
    avg_queries: float
    avg_pages: float
    avg_dwell_time: float
    avg_backtrack_rate: float
    avg_revisit_rate: float


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
    except Exception:
        pass
    return None


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


def compute_task_metrics(task: Task, pages: list, trials: list) -> Optional[TaskMetrics]:
    """Compute behavioral metrics for a single task."""
    if len(pages) < 2:
        return None

    # Determine correctness from final trial
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

    # Navigation metrics
    urls = [p.url for p in pages]
    normalized_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            normalized = f"{parsed.netloc}{parsed.path}".lower()
            normalized_urls.append(normalized)
        except Exception:
            normalized_urls.append(url)

    unique_urls = set(normalized_urls)
    revisit_rate = 1 - (len(unique_urls) / len(normalized_urls)) if normalized_urls else 0

    # Backtrack count (A->B->A)
    backtrack_count = 0
    for i in range(len(normalized_urls) - 2):
        if normalized_urls[i] == normalized_urls[i + 2] and normalized_urls[i] != normalized_urls[i + 1]:
            backtrack_count += 1

    # Dwell time
    dwell_times = [p.dwell_time / 1000.0 for p in pages if p.dwell_time and p.dwell_time > 0]
    total_dwell = sum(dwell_times) if dwell_times else 0

    # Domains
    domains = set(get_domain(p.url) for p in pages)
    domains.discard('')

    return TaskMetrics(
        task_id=task.id,
        user_id=task.user_id,
        question_id=task.content_id if task.content_id else 0,
        is_correct=is_correct,
        num_queries=len(queries),
        num_pages=len(pages),
        total_dwell_time=total_dwell,
        backtrack_count=backtrack_count,
        revisit_rate=revisit_rate,
        num_unique_domains=len(domains),
    )


class Command(BaseCommand):
    help = 'Analyzes behavioral patterns with proper controls for task difficulty.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--min-users-per-task',
            type=int,
            default=2,
            help='Minimum users per task for within-task comparison (default: 2)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        min_users = options['min_users_per_task']
        batch_size = options['batch_size']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Controlled Comparison: Removing Task Difficulty Confounds'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('WHY THIS MATTERS:'))
            self.stdout.write('  Naive success/failure comparison CONFOUNDS:')
            self.stdout.write('    - User skill (what we want)')
            self.stdout.write('    - Task difficulty (bias)')
            self.stdout.write('')
            self.stdout.write('  This analysis provides:')
            self.stdout.write('    1. Within-task comparison (same question, different users)')
            self.stdout.write('    2. User-level analysis (consistently skilled users)')
            self.stdout.write('    3. Task difficulty estimation')
            self.stdout.write('')

        # Get all tasks with content (question) association
        task_ids = list(
            Task.objects.filter(
                webpage__isnull=False,
                content__isnull=False
            ).exclude(content__belong_dataset__name='tutorial')
            .values_list('id', flat=True)
            .distinct()
        )
        total_tasks = len(task_ids)

        if output_format == 'text':
            self.stdout.write(f'Found {total_tasks} tasks with question associations.')

        # Collect all metrics
        all_metrics: list[TaskMetrics] = []

        for batch_start in range(0, total_tasks, batch_size):
            batch_ids = task_ids[batch_start:batch_start + batch_size]

            tasks = Task.objects.filter(id__in=batch_ids).only(
                'id', 'user_id', 'content_id'
            ).prefetch_related(
                Prefetch(
                    'webpage_set',
                    queryset=Webpage.objects.only(
                        'id', 'belong_task_id', 'url', 'dwell_time'
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

                if len(pages) < 2:
                    continue

                metrics = compute_task_metrics(task, pages, trials)
                if metrics and metrics.question_id:
                    all_metrics.append(metrics)

        if not all_metrics:
            self.stdout.write(self.style.WARNING('No valid tasks found.'))
            return

        # === ANALYSIS 1: Task Difficulty Estimation ===
        task_difficulty = self._compute_task_difficulty(all_metrics)

        # === ANALYSIS 2: Within-Task Comparison ===
        within_task_results = self._within_task_comparison(all_metrics, min_users)

        # === ANALYSIS 3: User-Level Analysis ===
        user_results = self._user_level_analysis(all_metrics)

        # Build results
        results = {
            'total_tasks_analyzed': len(all_metrics),
            'task_difficulty': task_difficulty,
            'within_task_comparison': within_task_results,
            'user_level_analysis': user_results,
        }

        # Generate insights
        results['insights'] = self._generate_insights(results)

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results)

    def _compute_task_difficulty(self, metrics: list[TaskMetrics]) -> dict:
        """Estimate task difficulty from success rates."""
        # Group by question
        by_question = defaultdict(list)
        for m in metrics:
            by_question[m.question_id].append(m)

        difficulties = []
        for qid, attempts in by_question.items():
            known = [m for m in attempts if m.is_correct is not None]
            if known:
                success_rate = sum(1 for m in known if m.is_correct) / len(known)
                difficulties.append({
                    'question_id': qid,
                    'num_attempts': len(known),
                    'success_rate': success_rate,
                })

        if not difficulties:
            return {'error': 'No tasks with known outcomes'}

        # Categorize difficulty
        easy = [d for d in difficulties if d['success_rate'] >= 0.8]
        medium = [d for d in difficulties if 0.4 <= d['success_rate'] < 0.8]
        hard = [d for d in difficulties if d['success_rate'] < 0.4]

        return {
            'total_questions': len(difficulties),
            'difficulty_distribution': {
                'easy': {'count': len(easy), 'pct': len(easy) / len(difficulties) * 100},
                'medium': {'count': len(medium), 'pct': len(medium) / len(difficulties) * 100},
                'hard': {'count': len(hard), 'pct': len(hard) / len(difficulties) * 100},
            },
            'avg_success_rate': statistics.mean(d['success_rate'] for d in difficulties),
            'success_rate_std': statistics.stdev(d['success_rate'] for d in difficulties) if len(difficulties) > 1 else 0,
        }

    def _within_task_comparison(self, metrics: list[TaskMetrics], min_users: int) -> dict:
        """Compare successful vs unsuccessful users on the SAME task."""
        # Group by question
        by_question = defaultdict(list)
        for m in metrics:
            if m.is_correct is not None:
                by_question[m.question_id].append(m)

        # Find questions with both successes and failures
        comparable_questions = []
        for qid, attempts in by_question.items():
            successes = [m for m in attempts if m.is_correct is True]
            failures = [m for m in attempts if m.is_correct is False]

            if len(successes) >= 1 and len(failures) >= 1 and len(attempts) >= min_users:
                comparable_questions.append({
                    'question_id': qid,
                    'successes': successes,
                    'failures': failures,
                })

        if not comparable_questions:
            return {
                'error': f'No questions with both successes and failures (min_users={min_users})',
                'questions_analyzed': 0,
            }

        # Compute within-task differences
        within_diffs = {
            'num_queries': [],
            'num_pages': [],
            'total_dwell_time': [],
            'backtrack_count': [],
            'revisit_rate': [],
        }

        for q in comparable_questions:
            # Average metrics for successes and failures on this question
            succ_avg = {
                'num_queries': statistics.mean(m.num_queries for m in q['successes']),
                'num_pages': statistics.mean(m.num_pages for m in q['successes']),
                'total_dwell_time': statistics.mean(m.total_dwell_time for m in q['successes']),
                'backtrack_count': statistics.mean(m.backtrack_count for m in q['successes']),
                'revisit_rate': statistics.mean(m.revisit_rate for m in q['successes']),
            }
            fail_avg = {
                'num_queries': statistics.mean(m.num_queries for m in q['failures']),
                'num_pages': statistics.mean(m.num_pages for m in q['failures']),
                'total_dwell_time': statistics.mean(m.total_dwell_time for m in q['failures']),
                'backtrack_count': statistics.mean(m.backtrack_count for m in q['failures']),
                'revisit_rate': statistics.mean(m.revisit_rate for m in q['failures']),
            }

            # Difference (failure - success) for each question
            for key in within_diffs:
                within_diffs[key].append(fail_avg[key] - succ_avg[key])

        # Aggregate differences
        results = {
            'questions_analyzed': len(comparable_questions),
            'total_success_attempts': sum(len(q['successes']) for q in comparable_questions),
            'total_failure_attempts': sum(len(q['failures']) for q in comparable_questions),
            'metric_differences': {},
        }

        for key, diffs in within_diffs.items():
            if diffs:
                mean_diff = statistics.mean(diffs)
                # Count how many questions show positive difference (failure > success)
                pct_higher_for_failure = sum(1 for d in diffs if d > 0) / len(diffs) * 100

                results['metric_differences'][key] = {
                    'mean_diff_failure_minus_success': mean_diff,
                    'pct_questions_higher_for_failure': pct_higher_for_failure,
                    'interpretation': 'Failure > Success' if mean_diff > 0 else 'Success > Failure',
                }

        return results

    def _user_level_analysis(self, metrics: list[TaskMetrics]) -> dict:
        """Aggregate by user to identify skill patterns."""
        # Group by user
        by_user = defaultdict(list)
        for m in metrics:
            by_user[m.user_id].append(m)

        # Compute user profiles
        user_profiles = []
        for user_id, user_metrics in by_user.items():
            known = [m for m in user_metrics if m.is_correct is not None]
            if len(known) < 3:  # Need minimum tasks for reliable estimate
                continue

            success_rate = sum(1 for m in known if m.is_correct) / len(known)

            profile = UserProfile(
                user_id=user_id,
                num_tasks=len(known),
                success_rate=success_rate,
                avg_queries=statistics.mean(m.num_queries for m in known),
                avg_pages=statistics.mean(m.num_pages for m in known),
                avg_dwell_time=statistics.mean(m.total_dwell_time for m in known),
                avg_backtrack_rate=statistics.mean(m.backtrack_count / max(m.num_pages - 2, 1) for m in known),
                avg_revisit_rate=statistics.mean(m.revisit_rate for m in known),
            )
            user_profiles.append(profile)

        if not user_profiles:
            return {'error': 'Not enough users with sufficient tasks'}

        # Split into high vs low performers
        median_success = statistics.median(p.success_rate for p in user_profiles)
        high_performers = [p for p in user_profiles if p.success_rate >= median_success]
        low_performers = [p for p in user_profiles if p.success_rate < median_success]

        def avg_metric(profiles, attr):
            vals = [getattr(p, attr) for p in profiles]
            return statistics.mean(vals) if vals else 0

        results = {
            'total_users': len(user_profiles),
            'median_success_rate': median_success,
            'high_performers': {
                'count': len(high_performers),
                'avg_success_rate': avg_metric(high_performers, 'success_rate'),
                'avg_queries': avg_metric(high_performers, 'avg_queries'),
                'avg_pages': avg_metric(high_performers, 'avg_pages'),
                'avg_dwell_time': avg_metric(high_performers, 'avg_dwell_time'),
                'avg_backtrack_rate': avg_metric(high_performers, 'avg_backtrack_rate'),
                'avg_revisit_rate': avg_metric(high_performers, 'avg_revisit_rate'),
            },
            'low_performers': {
                'count': len(low_performers),
                'avg_success_rate': avg_metric(low_performers, 'success_rate'),
                'avg_queries': avg_metric(low_performers, 'avg_queries'),
                'avg_pages': avg_metric(low_performers, 'avg_pages'),
                'avg_dwell_time': avg_metric(low_performers, 'avg_dwell_time'),
                'avg_backtrack_rate': avg_metric(low_performers, 'avg_backtrack_rate'),
                'avg_revisit_rate': avg_metric(low_performers, 'avg_revisit_rate'),
            },
        }

        # Compute differences
        results['skill_differences'] = {}
        for metric in ['avg_queries', 'avg_pages', 'avg_dwell_time', 'avg_backtrack_rate', 'avg_revisit_rate']:
            high_val = results['high_performers'][metric]
            low_val = results['low_performers'][metric]
            diff = low_val - high_val
            results['skill_differences'][metric] = {
                'high_performers': high_val,
                'low_performers': low_val,
                'diff_low_minus_high': diff,
                'interpretation': 'Low performers higher' if diff > 0 else 'High performers higher',
            }

        return results

    def _generate_insights(self, results: dict) -> list[str]:
        """Generate research insights from controlled analysis."""
        insights = []

        # Task difficulty insight
        diff = results.get('task_difficulty', {})
        if 'difficulty_distribution' in diff:
            dist = diff['difficulty_distribution']
            insights.append(
                f"TASK DIFFICULTY: {dist['easy']['pct']:.1f}% easy, "
                f"{dist['medium']['pct']:.1f}% medium, {dist['hard']['pct']:.1f}% hard. "
                f"This distribution should inform stratified analysis."
            )

        # Within-task insight
        within = results.get('within_task_comparison', {})
        if 'metric_differences' in within:
            metrics = within['metric_differences']
            insights.append(
                f"WITHIN-TASK COMPARISON: Analyzed {within['questions_analyzed']} questions "
                f"with both successes and failures. This CONTROLS for task difficulty."
            )

            # Find most discriminating metric
            best_metric = None
            best_pct = 0
            for name, data in metrics.items():
                pct = data['pct_questions_higher_for_failure']
                if pct > best_pct:
                    best_pct = pct
                    best_metric = name

            if best_metric:
                insights.append(
                    f"CONTROLLED FINDING: '{best_metric}' is higher for failures in "
                    f"{best_pct:.1f}% of questions. This is UNCONFOUNDED by task difficulty."
                )

        # User-level insight
        user = results.get('user_level_analysis', {})
        if 'skill_differences' in user:
            insights.append(
                f"USER SKILL ANALYSIS: {user['total_users']} users analyzed. "
                f"Median success rate = {user['median_success_rate']:.1%}."
            )

            # Find biggest skill difference
            biggest_diff = None
            biggest_val = 0
            for name, data in user['skill_differences'].items():
                diff_val = abs(data['diff_low_minus_high'])
                if diff_val > biggest_val:
                    biggest_val = diff_val
                    biggest_diff = name

            if biggest_diff:
                data = user['skill_differences'][biggest_diff]
                insights.append(
                    f"USER SKILL SIGNATURE: '{biggest_diff}' shows largest gap between "
                    f"high ({data['high_performers']:.2f}) and low ({data['low_performers']:.2f}) performers. "
                    f"This reflects SKILL, not task difficulty."
                )

        # Recommendation
        insights.append(
            "RECOMMENDATION: Use within-task and user-level metrics for agent training data curation. "
            "Avoid naive success/failure comparisons which conflate skill and difficulty."
        )

        return insights

    def _print_text_output(self, results: dict):
        """Print formatted text output."""
        self.stdout.write(f"\nAnalyzed {results['total_tasks_analyzed']} task attempts.")

        # Task Difficulty
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('1. TASK DIFFICULTY ESTIMATION'))
        self.stdout.write('=' * 70)

        diff = results.get('task_difficulty', {})
        if 'difficulty_distribution' in diff:
            self.stdout.write(f"  Total questions: {diff['total_questions']}")
            self.stdout.write(f"  Avg success rate: {diff['avg_success_rate']:.1%} (std={diff['success_rate_std']:.2f})")
            self.stdout.write('')

            dist = diff['difficulty_distribution']
            self.stdout.write('  Difficulty Distribution:')
            for level in ['easy', 'medium', 'hard']:
                data = dist[level]
                bar = '█' * int(data['pct'] / 2)
                self.stdout.write(f"    {level:<8} (>80% / 40-80% / <40%): {bar:<30} {data['pct']:5.1f}% ({data['count']})")
        else:
            self.stdout.write(f"  {diff.get('error', 'No data')}")

        # Within-Task Comparison
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('2. WITHIN-TASK COMPARISON (Controls for Task Difficulty)'))
        self.stdout.write('=' * 70)

        within = results.get('within_task_comparison', {})
        if 'metric_differences' in within:
            self.stdout.write(f"  Questions with both successes & failures: {within['questions_analyzed']}")
            self.stdout.write(f"  Success attempts: {within['total_success_attempts']}, Failure attempts: {within['total_failure_attempts']}")
            self.stdout.write('')
            self.stdout.write('  Metric Differences (Failure - Success, averaged across questions):')
            self.stdout.write(f"  {'Metric':<20} {'Mean Diff':<12} {'% Higher for Fail':<18} {'Interpretation'}")
            self.stdout.write('-' * 70)

            for name, data in within['metric_differences'].items():
                self.stdout.write(
                    f"  {name:<20} {data['mean_diff_failure_minus_success']:>+10.2f} "
                    f"{data['pct_questions_higher_for_failure']:>15.1f}%   "
                    f"{data['interpretation']}"
                )
        else:
            self.stdout.write(f"  {within.get('error', 'No data')}")

        # User-Level Analysis
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('3. USER-LEVEL SKILL ANALYSIS'))
        self.stdout.write('=' * 70)

        user = results.get('user_level_analysis', {})
        if 'skill_differences' in user:
            self.stdout.write(f"  Users analyzed: {user['total_users']}")
            self.stdout.write(f"  Median success rate: {user['median_success_rate']:.1%}")
            self.stdout.write('')
            self.stdout.write(f"  High Performers (n={user['high_performers']['count']}): "
                            f"success={user['high_performers']['avg_success_rate']:.1%}")
            self.stdout.write(f"  Low Performers (n={user['low_performers']['count']}): "
                            f"success={user['low_performers']['avg_success_rate']:.1%}")
            self.stdout.write('')
            self.stdout.write('  Skill Differences (Low - High Performers):')
            self.stdout.write(f"  {'Metric':<20} {'High Perf':<12} {'Low Perf':<12} {'Diff':<12} {'Interpretation'}")
            self.stdout.write('-' * 70)

            for name, data in user['skill_differences'].items():
                self.stdout.write(
                    f"  {name:<20} {data['high_performers']:>10.2f} "
                    f"{data['low_performers']:>10.2f} "
                    f"{data['diff_low_minus_high']:>+10.2f}   "
                    f"{data['interpretation']}"
                )
        else:
            self.stdout.write(f"  {user.get('error', 'No data')}")

        # Insights
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESEARCH INSIGHTS'))
        self.stdout.write('=' * 70)

        for insight in results.get('insights', []):
            self.stdout.write(f"  - {insight}")

        self.stdout.write('\n' + '=' * 70)
