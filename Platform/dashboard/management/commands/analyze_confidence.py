"""
Confidence Calibration Analysis: Teaching Agents When to Trust Human Demonstrations.

================================================================================
RESEARCH GAPS THIS ANALYSIS ADDRESSES
================================================================================

GAP 1: The Metacognition Transfer Problem
    Ackerman (2025, arXiv:2509.21545) shows LLMs have LIMITED metacognition:
    - Limited in resolution (can't finely discriminate confidence levels)
    - Context-dependent (metacognition emerges inconsistently)
    - Qualitatively different from humans

    Steyvers & Peters (2025, arXiv:2504.14045): Human-LLM metacognition appears
    aligned on surface, but critical differences remain.

    UNSOLVED: How can we transfer HUMAN metacognitive patterns to agents?
    Current approaches train on actions, not on the confidence/uncertainty
    that guided those actions.

    >>> YOUR DATA CAN: Provide confidence labels alongside trajectories.
        This enables training agents not just on WHAT humans did, but on
        HOW CONFIDENT they were—a signal for when to trust vs question actions.

GAP 2: Confidence-Weighted Training Data Selection
    PC Agent-E showed quality > quantity. But current quality metrics are
    binary (success/fail). Confidence calibration offers a CONTINUOUS quality
    signal.

    HYPOTHESIS: Well-calibrated users produce more reliable training data.
    - High confidence + correct → reliable positive example
    - Low confidence + correct → user got lucky, less reliable
    - High confidence + incorrect → dangerous overconfidence, train against
    - Low confidence + incorrect → appropriate uncertainty, less harmful

    >>> YOUR DATA CAN: Weight trajectory segments by calibration quality.
        Prioritize demonstrations from well-calibrated users (low ECE).
        This is a NOVEL data curation strategy not explored in current work.

GAP 3: Teaching Agents to Express Uncertainty
    MUSE framework (Valiente & Pilly, 2024): Agents need metacognitive
    self-assessment to handle unfamiliar challenges. But how to train this?

    Current agents either:
    - Always confident (overconfident on hard tasks)
    - Always hedging (underconfident, won't commit)

    UNSOLVED: How to learn CALIBRATED uncertainty from human demonstrations?

    >>> YOUR DATA CAN: Identify behavioral correlates of uncertainty.
        When humans are uncertain, do they: query more? backtrack more?
        spend longer on SERP? These behavioral signatures could train
        agents to recognize their own uncertainty situations.

GAP 4: The Hard-Easy Effect in Agent Training
    Classic finding: Humans are overconfident on hard tasks, underconfident
    on easy ones. This bias affects training data quality.

    UNSOLVED: Should we correct for this bias when selecting training data?
    Or should agents learn this bias to match human expectations?

    >>> YOUR DATA CAN: Analyze calibration by task difficulty.
        Identify difficulty levels where human demonstrations are most/least
        reliable. Inform difficulty-aware curriculum learning for agents.

================================================================================
NOVEL RESEARCH QUESTIONS YOUR DATA CAN ANSWER
================================================================================

Q1: Does user calibration predict trajectory usefulness for agent training?
    - Hypothesis: Trajectories from well-calibrated users (ECE < 0.15) produce
      better agent performance than those from miscalibrated users.
    - Experiment: Train agents on calibration-stratified subsets, compare.

Q2: What behavioral patterns correlate with confidence states?
    - Hypothesis: High confidence → shorter dwell, fewer queries, direct navigation
                  Low confidence → longer SERP time, more reformulations, backtracking
    - Analysis: Correlate confidence ratings with behavioral features.
    - Application: Train agents to infer their own "confidence" from behavior.

Q3: Can we identify "confident errors" for hard negative mining?
    - High confidence + wrong answer = most dangerous training examples
    - These could be used as hard negatives to teach agents caution.

Q4: Does calibration vary by task type?
    - Hypothesis: Lookup tasks have better calibration than exploratory tasks.
    - Implication: Weight demonstrations differently by task type.

Q5: Can human confidence patterns inform agent self-monitoring?
    - Extract: When do humans express uncertainty before failing?
    - Train: Agent to recognize similar situations and request help/clarify.

================================================================================
KEY METRICS AND THEIR AGENT TRAINING IMPLICATIONS
================================================================================

ECE (Expected Calibration Error):
    - User-level: Filter training data by user calibration quality
    - Segment-level: Weight trajectory segments by local calibration

Overconfidence Index:
    - Positive bias: User's high-confidence errors need verification
    - Negative bias: User's successes may be undervalued in training

Hard-Easy Effect Pattern:
    - Classic pattern: Adjust training weight by task difficulty
    - Reversed pattern: Unusual users, investigate their strategies

Brier Score:
    - Lower = more reliable probability estimates
    - Use for ranking trajectories within successful outcomes

Usage:
    python manage.py analyze_confidence
    python manage.py analyze_confidence --format json
    python manage.py analyze_confidence --by-difficulty
"""

import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from django.core.management.base import BaseCommand
from django.db.models import Count

from task_manager.models import TaskTrial, PreTaskAnnotation


@dataclass
class CalibrationMetrics:
    """Calibration metrics for a confidence bin."""
    bin_start: float
    bin_end: float
    count: int
    accuracy: float
    avg_confidence: float
    calibration_error: float  # |accuracy - confidence|
    bias: float  # confidence - accuracy (positive = overconfident)


def calculate_ece(bins: list[CalibrationMetrics], total_samples: int) -> float:
    """
    Calculate Expected Calibration Error (ECE).

    ECE = sum(bin_weight * |accuracy_bin - confidence_bin|)

    This is the standard metric for calibration quality.
    Lower is better, 0 = perfectly calibrated.
    """
    if total_samples == 0:
        return 0.0

    ece = 0.0
    for bin_data in bins:
        weight = bin_data.count / total_samples
        ece += weight * bin_data.calibration_error

    return ece


def calculate_mce(bins: list[CalibrationMetrics]) -> float:
    """
    Calculate Maximum Calibration Error (MCE).

    MCE = max(|accuracy_bin - confidence_bin|)

    Useful for identifying worst-case calibration failures.
    """
    if not bins:
        return 0.0

    return max(bin_data.calibration_error for bin_data in bins)


def calculate_brier_score(trials: list[tuple[float, bool]]) -> float:
    """
    Calculate Brier Score (mean squared error of probability estimates).

    Brier = (1/n) * sum((confidence - outcome)^2)

    Lower is better, 0 = perfect predictions.
    """
    if not trials:
        return 0.0

    total = 0.0
    for confidence, is_correct in trials:
        outcome = 1.0 if is_correct else 0.0
        total += (confidence - outcome) ** 2

    return total / len(trials)


def calculate_overconfidence_index(bins: list[CalibrationMetrics], total_samples: int) -> float:
    """
    Calculate weighted average bias (overconfidence index).

    Positive = systematic overconfidence
    Negative = systematic underconfidence
    """
    if total_samples == 0:
        return 0.0

    weighted_bias = 0.0
    for bin_data in bins:
        weight = bin_data.count / total_samples
        weighted_bias += weight * bin_data.bias

    return weighted_bias


class Command(BaseCommand):
    help = 'Analyzes confidence calibration using metacognition research frameworks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--num-bins',
            type=int,
            default=5,
            help='Number of confidence bins (default: 5 for 0-4 scale)',
        )
        parser.add_argument(
            '--by-difficulty',
            action='store_true',
            help='Analyze calibration by pre-task difficulty rating',
        )
        parser.add_argument(
            '--exclude-unknown',
            action='store_true',
            help='Exclude trials with unknown correctness',
        )

    def handle(self, *args, **options):
        output_format = options['format']
        num_bins = options['num_bins']
        by_difficulty = options['by_difficulty']
        exclude_unknown = options['exclude_unknown']

        if output_format == 'text':
            self.stdout.write(self.style.SUCCESS('Confidence Calibration: Teaching Agents When to Trust Demonstrations'))
            self.stdout.write('=' * 70)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESEARCH GAPS ADDRESSED:'))
            self.stdout.write('  1. Metacognition Transfer Problem (Ackerman 2025, Steyvers 2025)')
            self.stdout.write('     - LLMs have LIMITED metacognition (context-dependent, low resolution)')
            self.stdout.write('     - Human-LLM metacognition differs qualitatively')
            self.stdout.write('  2. Confidence-Weighted Training Data')
            self.stdout.write('     - High confidence + correct = reliable training example')
            self.stdout.write('     - High confidence + wrong = dangerous, train against')
            self.stdout.write('  3. Teaching Uncertainty Expression (MUSE framework)')
            self.stdout.write('     - Agents need calibrated uncertainty, not always-confident')
            self.stdout.write('')
            self.stdout.write('YOUR DATA CAN: Provide confidence labels alongside trajectories')
            self.stdout.write('               Weight training data by user calibration quality')
            self.stdout.write('               Identify behavioral correlates of uncertainty')
            self.stdout.write('')

        # Get trials with confidence ratings
        trials_qs = TaskTrial.objects.exclude(confidence=-1)
        if exclude_unknown:
            trials_qs = trials_qs.exclude(is_correct__isnull=True)

        trials_data = list(trials_qs.values('id', 'confidence', 'is_correct', 'belong_task_id'))

        if output_format == 'text':
            self.stdout.write(f'Found {len(trials_data)} trials with confidence ratings.')

        # Filter to known correctness for calibration analysis
        known_trials = [t for t in trials_data if t['is_correct'] is not None]

        if not known_trials:
            self.stdout.write(self.style.WARNING('No trials with known correctness found.'))
            return

        # Calculate calibration bins
        bins = self._calculate_calibration_bins(known_trials, num_bins)
        total_known = len(known_trials)

        # Calculate overall metrics
        ece = calculate_ece(bins, total_known)
        mce = calculate_mce(bins)

        # For Brier score, normalize confidence to [0, 1]
        max_conf = num_bins - 1  # Assuming 0-indexed bins
        normalized_trials = [
            (t['confidence'] / max_conf, t['is_correct'])
            for t in known_trials
        ]
        brier = calculate_brier_score(normalized_trials)

        overconfidence_idx = calculate_overconfidence_index(bins, total_known)

        # Overall accuracy
        overall_accuracy = sum(1 for t in known_trials if t['is_correct']) / total_known
        overall_avg_conf = sum(t['confidence'] for t in known_trials) / total_known / max_conf

        # Hard-easy effect analysis
        hard_easy = self._analyze_hard_easy_effect(bins)

        # Build results
        results = {
            'total_trials': len(trials_data),
            'known_trials': total_known,
            'overall_accuracy': overall_accuracy,
            'overall_avg_confidence': overall_avg_conf,
            'calibration_metrics': {
                'ece': ece,
                'mce': mce,
                'brier_score': brier,
                'overconfidence_index': overconfidence_idx,
            },
            'calibration_bins': [
                {
                    'bin': f"{b.bin_start}-{b.bin_end}",
                    'count': b.count,
                    'accuracy': b.accuracy,
                    'avg_confidence': b.avg_confidence,
                    'calibration_error': b.calibration_error,
                    'bias': b.bias,
                }
                for b in bins
            ],
            'hard_easy_effect': hard_easy,
            'interpretation': self._generate_interpretation(ece, overconfidence_idx, hard_easy),
        }

        # Difficulty-stratified analysis
        if by_difficulty:
            results['by_difficulty'] = self._analyze_by_difficulty(known_trials, num_bins)

        # Agent insights
        results['agent_insights'] = self._generate_agent_insights(results)

        # Output
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._print_text_output(results, bins, by_difficulty)

    def _calculate_calibration_bins(
        self,
        trials: list[dict],
        num_bins: int
    ) -> list[CalibrationMetrics]:
        """Calculate calibration metrics per confidence bin."""
        bins = []
        max_conf = num_bins - 1  # Assuming confidence is 0 to num_bins-1

        for bin_idx in range(num_bins):
            bin_trials = [t for t in trials if t['confidence'] == bin_idx]

            if not bin_trials:
                bins.append(CalibrationMetrics(
                    bin_start=bin_idx,
                    bin_end=bin_idx,
                    count=0,
                    accuracy=0.0,
                    avg_confidence=bin_idx / max_conf if max_conf > 0 else 0,
                    calibration_error=0.0,
                    bias=0.0,
                ))
                continue

            count = len(bin_trials)
            correct = sum(1 for t in bin_trials if t['is_correct'])
            accuracy = correct / count

            # Normalize confidence to [0, 1] for comparison
            avg_confidence = bin_idx / max_conf if max_conf > 0 else 0

            calibration_error = abs(accuracy - avg_confidence)
            bias = avg_confidence - accuracy  # positive = overconfident

            bins.append(CalibrationMetrics(
                bin_start=bin_idx,
                bin_end=bin_idx,
                count=count,
                accuracy=accuracy,
                avg_confidence=avg_confidence,
                calibration_error=calibration_error,
                bias=bias,
            ))

        return bins

    def _analyze_hard_easy_effect(self, bins: list[CalibrationMetrics]) -> dict:
        """
        Analyze the hard-easy effect.

        Hard-easy effect: People tend to be overconfident on hard tasks
        and underconfident on easy tasks.
        """
        # Low confidence bins (hard tasks) - check for overconfidence
        low_bins = [b for b in bins if b.bin_start <= 1 and b.count > 0]
        # High confidence bins (easy tasks) - check for underconfidence
        high_bins = [b for b in bins if b.bin_start >= 3 and b.count > 0]

        low_bias = statistics.mean([b.bias for b in low_bins]) if low_bins else 0
        high_bias = statistics.mean([b.bias for b in high_bins]) if high_bins else 0

        # Classic hard-easy effect: positive bias on low confidence, negative on high
        effect_strength = low_bias - high_bias

        return {
            'low_confidence_bias': low_bias,
            'high_confidence_bias': high_bias,
            'effect_strength': effect_strength,
            'pattern': self._classify_hard_easy_pattern(low_bias, high_bias),
        }

    def _classify_hard_easy_pattern(self, low_bias: float, high_bias: float) -> str:
        """Classify the hard-easy effect pattern."""
        threshold = 0.1

        if low_bias > threshold and high_bias < -threshold:
            return 'classic_hard_easy'  # Overconfident on hard, underconfident on easy
        elif low_bias > threshold and high_bias > threshold:
            return 'systematic_overconfidence'
        elif low_bias < -threshold and high_bias < -threshold:
            return 'systematic_underconfidence'
        elif abs(low_bias) < threshold and abs(high_bias) < threshold:
            return 'well_calibrated'
        else:
            return 'mixed'

    def _analyze_by_difficulty(self, trials: list[dict], num_bins: int) -> dict:
        """Analyze calibration stratified by pre-task difficulty rating."""
        # Get difficulty ratings
        task_ids = list(set(t['belong_task_id'] for t in trials))

        difficulty_map = {}
        for annotation in PreTaskAnnotation.objects.filter(
            belong_task_id__in=task_ids,
            difficulty__isnull=False
        ).values('belong_task_id', 'difficulty'):
            difficulty_map[annotation['belong_task_id']] = annotation['difficulty']

        # Group trials by difficulty
        by_difficulty = defaultdict(list)
        for t in trials:
            diff = difficulty_map.get(t['belong_task_id'])
            if diff is not None:
                by_difficulty[diff].append(t)

        # Calculate metrics per difficulty level
        results = {}
        for diff_level, diff_trials in sorted(by_difficulty.items()):
            if not diff_trials:
                continue

            bins = self._calculate_calibration_bins(diff_trials, num_bins)
            total = len(diff_trials)

            ece = calculate_ece(bins, total)
            accuracy = sum(1 for t in diff_trials if t['is_correct']) / total
            avg_conf = sum(t['confidence'] for t in diff_trials) / total / (num_bins - 1)

            results[diff_level] = {
                'count': total,
                'accuracy': accuracy,
                'avg_confidence': avg_conf,
                'ece': ece,
                'bias': avg_conf - accuracy,
            }

        return results

    def _generate_interpretation(self, ece: float, overconf_idx: float, hard_easy: dict) -> list[str]:
        """Generate human-readable interpretation."""
        interpretations = []

        # ECE interpretation
        if ece < 0.1:
            interpretations.append(f"ECE={ece:.3f}: Well-calibrated (excellent)")
        elif ece < 0.2:
            interpretations.append(f"ECE={ece:.3f}: Reasonably calibrated (good)")
        elif ece < 0.3:
            interpretations.append(f"ECE={ece:.3f}: Moderate miscalibration (needs improvement)")
        else:
            interpretations.append(f"ECE={ece:.3f}: Poorly calibrated (significant issues)")

        # Overconfidence interpretation
        if overconf_idx > 0.1:
            interpretations.append(f"Systematic overconfidence (bias={overconf_idx:+.3f})")
        elif overconf_idx < -0.1:
            interpretations.append(f"Systematic underconfidence (bias={overconf_idx:+.3f})")
        else:
            interpretations.append(f"No systematic bias (bias={overconf_idx:+.3f})")

        # Hard-easy effect
        pattern = hard_easy.get('pattern', 'unknown')
        if pattern == 'classic_hard_easy':
            interpretations.append("Classic hard-easy effect detected: overconfident on hard, underconfident on easy")
        elif pattern == 'systematic_overconfidence':
            interpretations.append("Systematic overconfidence across all difficulty levels")
        elif pattern == 'systematic_underconfidence':
            interpretations.append("Systematic underconfidence across all difficulty levels")
        elif pattern == 'well_calibrated':
            interpretations.append("Users show good calibration across difficulty levels")

        return interpretations

    def _generate_agent_insights(self, results: dict) -> list[str]:
        """Generate research-focused insights on confidence for agent training."""
        insights = []

        ece = results['calibration_metrics']['ece']
        overconf = results['calibration_metrics']['overconfidence_index']
        brier = results['calibration_metrics']['brier_score']

        # === NOVEL: Calibration as Training Data Filter ===
        insights.append(
            f"NOVEL DATA CURATION: User-level ECE = {ece:.3f}. "
            f"HYPOTHESIS: Trajectories from well-calibrated users (ECE < 0.15) "
            f"produce better agent performance. TEST THIS with stratified training."
        )

        # === RESEARCH GAP: Confidence-Weighted Examples ===
        if overconf > 0.05:
            insights.append(
                f"OVERCONFIDENCE DETECTED (bias = {overconf:+.3f}): "
                f"RESEARCH OPPORTUNITY: Use (high confidence + wrong) cases as HARD NEGATIVES. "
                f"These are dangerous patterns agents should learn to avoid."
            )
        elif overconf < -0.05:
            insights.append(
                f"UNDERCONFIDENCE DETECTED (bias = {overconf:+.3f}): "
                f"Users' correct low-confidence answers may contain valuable uncertainty signals. "
                f"Extract behavioral correlates of appropriate uncertainty."
            )

        # === NOVEL: Behavioral Correlates of Confidence ===
        insights.append(
            "RESEARCH QUESTION: What behaviors correlate with confidence states? "
            "HYPOTHESIS: High confidence → shorter dwell, fewer queries, direct navigation. "
            "Low confidence → longer SERP time, more reformulations. "
            "CROSS-VALIDATE with analyze_cognitive_load and analyze_query_evolution."
        )

        # === ACTIONABLE: Training Data Weighting Scheme ===
        insights.append(
            f"PROPOSED WEIGHTING SCHEME based on calibration:\n"
            f"  • High conf + correct: weight = 1.0 (reliable positive)\n"
            f"  • Low conf + correct:  weight = 0.7 (lucky success)\n"
            f"  • High conf + wrong:   weight = -0.5 (train against)\n"
            f"  • Low conf + wrong:    weight = 0.3 (appropriate uncertainty)"
        )

        # === Difficulty-based Research ===
        if 'by_difficulty' in results:
            diff_data = results['by_difficulty']
            if diff_data:
                worst_diff = max(diff_data.items(), key=lambda x: x[1]['ece'])
                best_diff = min(diff_data.items(), key=lambda x: x[1]['ece'])

                insights.append(
                    f"HARD-EASY EFFECT: Best calibration at difficulty={best_diff[0]} "
                    f"(ECE={best_diff[1]['ece']:.3f}), worst at difficulty={worst_diff[0]} "
                    f"(ECE={worst_diff[1]['ece']:.3f}). "
                    f"IMPLICATION: Difficulty-aware curriculum—start training on {best_diff[0]} tasks."
                )

        # === Cross-validation suggestion ===
        insights.append(
            "NEXT STEPS:\n"
            "  1. Correlate user ECE with efficiency_score from success_patterns\n"
            "  2. Check if well-calibrated users have better reformulation patterns\n"
            "  3. Test hypothesis: train on ECE < 0.15 users only → better agent"
        )

        return insights

    def _print_text_output(self, results: dict, bins: list[CalibrationMetrics], by_difficulty: bool):
        """Print formatted text output."""
        self.stdout.write(f"\nAnalyzed {results['known_trials']} trials with known correctness.")

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('OVERALL METRICS'))
        self.stdout.write('=' * 70)
        self.stdout.write(f"  Overall Accuracy:     {results['overall_accuracy']*100:.1f}%")
        self.stdout.write(f"  Overall Confidence:   {results['overall_avg_confidence']*100:.1f}%")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('CALIBRATION METRICS'))
        self.stdout.write('-' * 70)

        metrics = results['calibration_metrics']
        self.stdout.write(f"  ECE (Expected Calibration Error): {metrics['ece']:.4f}")
        self.stdout.write(f"    Lower is better, 0 = perfectly calibrated")
        self.stdout.write(f"  MCE (Maximum Calibration Error):  {metrics['mce']:.4f}")
        self.stdout.write(f"  Brier Score:                      {metrics['brier_score']:.4f}")
        self.stdout.write(f"  Overconfidence Index:             {metrics['overconfidence_index']:+.4f}")
        self.stdout.write(f"    Positive = overconfident, Negative = underconfident")

        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('CALIBRATION BY CONFIDENCE LEVEL'))
        self.stdout.write('-' * 70)
        self.stdout.write(f"  {'Conf':<6} {'Count':<8} {'Accuracy':<10} {'Expected':<10} {'Error':<10} {'Bias':<10}")

        for b in bins:
            if b.count > 0:
                bias_str = f"{b.bias:+.3f}" if b.bias != 0 else "0.000"
                self.stdout.write(
                    f"  {int(b.bin_start):<6} {b.count:<8} {b.accuracy*100:<10.1f}% "
                    f"{b.avg_confidence*100:<10.1f}% {b.calibration_error:.3f}      {bias_str}"
                )

        # Reliability diagram (ASCII)
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('RELIABILITY DIAGRAM'))
        self.stdout.write('-' * 70)
        self.stdout.write("  (Perfect calibration = diagonal line)")
        self.stdout.write("  Conf  | Accuracy Bar")

        for b in bins:
            if b.count > 0:
                expected_bar = int(b.avg_confidence * 20)
                actual_bar = int(b.accuracy * 20)

                # Create visual bar
                bar = ['░'] * 21
                bar[expected_bar] = '│'  # Expected (diagonal)
                for i in range(min(actual_bar, expected_bar), max(actual_bar, expected_bar) + 1):
                    if i == actual_bar:
                        bar[i] = '█'

                self.stdout.write(f"  {int(b.bin_start):<5} | {''.join(bar)} ({b.accuracy*100:.0f}% vs {b.avg_confidence*100:.0f}%)")

        # Hard-easy effect
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('HARD-EASY EFFECT ANALYSIS'))
        self.stdout.write('-' * 70)

        hard_easy = results['hard_easy_effect']
        self.stdout.write(f"  Low confidence bias:  {hard_easy['low_confidence_bias']:+.3f}")
        self.stdout.write(f"  High confidence bias: {hard_easy['high_confidence_bias']:+.3f}")
        self.stdout.write(f"  Pattern: {hard_easy['pattern']}")

        # By difficulty
        if by_difficulty and results.get('by_difficulty'):
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.SUCCESS('CALIBRATION BY TASK DIFFICULTY'))
            self.stdout.write('-' * 70)
            self.stdout.write(f"  {'Diff':<6} {'Count':<8} {'Accuracy':<10} {'Confidence':<12} {'ECE':<10} {'Bias':<10}")

            for diff, data in sorted(results['by_difficulty'].items()):
                self.stdout.write(
                    f"  {diff:<6} {data['count']:<8} {data['accuracy']*100:<10.1f}% "
                    f"{data['avg_confidence']*100:<12.1f}% {data['ece']:<10.4f} {data['bias']:+.3f}"
                )

        # Interpretation
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('INTERPRETATION'))
        self.stdout.write('-' * 70)

        for interp in results.get('interpretation', []):
            self.stdout.write(f"  - {interp}")

        # Agent insights
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(self.style.SUCCESS('AGENT-ACTIONABLE INSIGHTS'))
        self.stdout.write('-' * 70)

        for insight in results.get('agent_insights', []):
            self.stdout.write(f"  - {insight}")

        self.stdout.write('\n' + '=' * 70)
