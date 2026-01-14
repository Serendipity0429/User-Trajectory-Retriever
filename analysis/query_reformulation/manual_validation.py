#!/usr/bin/env python
"""
Manual validation tool for creating gold-standard reformulation labels.
This allows tuning thresholds to match human judgment.
"""
import json
import random
from pathlib import Path
from metrics import load_query_data, extract_trajectories, classify_reformulation, token_overlap

def create_validation_sample(data_path='extracted_queries/human_trajectories.json',
                             sample_size=100,
                             output_path='validation_sample.json'):
    """
    Create a random sample of query pairs for manual annotation.
    """
    print("Loading data...")
    data = load_query_data(data_path)
    trajectories = extract_trajectories(data)

    # Extract all consecutive query pairs
    query_pairs = []
    for traj in trajectories:
        queries = traj['queries']
        if len(queries) < 2:
            continue

        for i in range(len(queries) - 1):
            query_pairs.append({
                'question': traj['question'],
                'trajectory_id': traj['trajectory_id'],
                'query1': queries[i],
                'query2': queries[i+1],
                'manual_label': None,  # To be filled manually
                'auto_label': None     # Will add automatic classification for comparison
            })

    # Sample randomly
    if len(query_pairs) > sample_size:
        sample = random.sample(query_pairs, sample_size)
    else:
        sample = query_pairs

    # Add automatic classification for comparison
    for pair in sample:
        pair['auto_label'] = classify_reformulation(pair['query1'], pair['query2'])

        # Add token stats for reference
        overlap = token_overlap(pair['query1'], pair['query2'])
        n_added = len(overlap['added'])
        n_removed = len(overlap['removed'])
        n_shared = len(overlap['shared'])
        n_total = n_added + n_removed + n_shared

        pair['overlap_ratio'] = n_shared / n_total if n_total > 0 else 0
        pair['n_added'] = n_added
        pair['n_removed'] = n_removed
        pair['n_shared'] = n_shared

    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample, f, indent=2, ensure_ascii=False)

    print(f"\nSampled {len(sample)} query pairs")
    print(f"Saved to: {output_path}")
    print("\nInstructions:")
    print("1. Open the JSON file")
    print("2. For each pair, set 'manual_label' to one of:")
    print("   - 'expansion': Adding terms (e.g., 'Leo' → 'Leo Dalton')")
    print("   - 'refinement': Mixed changes (e.g., rephrasing)")
    print("   - 'pivoting': Major topic change")
    print("   - 'specification': Removing terms to focus")
    print("   - 'minimal': Very small change (typo, tense)")
    print("   - 'other': Doesn't fit categories")
    print("3. Save the file")
    print(f"4. Run: python manual_validation.py --validate {output_path}")


def compute_agreement(validation_file='validation_sample.json'):
    """
    Compute agreement between manual and automatic labels.
    """
    with open(validation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter only manually labeled pairs
    labeled = [d for d in data if d.get('manual_label') is not None]

    if not labeled:
        print("No manual labels found. Please label the 'manual_label' field first.")
        return

    # Compute agreement
    agreements = sum(1 for d in labeled if d['manual_label'] == d['auto_label'])
    accuracy = agreements / len(labeled)

    print(f"\nManual Validation Results")
    print("=" * 80)
    print(f"Total labeled pairs: {len(labeled)}")
    print(f"Agreement with automatic labels: {agreements}/{len(labeled)} ({accuracy*100:.1f}%)")

    # Confusion matrix
    from collections import defaultdict
    confusion = defaultdict(lambda: defaultdict(int))

    for d in labeled:
        confusion[d['manual_label']][d['auto_label']] += 1

    print("\nConfusion Matrix (rows=manual, cols=automatic):")
    print("-" * 80)

    # Get all labels
    all_labels = sorted(set([d['manual_label'] for d in labeled] + [d['auto_label'] for d in labeled]))

    # Print header
    print(f"{'Manual \\ Auto':<20}", end='')
    for label in all_labels:
        print(f"{label:<15}", end='')
    print()

    # Print rows
    for manual_label in all_labels:
        print(f"{manual_label:<20}", end='')
        for auto_label in all_labels:
            count = confusion[manual_label][auto_label]
            print(f"{count:<15}", end='')
        print()

    # Analyze misclassifications
    print("\nMisclassification Examples:")
    print("-" * 80)

    misclassified = [d for d in labeled if d['manual_label'] != d['auto_label']][:10]

    for i, d in enumerate(misclassified, 1):
        print(f"\nExample {i}:")
        print(f"  Q1: {d['query1']}")
        print(f"  Q2: {d['query2']}")
        print(f"  Overlap ratio: {d['overlap_ratio']:.3f} (added={d['n_added']}, removed={d['n_removed']})")
        print(f"  Manual: {d['manual_label']} | Automatic: {d['auto_label']}")

    # Suggest threshold adjustments
    print("\n" + "=" * 80)
    print("THRESHOLD ADJUSTMENT SUGGESTIONS")
    print("=" * 80)

    # Analyze overlap ratios for each manual label
    from collections import defaultdict
    import numpy as np

    label_overlaps = defaultdict(list)
    for d in labeled:
        label_overlaps[d['manual_label']].append(d['overlap_ratio'])

    for label in sorted(label_overlaps.keys()):
        overlaps = label_overlaps[label]
        print(f"\n{label.upper()}:")
        print(f"  Count: {len(overlaps)}")
        print(f"  Overlap range: [{min(overlaps):.3f}, {max(overlaps):.3f}]")
        print(f"  Mean: {np.mean(overlaps):.3f}, Median: {np.median(overlaps):.3f}")
        print(f"  25th-75th percentile: [{np.percentile(overlaps, 25):.3f}, {np.percentile(overlaps, 75):.3f}]")


def tune_thresholds(validation_file='validation_sample.json'):
    """
    Grid search to find optimal thresholds based on manual labels.
    """
    with open(validation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    labeled = [d for d in data if d.get('manual_label') is not None]

    if len(labeled) < 20:
        print("Need at least 20 manual labels for threshold tuning")
        return

    print(f"\nTuning thresholds on {len(labeled)} labeled examples...")
    print("=" * 80)

    best_accuracy = 0
    best_thresholds = None

    # Grid search over threshold combinations
    pivot_thresholds = [0.2, 0.3, 0.4, 0.5]
    expansion_thresholds = [0.6, 0.7, 0.8]
    minimal_thresholds = [0.85, 0.9, 0.95]

    for pivot_t in pivot_thresholds:
        for exp_t in expansion_thresholds:
            for min_t in minimal_thresholds:
                if pivot_t >= exp_t or exp_t >= min_t:
                    continue

                # Test these thresholds
                correct = 0
                for d in labeled:
                    # Recompute classification with these thresholds
                    predicted = classify_with_thresholds(
                        d['overlap_ratio'], d['n_added'], d['n_removed'], d['n_shared'],
                        pivot_t, exp_t, min_t
                    )

                    if predicted == d['manual_label']:
                        correct += 1

                accuracy = correct / len(labeled)

                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_thresholds = (pivot_t, exp_t, min_t)

    print(f"\nBest thresholds found:")
    print(f"  Pivot threshold: {best_thresholds[0]:.2f} (current: 0.70)")
    print(f"  Expansion threshold: {best_thresholds[1]:.2f} (current: 0.30)")
    print(f"  Minimal threshold: {best_thresholds[2]:.2f} (current: 0.90)")
    print(f"  Accuracy on manual labels: {best_accuracy*100:.1f}%")
    print(f"\nTo use these thresholds, update metrics.py:classify_reformulation()")


def classify_with_thresholds(overlap_ratio, n_added, n_removed, n_shared,
                             pivot_threshold=0.7, expansion_threshold=0.3, minimal_threshold=0.9):
    """Classify reformulation with custom thresholds."""

    # Very high overlap, small change
    if overlap_ratio > minimal_threshold and (n_added + n_removed) <= 2:
        return 'minimal'

    # Low overlap = topic pivot
    if overlap_ratio < pivot_threshold:
        return 'pivoting'

    # High overlap with additions = expansion
    if n_added > 0 and n_removed == 0 and overlap_ratio > expansion_threshold:
        return 'expansion'

    # High overlap with removals = specification
    if n_removed > 0 and n_added == 0 and overlap_ratio > expansion_threshold:
        return 'specification'

    # Mixed = refinement
    return 'refinement'


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Manual validation for reformulation classification')
    parser.add_argument('--create', action='store_true', help='Create validation sample')
    parser.add_argument('--validate', type=str, help='Validate and compute agreement')
    parser.add_argument('--tune', type=str, help='Tune thresholds based on manual labels')
    parser.add_argument('--sample-size', type=int, default=100, help='Sample size for validation')

    args = parser.parse_args()

    if args.create:
        create_validation_sample(sample_size=args.sample_size)
    elif args.validate:
        compute_agreement(args.validate)
    elif args.tune:
        tune_thresholds(args.tune)
    else:
        print("Usage:")
        print("  1. Create sample: python manual_validation.py --create --sample-size 100")
        print("  2. Manually label the 'manual_label' field in validation_sample.json")
        print("  3. Validate: python manual_validation.py --validate validation_sample.json")
        print("  4. Tune thresholds: python manual_validation.py --tune validation_sample.json")


if __name__ == '__main__':
    main()
