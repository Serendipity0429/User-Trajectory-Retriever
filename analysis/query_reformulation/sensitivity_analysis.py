#!/usr/bin/env python
"""
Sensitivity analysis: Test robustness of findings across different threshold configurations.
Shows that key conclusions hold regardless of specific threshold choices.
"""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from itertools import product
from metrics import load_query_data, extract_trajectories, token_overlap
from collections import Counter


def classify_with_custom_thresholds(query1, query2, max_overlap_for_pivot=0.3,
                                    min_overlap_for_expansion=0.5, threshold_minimal=0.9):
    """Classify reformulation with custom thresholds (corrected logic)."""
    overlap = token_overlap(query1, query2)

    n_added = len(overlap['added'])
    n_removed = len(overlap['removed'])
    n_shared = len(overlap['shared'])
    n_total = n_added + n_removed + n_shared

    if n_total == 0:
        return 'identical'

    overlap_ratio = n_shared / n_total

    # Very high overlap, small change
    if overlap_ratio > threshold_minimal and (n_added + n_removed) <= 2:
        return 'minimal'

    # Check expansion/specification FIRST
    if n_added > 0 and n_removed == 0 and overlap_ratio > min_overlap_for_expansion:
        return 'expansion'

    if n_removed > 0 and n_added == 0 and overlap_ratio > min_overlap_for_expansion:
        return 'specification'

    # Low overlap = topic pivot
    if overlap_ratio < max_overlap_for_pivot:
        return 'pivoting'

    # Mixed = refinement
    return 'refinement'


def compute_diversity_with_thresholds(trajectories, pivot_t, exp_t, min_t):
    """
    Compute reformulation strategy diversity with given thresholds.
    Returns: entropy and strategy counts
    """
    reform_counts = Counter()

    for traj in trajectories:
        queries = traj['queries']
        if len(queries) < 2:
            continue

        for i in range(len(queries) - 1):
            reform_type = classify_with_custom_thresholds(
                queries[i], queries[i+1],
                threshold_pivot=pivot_t,
                threshold_expansion=exp_t,
                threshold_minimal=min_t
            )
            reform_counts[reform_type] += 1

    # Compute Shannon entropy as diversity measure
    total = sum(reform_counts.values())
    if total == 0:
        return 0, reform_counts

    probs = [count / total for count in reform_counts.values()]
    entropy = -sum(p * np.log2(p) for p in probs if p > 0)

    return entropy, reform_counts


def run_sensitivity_analysis(data_dir='extracted_queries', output_dir='outputs/figures'):
    """
    Test multiple threshold configurations and measure impact on key findings.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    print("Running Sensitivity Analysis")
    print("=" * 80)
    print("Testing robustness of findings across different threshold configurations\n")

    # Load data
    dataset_names = ['human', 'rag', 'vanilla_agent', 'browser_agent']
    all_trajectories = {}

    for name in dataset_names:
        filepath = Path(data_dir) / f"{name}_trajectories.json" if name == 'human' else Path(data_dir) / f"{name}.json"

        if not filepath.exists():
            continue

        data = load_query_data(str(filepath))
        all_trajectories[name] = extract_trajectories(data)

    # Define threshold variations to test
    # Current default: pivot=0.7, expansion=0.3, minimal=0.9
    threshold_configs = [
        # (pivot, expansion, minimal, label)
        (0.7, 0.3, 0.9, 'Default'),
        (0.6, 0.3, 0.9, 'Lower pivot'),
        (0.8, 0.3, 0.9, 'Higher pivot'),
        (0.7, 0.2, 0.9, 'Lower expansion'),
        (0.7, 0.4, 0.9, 'Higher expansion'),
        (0.7, 0.3, 0.85, 'Lower minimal'),
        (0.7, 0.3, 0.95, 'Higher minimal'),
        (0.6, 0.2, 0.85, 'All lower'),
        (0.8, 0.4, 0.95, 'All higher'),
    ]

    # Compute diversity for each configuration
    results = []

    for pivot_t, exp_t, min_t, label in threshold_configs:
        for name, trajectories in all_trajectories.items():
            entropy, counts = compute_diversity_with_thresholds(trajectories, pivot_t, exp_t, min_t)

            results.append({
                'dataset': name,
                'config': label,
                'pivot_threshold': pivot_t,
                'expansion_threshold': exp_t,
                'minimal_threshold': min_t,
                'entropy': entropy,
                'total_transitions': sum(counts.values()),
                **{f'pct_{k}': (v / sum(counts.values()) * 100) if sum(counts.values()) > 0 else 0
                   for k, v in counts.items()}
            })

    results_df = pd.DataFrame(results)

    # Save results
    output_csv = Path(output_dir).parent / 'data' / 'sensitivity_analysis_results.csv'
    output_csv.parent.mkdir(exist_ok=True, parents=True)
    results_df.to_csv(output_csv, index=False)
    print(f"Results saved to: {output_csv}\n")

    # Print summary statistics
    print("ENTROPY (Strategy Diversity) Across Threshold Configurations")
    print("=" * 80)

    for name in dataset_names:
        if name not in all_trajectories:
            continue

        subset = results_df[results_df['dataset'] == name]
        print(f"\n{name.upper()}:")
        print(f"  Mean entropy: {subset['entropy'].mean():.3f} ± {subset['entropy'].std():.3f}")
        print(f"  Min entropy: {subset['entropy'].min():.3f} (config: {subset.loc[subset['entropy'].idxmin(), 'config']})")
        print(f"  Max entropy: {subset['entropy'].max():.3f} (config: {subset.loc[subset['entropy'].idxmax(), 'config']})")
        print(f"  Coefficient of variation: {subset['entropy'].std() / subset['entropy'].mean() * 100:.1f}%")

    # Visualize sensitivity
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Entropy across configs
    pivot_data = results_df.pivot(index='config', columns='dataset', values='entropy')
    pivot_data = pivot_data.reindex(['Default', 'Lower pivot', 'Higher pivot', 'Lower expansion',
                                     'Higher expansion', 'Lower minimal', 'Higher minimal',
                                     'All lower', 'All higher'])

    pivot_data.plot(kind='bar', ax=axes[0])
    axes[0].set_title('Strategy Diversity (Entropy) Across Threshold Configurations', fontweight='bold')
    axes[0].set_xlabel('Threshold Configuration')
    axes[0].set_ylabel('Shannon Entropy (bits)')
    axes[0].legend(title='Dataset')
    axes[0].tick_params(axis='x', rotation=45)
    axes[0].grid(axis='y', alpha=0.3)

    # Plot 2: Relative ranking stability
    # Compute mean entropy for each dataset across all configs
    dataset_rankings = []
    for config in results_df['config'].unique():
        subset = results_df[results_df['config'] == config]
        subset_sorted = subset.sort_values('entropy', ascending=False)
        dataset_rankings.append(subset_sorted['dataset'].tolist())

    # Check if ranking is consistent
    from collections import Counter
    position_stability = {name: [] for name in dataset_names}

    for ranking in dataset_rankings:
        for pos, name in enumerate(ranking, 1):
            if name in position_stability:
                position_stability[name].append(pos)

    # Plot ranking positions
    ax = axes[1]
    for name in dataset_names:
        if name not in position_stability or not position_stability[name]:
            continue
        positions = position_stability[name]
        ax.scatter([name] * len(positions), positions, alpha=0.5, s=100)
        ax.plot([name], [np.mean(positions)], 'r*', markersize=15, label='Mean' if name == dataset_names[0] else '')

    ax.set_title('Ranking Stability Across Configurations\n(Lower rank = higher diversity)', fontweight='bold')
    ax.set_ylabel('Rank Position')
    ax.set_xlabel('Dataset')
    ax.set_ylim(0.5, len(dataset_names) + 0.5)
    ax.invert_yaxis()
    ax.grid(axis='y', alpha=0.3)
    if 'Mean' in [h.get_label() for h in ax.get_legend_handles_labels()[0]]:
        ax.legend()

    plt.tight_layout()
    output_plot = output_dir / 'sensitivity_analysis_entropy.png'
    plt.savefig(output_plot, dpi=300, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_plot}")
    plt.show()

    # Statistical test: Is human diversity consistently higher?
    print("\n" + "=" * 80)
    print("KEY FINDING ROBUSTNESS")
    print("=" * 80)

    human_entropies = results_df[results_df['dataset'] == 'human']['entropy'].values
    llm_datasets = ['rag', 'vanilla_agent', 'browser_agent']

    for llm_name in llm_datasets:
        if llm_name not in all_trajectories:
            continue

        llm_entropies = results_df[results_df['dataset'] == llm_name]['entropy'].values

        # Count how many configs show human > LLM
        comparisons = human_entropies > llm_entropies
        consistency = np.mean(comparisons) * 100

        print(f"\nHuman vs. {llm_name.upper()}:")
        print(f"  Human diversity higher in {np.sum(comparisons)}/{len(comparisons)} configs ({consistency:.0f}%)")
        print(f"  Mean difference: {np.mean(human_entropies - llm_entropies):.3f} bits")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    # Check coefficient of variation for all datasets
    cv_values = []
    for name in dataset_names:
        if name not in all_trajectories:
            continue
        subset = results_df[results_df['dataset'] == name]
        cv = subset['entropy'].std() / subset['entropy'].mean() * 100
        cv_values.append(cv)

    avg_cv = np.mean(cv_values)
    print(f"\nAverage coefficient of variation: {avg_cv:.1f}%")

    if avg_cv < 20:
        print("✓ ROBUST: Results show low sensitivity to threshold choices (CV < 20%)")
    elif avg_cv < 30:
        print("~ MODERATE: Results show moderate sensitivity to threshold choices (20% < CV < 30%)")
    else:
        print("✗ SENSITIVE: Results show high sensitivity to threshold choices (CV > 30%)")

    print("\nRecommendation:")
    if avg_cv < 20:
        print("  The current thresholds are reasonable. Key findings are robust.")
    else:
        print("  Consider using data-driven threshold selection or manual validation.")
        print("  Run: python threshold_analysis.py")
        print("  Run: python manual_validation.py --create")


def main():
    run_sensitivity_analysis()


if __name__ == '__main__':
    main()
