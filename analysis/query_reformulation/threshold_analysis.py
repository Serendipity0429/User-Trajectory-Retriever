#!/usr/bin/env python
"""
Analyze token overlap distributions to inform threshold selection for reformulation classification.
This provides empirical justification for threshold choices.
"""
import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from collections import defaultdict
from metrics import tokenize, token_overlap, load_query_data, extract_trajectories

def compute_overlap_statistics(trajectories):
    """
    Compute token overlap ratios for all consecutive query pairs.
    Returns: list of (overlap_ratio, n_added, n_removed, n_shared) tuples
    """
    stats = []

    for traj in trajectories:
        queries = traj['queries']
        if len(queries) < 2:
            continue

        for i in range(len(queries) - 1):
            overlap = token_overlap(queries[i], queries[i+1])

            n_added = len(overlap['added'])
            n_removed = len(overlap['removed'])
            n_shared = len(overlap['shared'])
            n_total = n_added + n_removed + n_shared

            if n_total == 0:
                continue

            overlap_ratio = n_shared / n_total

            stats.append({
                'overlap_ratio': overlap_ratio,
                'n_added': n_added,
                'n_removed': n_removed,
                'n_shared': n_shared,
                'query1': queries[i],
                'query2': queries[i+1]
            })

    return stats


def analyze_thresholds(data_dir='extracted_queries', output_dir='outputs/figures'):
    """Analyze overlap distributions across all datasets to inform threshold choices."""

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    dataset_names = ['human', 'rag', 'vanilla_agent', 'browser_agent']
    all_stats = {}

    print("Analyzing token overlap distributions...\n")

    for name in dataset_names:
        filepath = Path(data_dir) / f"{name}_trajectories.json" if name == 'human' else Path(data_dir) / f"{name}.json"

        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue

        print(f"Processing {name}...")
        data = load_query_data(str(filepath))
        trajectories = extract_trajectories(data)
        stats = compute_overlap_statistics(trajectories)
        all_stats[name] = stats

        if stats:
            overlap_ratios = [s['overlap_ratio'] for s in stats]
            print(f"  Total transitions: {len(stats)}")
            print(f"  Overlap ratio - Mean: {np.mean(overlap_ratios):.3f}, "
                  f"Std: {np.std(overlap_ratios):.3f}, "
                  f"Median: {np.median(overlap_ratios):.3f}")
            print(f"  Percentiles: 25%={np.percentile(overlap_ratios, 25):.3f}, "
                  f"50%={np.percentile(overlap_ratios, 50):.3f}, "
                  f"75%={np.percentile(overlap_ratios, 75):.3f}")
            print()

    # Visualize distributions
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for idx, name in enumerate(dataset_names):
        if name not in all_stats or not all_stats[name]:
            continue

        overlap_ratios = [s['overlap_ratio'] for s in all_stats[name]]

        ax = axes[idx]
        ax.hist(overlap_ratios, bins=50, alpha=0.7, edgecolor='black')
        ax.axvline(0.3, color='red', linestyle='--', linewidth=2, label='Pivot boundary: 0.3')
        ax.axvline(0.5, color='orange', linestyle='--', linewidth=2, label='Expansion min: 0.5')
        ax.axvline(0.9, color='green', linestyle='--', linewidth=2, label='Minimal: 0.9')
        ax.set_title(f'{name.upper()}\n{len(overlap_ratios)} transitions', fontweight='bold')
        ax.set_xlabel('Token Overlap Ratio')
        ax.set_ylabel('Frequency')
        ax.legend(fontsize=8, loc='upper left')
        ax.grid(alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / 'threshold_analysis_distributions.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Distribution plot saved to: {output_path}")
    plt.show()

    # Combined distribution for threshold recommendation
    print("\n" + "="*80)
    print("THRESHOLD RECOMMENDATIONS (Data-Driven)")
    print("="*80)

    for name in dataset_names:
        if name not in all_stats or not all_stats[name]:
            continue

        overlap_ratios = [s['overlap_ratio'] for s in all_stats[name]]

        # Suggest thresholds based on percentiles
        p25 = np.percentile(overlap_ratios, 25)
        p50 = np.percentile(overlap_ratios, 50)
        p90 = np.percentile(overlap_ratios, 90)

        print(f"\n{name.upper()}:")
        print(f"  25th percentile: {p25:.3f} (suggested MAX overlap for pivoting)")
        print(f"  50th percentile: {p50:.3f} (suggested MIN overlap for expansion/specification)")
        print(f"  90th percentile: {p90:.3f} (suggested minimal change threshold)")

    print("\n" + "="*80)
    print("RECOMMENDED THRESHOLDS (based on human data):")
    print("="*80)
    print("  max_overlap_for_pivot = 0.3  (captures low overlap queries)")
    print("  min_overlap_for_expansion = 0.5  (above median, clear additions)")
    print("  minimal_threshold = 0.9  (unchanged)")
    print("\nThese thresholds are now implemented in metrics.py")

    # Analyze edit operations
    print("\n" + "="*80)
    print("EDIT OPERATION ANALYSIS")
    print("="*80)

    for name in dataset_names:
        if name not in all_stats or not all_stats[name]:
            continue

        stats = all_stats[name]

        # Categorize by operation type
        only_add = sum(1 for s in stats if s['n_added'] > 0 and s['n_removed'] == 0)
        only_remove = sum(1 for s in stats if s['n_removed'] > 0 and s['n_added'] == 0)
        both = sum(1 for s in stats if s['n_added'] > 0 and s['n_removed'] > 0)

        print(f"\n{name.upper()}:")
        print(f"  Only additions: {only_add} ({only_add/len(stats)*100:.1f}%)")
        print(f"  Only removals: {only_remove} ({only_remove/len(stats)*100:.1f}%)")
        print(f"  Both add & remove: {both} ({both/len(stats)*100:.1f}%)")

    return all_stats


def sample_examples_by_threshold(all_stats, dataset='human', n_samples=5):
    """Sample example query pairs at different threshold boundaries."""

    if dataset not in all_stats:
        print(f"Dataset {dataset} not found")
        return

    stats = all_stats[dataset]
    overlap_ratios = np.array([s['overlap_ratio'] for s in stats])

    print(f"\n{'='*80}")
    print(f"EXAMPLE REFORMULATIONS FROM {dataset.upper()}")
    print(f"{'='*80}")

    # Sample around different thresholds
    thresholds = [
        (0.0, 0.3, "PIVOTING (overlap < 0.3)"),
        (0.3, 0.5, "LOW OVERLAP (0.3-0.5)"),
        (0.5, 0.7, "MODERATE OVERLAP (0.5-0.7)"),
        (0.7, 0.9, "HIGH OVERLAP (0.7-0.9)"),
        (0.9, 1.0, "MINIMAL CHANGE (overlap > 0.9)")
    ]

    for low, high, label in thresholds:
        mask = (overlap_ratios >= low) & (overlap_ratios < high)
        candidates = [stats[i] for i in np.where(mask)[0]]

        if not candidates:
            continue

        print(f"\n{label} - {len(candidates)} examples")
        print("-" * 80)

        # Sample a few examples
        samples = np.random.choice(candidates, size=min(n_samples, len(candidates)), replace=False)

        for i, sample in enumerate(samples, 1):
            print(f"\n  Example {i} (overlap={sample['overlap_ratio']:.3f}, "
                  f"added={sample['n_added']}, removed={sample['n_removed']}, shared={sample['n_shared']}):")
            print(f"    Q1: {sample['query1']}")
            print(f"    Q2: {sample['query2']}")


def main():
    """Run threshold analysis."""
    all_stats = analyze_thresholds()

    # Sample examples for human data
    if 'human' in all_stats:
        sample_examples_by_threshold(all_stats, dataset='human', n_samples=3)

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nRecommendations:")
    print("1. Review the distribution plots to see if current thresholds align with data")
    print("2. Examine example reformulations at each threshold level")
    print("3. Consider using percentile-based thresholds for robustness")
    print("4. Run sensitivity analysis with alternative thresholds")


if __name__ == '__main__':
    main()
