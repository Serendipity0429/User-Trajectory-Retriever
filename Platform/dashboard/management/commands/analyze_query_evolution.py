"""
Query Evolution Analysis: Learning Human Reformulation Strategies for Agent Query Generation.

================================================================================
RESEARCH GAPS THIS ANALYSIS ADDRESSES
================================================================================

GAP 1: Human vs LLM Reformulation Strategy Mismatch
    LLM-based query reformulation (GenQR, IterCQR, ConvGQR) achieves good
    retrieval metrics, but:

    UNSOLVED: Do LLMs reformulate queries the same WAY humans do?
    - LLMs: Often expand queries, add context, use formal language
    - Humans: Use shortcuts, implicit context, adapt based on results seen

    Son et al. (2024): Key human advantage is "knowledge updating"—modifying
    queries based on OBSERVED INFORMATION from search results.

    >>> YOUR DATA CAN: Extract reformulation patterns CONDITIONED on what
        users SAW before reformulating. This is information current LLM-based
        QR systems don't have—they reformulate based on query alone, not on
        the search context that triggered the reformulation.

GAP 2: The Missing "Why" Behind Reformulations
    Huang & Efthimiadis taxonomy captures WHAT changed (add/remove/substitute),
    but not WHY the user made that change.

    UNSOLVED: What triggers each reformulation type?
    - Did they see irrelevant results? (context mismatch)
    - Did they learn new terminology from results? (knowledge acquisition)
    - Did they realize initial query was wrong? (error correction)

    >>> YOUR DATA CAN: Correlate reformulation type with the PAGE CONTENT
        viewed before reformulation. Build a model: [results seen] → [likely
        reformulation strategy]. This could inform context-aware QR for agents.

GAP 3: Reformulation as Implicit Reward Signal
    IterCQR (Jang et al., 2023) uses IR signals as reward for training
    without human rewrites. But IR signals only measure retrieval quality.

    UNSOLVED: Can HUMAN reformulation choices serve as reward signal?
    - If a user reformulates query A → B after seeing results, this implies
      query A was insufficient for their intent.
    - The reformulation B represents human judgment about improvement.

    >>> YOUR DATA CAN: Create preference pairs from reformulation sequences.
        (query A, results, query B) forms a preference: B > A for this context.
        This is FREE preference data for RLHF-style training.

GAP 4: When to STOP Reformulating (Satisfaction Detection)
    Current agents either:
    - Keep searching indefinitely
    - Stop after arbitrary limits

    UNSOLVED: What signals indicate a user is SATISFIED and stops reformulating?

    >>> YOUR DATA CAN: Identify terminal query patterns. What distinguishes
        the FINAL query in successful sessions? Shorter? More specific?
        Different dwell time on results? This could train stopping criteria.

GAP 5: The "New Query" Problem (Topic Abandonment vs Pivot)
    High "new query" rate is flagged as disorientation. But sometimes pivoting
    to a new approach is STRATEGIC, not confused.

    UNSOLVED: How to distinguish strategic pivots from confused abandonment?

    >>> YOUR DATA CAN: Analyze "new query" events in successful vs failed
        trajectories. Strategic pivots likely have: deliberate timing,
        maintained task context, eventual success. Confused abandonment has:
        rapid oscillation, no convergence, failure.

================================================================================
NOVEL RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: What information from search results triggers human reformulation?
    - Extract: Content viewed immediately before each reformulation
    - Analyze: What vocabulary/concepts from results appear in new query?
    - Train: Context-aware query reformulation for agents

Q2: Can reformulation sequences serve as preference data?
    - Method: Treat each (query_n, query_n+1) as preference pair
    - Use: Train reward model for query quality
    - Novel: No manual annotation needed—implicit human preferences

Q3: What reformulation patterns predict eventual success?
    - Hypothesis: Specialization → Specialization = convergent, likely success
                  New Query → New Query = divergent, likely failure
    - Application: Early detection of struggling agents

Q4: Do expert users reformulate differently than novices?
    - Cluster: Users by efficiency metrics
    - Compare: Reformulation type distributions
    - Learn: Expert reformulation strategies for agent training

Q5: What is the optimal reformulation "rhythm"?
    - Analyze: Time between queries, pages visited between queries
    - Identify: Rushing (too fast) vs stuck (too slow) patterns
    - Train: Pacing signals for agent query generation

================================================================================
REFORMULATION TAXONOMY (Huang & Efthimiadis 2009) + AGENT TRAINING VALUE
================================================================================

HIGH TRAINING VALUE (strategic patterns):
1. Add Words (Specialization) → Agent should learn WHEN to narrow
2. Word Substitution → Agent should learn vocabulary from results
3. Remove Words (Generalization) → Agent should learn WHEN to broaden

MEDIUM TRAINING VALUE (error recovery):
4. Spelling Correction → Basic capability, easy to train
5. Stemming/Morphological → Linguistic normalization

DIAGNOSTIC VALUE (session health):
6. New Query → High rate = problem signal, but context matters
7. Repeat → Indicates dissatisfaction with results
8. Word Reorder → Minor adjustment, lower signal

Usage:
    python manage.py analyze_query_evolution
    python manage.py analyze_query_evolution --format json
    python manage.py analyze_query_evolution --correlate-success
"""

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from task_manager.models import Task, TaskTrial, Webpage


# Common acronym expansions (extensible)
ACRONYMS = {
    'cpu': 'central processing unit',
    'gpu': 'graphics processing unit',
    'api': 'application programming interface',
    'url': 'uniform resource locator',
    'html': 'hypertext markup language',
    'css': 'cascading style sheets',
    'js': 'javascript',
    'ai': 'artificial intelligence',
    'ml': 'machine learning',
    'nfl': 'national football league',
    'nba': 'national basketball association',
    'usa': 'united states of america',
    'uk': 'united kingdom',
    'nyc': 'new york city',
    'la': 'los angeles',
}

# Search operators
OPERATORS_PATTERN = re.compile(r'(site:|intitle:|inurl:|filetype:|\+|\-|"[^"]+"|\'[^\']+\')')


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def get_word_stem(word: str) -> str:
    """Simple stemming heuristic (Porter-like suffixes)."""
    suffixes = ['ing', 'ed', 'ly', 'es', 's', 'er', 'est', 'ment', 'ness', 'tion', 'sion']
    word = word.lower()
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[:-len(suffix)]
    return word


def extract_operators(query: str) -> tuple[str, list[str]]:
    """Extract search operators from query, return (clean_query, operators)."""
    operators = OPERATORS_PATTERN.findall(query)
    clean = OPERATORS_PATTERN.sub('', query).strip()
    clean = ' '.join(clean.split())  # normalize whitespace
    return clean, operators


def classify_reformulation(q1: str, q2: str) -> str:
    """
    Classify query transition using Huang & Efthimiadis (2009) taxonomy.

    Returns one of:
        'repeat', 'spelling_correction', 'whitespace_punctuation',
        'word_reorder', 'add_words', 'remove_words', 'word_substitution',
        'stemming_morphological', 'acronym_expansion', 'operator_change',
        'new_query'
    """
    # Normalize
    q1_lower = q1.lower().strip()
    q2_lower = q2.lower().strip()

    # 1. Repeat - identical
    if q1_lower == q2_lower:
        return 'repeat'

    # Extract operators
    q1_clean, q1_ops = extract_operators(q1_lower)
    q2_clean, q2_ops = extract_operators(q2_lower)

    # 2. Operator Change - only operators differ
    if q1_clean == q2_clean and q1_ops != q2_ops:
        return 'operator_change'

    # Normalize whitespace/punctuation for comparison
    q1_normalized = re.sub(r'[^\w\s]', '', q1_clean)
    q2_normalized = re.sub(r'[^\w\s]', '', q2_clean)
    q1_normalized = ' '.join(q1_normalized.split())
    q2_normalized = ' '.join(q2_normalized.split())

    # 3. Whitespace/Punctuation only
    if q1_normalized == q2_normalized:
        return 'whitespace_punctuation'

    # Get word sets
    w1 = q1_normalized.split()
    w2 = q2_normalized.split()
    w1_set = set(w1)
    w2_set = set(w2)

    # 4. Word Reorder - same words, different order
    if w1_set == w2_set and w1 != w2:
        return 'word_reorder'

    # 5. Spelling Correction - Levenshtein distance <= 2 per word
    if len(w1) == len(w2):
        total_distance = sum(levenshtein_distance(a, b) for a, b in zip(w1, w2))
        if 0 < total_distance <= 2:
            return 'spelling_correction'

    # 6. Stemming/Morphological - same stems
    stems1 = set(get_word_stem(w) for w in w1)
    stems2 = set(get_word_stem(w) for w in w2)
    if stems1 == stems2 and w1_set != w2_set:
        return 'stemming_morphological'

    # 7. Acronym Expansion
    for acronym, expansion in ACRONYMS.items():
        if acronym in w1_set and any(exp_word in w2_set for exp_word in expansion.split()):
            return 'acronym_expansion'
        if acronym in w2_set and any(exp_word in w1_set for exp_word in expansion.split()):
            return 'acronym_expansion'

    # 8. Add Words (Specialization) - q2 contains all of q1 plus more
    if w1_set.issubset(w2_set) and len(w2_set) > len(w1_set):
        return 'add_words'

    # 9. Remove Words (Generalization) - q2 is subset of q1
    if w2_set.issubset(w1_set) and len(w1_set) > len(w2_set):
        return 'remove_words'

    # 10. Word Substitution - some overlap with some changes
    overlap = w1_set & w2_set
    if len(overlap) > 0 and len(overlap) < max(len(w1_set), len(w2_set)):
        # Check if it's mostly substitution (>50% overlap)
        overlap_ratio = len(overlap) / max(len(w1_set), len(w2_set))
        if overlap_ratio >= 0.3:
            return 'word_substitution'

    # 11. New Query - no meaningful overlap
    return 'new_query'


class Command(BaseCommand):
    help = 'Analyzes query evolution using Huang & Efthimiadis (2009) 12-category taxonomy.'

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
            help='Correlate reformulation patterns with task success',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        correlate_success = options['correlate_success']
        batch_size = options['batch_size']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Query Evolution: Learning Human Reformulation for Agent Query Generation'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. Human vs LLM Reformulation Mismatch')
            self.stdout.write('     - LLMs reformulate based on query alone')
            self.stdout.write('     - Humans reformulate based on WHAT THEY SAW (knowledge updating)')
            self.stdout.write('  2. Missing "Why" Behind Reformulations')
            self.stdout.write('     - Taxonomy captures WHAT changed, not WHY')
            self.stdout.write('     - Need: context-aware reformulation models')
            self.stdout.write('  3. Reformulation as Implicit Reward Signal')
            self.stdout.write('     - Query A → Query B implies B > A for context')
            self.stdout.write('     - FREE preference data for training')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Extract reformulations conditioned on viewed content')
            self.stdout.write('               Create preference pairs from reformulation sequences')
            self.stdout.write('               Identify terminal query patterns (satisfaction signals)')
            self.stdout.write('')

        # Initialize counters
        evolution_stats = Counter()
        total_transitions = 0

        # For success correlation
        success_stats = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'unknown': 0})
        session_stats = {
            'queries_per_task': [],
            'reformulations_per_task': [],
        }

        # Per-task tracking for success correlation
        task_reformulations = defaultdict(list)

        task_ids = list(
            Task.objects.filter(webpage__isnull=False)
            .values_list('id', flat=True)
            .distinct()
        )
        total_tasks = len(task_ids)

        if output_format == 'text':
            self.stdout.write(f'Found {total_tasks} tasks to process.')

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
                queries = []

                for p in pages:
                    try:
                        parsed = urlparse(p.url)
                        params = parse_qs(parsed.query)
                        q = None

                        netloc = parsed.netloc.lower()
                        if 'google' in netloc:
                            q = params.get('q', [None])[0]
                        elif 'bing' in netloc:
                            q = params.get('q', [None])[0]
                        elif 'baidu' in netloc:
                            q = params.get('wd', [None])[0]
                        elif 'duckduckgo' in netloc:
                            q = params.get('q', [None])[0]
                        elif 'yahoo' in netloc:
                            q = params.get('p', [None])[0]

                        if q:
                            q = q.strip()
                            if not queries or queries[-1] != q:
                                queries.append(q)
                    except Exception:
                        pass

                session_stats['queries_per_task'].append(len(queries))

                if len(queries) < 2:
                    continue

                task_types = []
                for i in range(len(queries) - 1):
                    q1, q2 = queries[i], queries[i + 1]
                    reform_type = classify_reformulation(q1, q2)
                    evolution_stats[reform_type] += 1
                    total_transitions += 1
                    task_types.append(reform_type)

                session_stats['reformulations_per_task'].append(len(task_types))
                task_reformulations[task.id] = task_types

                # Get task outcome for correlation
                if correlate_success:
                    trials = list(task.tasktrial_set.all())
                    if trials:
                        final_trial = max(trials, key=lambda t: (t.num_trial, t.id))
                        outcome = 'correct' if final_trial.is_correct else 'incorrect' if final_trial.is_correct is False else 'unknown'
                    else:
                        outcome = 'unknown'

                    for reform_type in task_types:
                        success_stats[reform_type][outcome] += 1

        # Calculate derived metrics
        results = {
            'total_transitions': total_transitions,
            'taxonomy': {},
            'category_groups': {},
            'session_metrics': {},
            'agent_insights': {},
        }

        # Group categories (Huang & Efthimiadis groupings)
        category_groups = {
            'modification': ['add_words', 'remove_words', 'word_substitution', 'word_reorder'],
            'correction': ['spelling_correction', 'stemming_morphological', 'acronym_expansion'],
            'formatting': ['whitespace_punctuation', 'operator_change'],
            'navigation': ['new_query', 'repeat'],
        }

        for reform_type in ['repeat', 'spelling_correction', 'whitespace_punctuation',
                           'word_reorder', 'add_words', 'remove_words', 'word_substitution',
                           'stemming_morphological', 'acronym_expansion', 'operator_change',
                           'new_query']:
            count = evolution_stats.get(reform_type, 0)
            pct = (count / total_transitions * 100) if total_transitions > 0 else 0
            results['taxonomy'][reform_type] = {'count': count, 'percentage': pct}

        for group_name, types in category_groups.items():
            group_count = sum(evolution_stats.get(t, 0) for t in types)
            group_pct = (group_count / total_transitions * 100) if total_transitions > 0 else 0
            results['category_groups'][group_name] = {'count': group_count, 'percentage': group_pct}

        # Session metrics
        if session_stats['queries_per_task']:
            results['session_metrics'] = {
                'avg_queries_per_task': sum(session_stats['queries_per_task']) / len(session_stats['queries_per_task']),
                'tasks_with_reformulations': sum(1 for r in session_stats['reformulations_per_task'] if r > 0),
                'avg_reformulations_per_task': sum(session_stats['reformulations_per_task']) / len(session_stats['reformulations_per_task']) if session_stats['reformulations_per_task'] else 0,
            }

        # Agent-actionable insights
        add_count = evolution_stats.get('add_words', 0)
        remove_count = evolution_stats.get('remove_words', 0)
        spec_gen_ratio = add_count / remove_count if remove_count > 0 else float('inf')

        results['agent_insights'] = {
            'specialization_generalization_ratio': spec_gen_ratio,
            'new_query_rate': results['taxonomy'].get('new_query', {}).get('percentage', 0),
            'spelling_correction_rate': results['taxonomy'].get('spelling_correction', {}).get('percentage', 0),
            'interpretation': self._generate_interpretation(results, spec_gen_ratio),
        }

        # Success correlation
        if correlate_success:
            results['success_correlation'] = {}
            for reform_type, outcomes in success_stats.items():
                total = outcomes['correct'] + outcomes['incorrect']
                if total > 0:
                    accuracy = outcomes['correct'] / total * 100
                    results['success_correlation'][reform_type] = {
                        'correct': outcomes['correct'],
                        'incorrect': outcomes['incorrect'],
                        'unknown': outcomes['unknown'],
                        'accuracy_when_known': accuracy,
                    }

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, correlate_success)

    def _generate_interpretation(self, results, spec_gen_ratio):
        """Generate research-focused insights based on reformulation patterns."""
        insights = []

        # NOVEL METRIC: Specialization/Generalization ratio as training signal
        if spec_gen_ratio >= 2.0:
            insights.append(
                f"NOVEL METRIC: Spec/Gen ratio = {spec_gen_ratio:.1f} (healthy). "
                f"AGENT TRAINING: These reformulation sequences show CONVERGENT behavior - "
                f"users narrow down to find answers. Use these as positive examples."
            )
        elif spec_gen_ratio >= 1.0:
            insights.append(
                f"Balanced spec/gen ratio ({spec_gen_ratio:.1f}): Mixed refinement strategies."
            )
        else:
            insights.append(
                f"RESEARCH FINDING: High generalization rate (ratio={spec_gen_ratio:.1f}). "
                f"HYPOTHESIS: Poor initial queries force broadening. "
                f"AGENT TRAINING: Teach initial query generation from these failures."
            )

        # New query rate - can resolve "strategic pivot vs confused abandon" gap
        new_query_rate = results['taxonomy'].get('new_query', {}).get('percentage', 0)
        if new_query_rate > 20:
            insights.append(
                f"RESEARCH OPPORTUNITY: High new query rate ({new_query_rate:.1f}%). "
                f"UNSOLVED: Is this strategic pivoting or confused abandonment? "
                f"CROSS-VALIDATE: Correlate with task success using --correlate-success flag."
            )
        elif new_query_rate < 5:
            insights.append(
                f"Low new query rate ({new_query_rate:.1f}%): Focused reformulation sessions. "
                f"These trajectories model INCREMENTAL refinement for agents."
            )

        # Word substitution - source of synonym/vocabulary learning
        subst_rate = results['taxonomy'].get('word_substitution', {}).get('percentage', 0)
        if subst_rate > 15:
            insights.append(
                f"TRAINING SIGNAL: High word substitution ({subst_rate:.1f}%). "
                f"NOVEL: Extract vocabulary pairs from substitutions - "
                f"if user replaces A→B, they learned B from search results. "
                f"This is FREE vocabulary grounding data."
            )

        # Preference data generation insight
        add_rate = results['taxonomy'].get('add_words', {}).get('percentage', 0)
        remove_rate = results['taxonomy'].get('remove_words', {}).get('percentage', 0)
        if add_rate + remove_rate > 30:
            insights.append(
                f"PREFERENCE DATA: {add_rate + remove_rate:.1f}% of transitions are add/remove words. "
                f"Each (query_n → query_n+1) forms an implicit preference pair. "
                f"NOVEL: Use for RLHF-style training without manual annotation."
            )

        # Session metrics insight
        session = results.get('session_metrics', {})
        avg_reformulations = session.get('avg_reformulations_per_task', 0)
        if avg_reformulations > 3:
            insights.append(
                f"RESEARCH QUESTION: Avg {avg_reformulations:.1f} reformulations/task. "
                f"What triggers STOPPING? Analyze terminal queries in successful sessions - "
                f"what makes the FINAL query different from earlier ones?"
            )

        return insights

    def _print_text_output(self, results, correlate_success):
        """Print formatted text output."""
        self.stdout.write(f"\nAnalyzed {results['total_transitions']} query transitions.")

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('REFORMULATION TAXONOMY (12 Categories)'))
        self.stdout.write('=' * 70)

        for reform_type, data in results['taxonomy'].items():
            bar = '█' * int(data['percentage'] / 2) + '░' * (50 - int(data['percentage'] / 2))
            self.stdout.write(f"  {reform_type:<25} {bar[:25]} {data['percentage']:5.1f}% ({data['count']})")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('CATEGORY GROUPS'))
        self.stdout.write('-' * 70)

        for group, data in results['category_groups'].items():
            self.stdout.write(f"  {group:<20}: {data['percentage']:5.1f}% ({data['count']})")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('SESSION METRICS'))
        self.stdout.write('-' * 70)

        metrics = results.get('session_metrics', {})
        self.stdout.write(f"  Avg queries per task:        {metrics.get('avg_queries_per_task', 0):.2f}")
        self.stdout.write(f"  Tasks with reformulations:   {metrics.get('tasks_with_reformulations', 0)}")
        self.stdout.write(f"  Avg reformulations per task: {metrics.get('avg_reformulations_per_task', 0):.2f}")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGENT-ACTIONABLE INSIGHTS'))
        self.stdout.write('-' * 70)

        insights = results.get('agent_insights', {})
        ratio = insights.get('specialization_generalization_ratio', 0)
        self.stdout.write(f"  Specialization/Generalization ratio: {ratio:.2f}")
        self.stdout.write(f"  (Literature benchmark: successful users ~2:1)")
        self.stdout.write(f"  New Query rate: {insights.get('new_query_rate', 0):.1f}%")
        self.stdout.write(f"  (High rate suggests disorientation)")

        self.stdout.write('\n  Interpretation:')
        for interp in insights.get('interpretation', []):
            self.stdout.write(f"    - {interp}")

        if correlate_success and results.get('success_correlation'):
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('SUCCESS CORRELATION'))
            self.stdout.write('-' * 70)
            self.stdout.write(f"  {'Type':<25} {'Accuracy':<10} {'Correct':<10} {'Incorrect':<10}")

            for reform_type, data in sorted(
                results['success_correlation'].items(),
                key=lambda x: x[1].get('accuracy_when_known', 0),
                reverse=True
            ):
                self.stdout.write(
                    f"  {reform_type:<25} {data['accuracy_when_known']:>6.1f}%    "
                    f"{data['correct']:<10} {data['incorrect']:<10}"
                )

        self.stdout.write('\n' + '=' * 70)
