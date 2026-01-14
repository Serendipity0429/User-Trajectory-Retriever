#!/usr/bin/env python
"""
Comprehensive Query Reformulation Analysis using Huang & Efthimiadis (2009) Taxonomy

This script performs both single-label and multi-label analysis on query reformulations
across human and LLM trajectories.

Reference:
    Huang, J., & Efthimiadis, E. N. (2009). Analyzing and evaluating query
    reformulation strategies in web search logs. In CIKM '09 (pp. 77-86).
    https://doi.org/10.1145/1645953.1645966
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from metrics_huang2009_extended import (
    classify_reformulation_extended,
    get_extended_reformulation_category
)
from metrics_huang2009 import classify_reformulation_multilabel
from metrics import load_query_data, extract_trajectories

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)


class ReformulationAnalyzer:
    """Analyzer for query reformulation patterns using Huang & Efthimiadis taxonomy."""

    def __init__(self, data_dir='extracted_queries', output_dir='outputs'):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Create subdirectories
        self.figures_dir = self.output_dir / 'figures'
        self.data_out_dir = self.output_dir / 'data'
        self.reports_dir = self.output_dir / 'reports'
        self.figures_dir.mkdir(exist_ok=True, parents=True)
        self.data_out_dir.mkdir(exist_ok=True, parents=True)
        self.reports_dir.mkdir(exist_ok=True, parents=True)

        self.dataset_names = ['human', 'rag', 'vanilla_agent', 'browser_agent']
        self.datasets = {}
        self.trajectories = {}

    def load_data(self):
        """Load all datasets."""
        print("=" * 80)
        print("LOADING DATA")
        print("=" * 80)

        for name in self.dataset_names:
            if name == 'human':
                filepath = self.data_dir / f"{name}_trajectories.json"
            else:
                filepath = self.data_dir / f"{name}.json"

            if not filepath.exists():
                print(f"⊗ {name}: File not found at {filepath}")
                continue

            data = load_query_data(str(filepath))
            trajectories = extract_trajectories(data)

            self.datasets[name] = data
            self.trajectories[name] = trajectories

            # Count query pairs
            n_pairs = sum(len(t['queries']) - 1 for t in trajectories if len(t['queries']) > 1)
            print(f"✓ {name}: {len(trajectories)} trajectories, {n_pairs} query pairs")

        print()

    def analyze_single_label(self) -> pd.DataFrame:
        """
        Single-label analysis: Each query pair gets ONE label based on precedence order.

        Returns:
            DataFrame with reformulation type counts and percentages per dataset
        """
        print("=" * 80)
        print("SINGLE-LABEL ANALYSIS (Precedence-Based)")
        print("=" * 80)
        print("Each query pair classified into ONE category following paper's precedence order\n")

        results = []

        for name in self.dataset_names:
            if name not in self.trajectories:
                continue

            trajectories = self.trajectories[name]
            reform_counts = Counter()
            category_counts = Counter()

            # Collect query pairs
            pairs = []
            for traj in trajectories:
                queries = traj['queries']
                for i in range(len(queries) - 1):
                    q1, q2 = queries[i], queries[i+1]
                    reform_type = classify_reformulation_extended(q1, q2)
                    reform_counts[reform_type] += 1

                    # Also track broader category
                    category = get_extended_reformulation_category(reform_type)
                    category_counts[category] += 1

                    pairs.append({
                        'query1': q1,
                        'query2': q2,
                        'reform_type': reform_type,
                        'category': category
                    })

            total = sum(reform_counts.values())

            print(f"\n{name.upper()}")
            print("-" * 80)
            print(f"Total query pairs: {total}\n")

            # Show detailed reformulation types
            print("Reformulation Types:")
            for reform_type, count in reform_counts.most_common():
                pct = count / total * 100 if total > 0 else 0
                print(f"  {reform_type:25s}: {count:4d} ({pct:5.1f}%)")

            # Show broader categories
            print("\nBroader Categories:")
            for category, count in category_counts.most_common():
                pct = count / total * 100 if total > 0 else 0
                print(f"  {category:20s}: {count:4d} ({pct:5.1f}%)")

            # Store results
            for reform_type, count in reform_counts.items():
                results.append({
                    'dataset': name,
                    'reform_type': reform_type,
                    'category': get_extended_reformulation_category(reform_type),
                    'count': count,
                    'percentage': count / total * 100 if total > 0 else 0
                })

        results_df = pd.DataFrame(results)

        # Save results
        output_file = self.data_out_dir / 'single_label_results.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\n✓ Single-label results saved to: {output_file}")

        return results_df

    def analyze_multi_label(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Multi-label analysis: Each query pair can match MULTIPLE categories.

        Returns:
            Tuple of (label_counts_df, overlap_analysis_df)
        """
        print("\n" + "=" * 80)
        print("MULTI-LABEL ANALYSIS (All Matches)")
        print("=" * 80)
        print("Each query pair can match multiple categories simultaneously\n")

        label_results = []
        overlap_results = []

        for name in self.dataset_names:
            if name not in self.trajectories:
                continue

            trajectories = self.trajectories[name]

            # Track individual labels
            label_counts = Counter()

            # Track combinations
            combination_counts = Counter()
            overlap_examples = defaultdict(list)

            total_pairs = 0
            multi_label_pairs = 0

            for traj in trajectories:
                queries = traj['queries']
                for i in range(len(queries) - 1):
                    q1, q2 = queries[i], queries[i+1]
                    labels = classify_reformulation_multilabel(q1, q2)

                    total_pairs += 1

                    # Count individual labels
                    for label in labels:
                        label_counts[label] += 1

                    # Track combinations
                    if len(labels) > 1:
                        multi_label_pairs += 1
                        combo = tuple(sorted(labels))
                        combination_counts[combo] += 1

                        # Store example
                        if len(overlap_examples[combo]) < 3:
                            overlap_examples[combo].append((q1, q2))

            overlap_pct = multi_label_pairs / total_pairs * 100 if total_pairs > 0 else 0

            print(f"\n{name.upper()}")
            print("-" * 80)
            print(f"Total query pairs: {total_pairs}")
            print(f"Multi-label pairs: {multi_label_pairs} ({overlap_pct:.1f}%)\n")

            # Show label frequencies
            print("Label Frequencies (cumulative):")
            for label, count in label_counts.most_common(10):
                pct = count / total_pairs * 100 if total_pairs > 0 else 0
                print(f"  {label:25s}: {count:4d} ({pct:5.1f}%)")

            # Show top combinations
            if combination_counts:
                print("\nTop Label Combinations:")
                for combo, count in combination_counts.most_common(5):
                    pct = count / multi_label_pairs * 100 if multi_label_pairs > 0 else 0
                    combo_str = ' + '.join(combo)
                    print(f"  {combo_str:50s}: {count:3d} ({pct:5.1f}% of multi-label)")

                    # Show example
                    if combo in overlap_examples and overlap_examples[combo]:
                        q1, q2 = overlap_examples[combo][0]
                        q1_short = q1[:40] + '...' if len(q1) > 40 else q1
                        q2_short = q2[:40] + '...' if len(q2) > 40 else q2
                        print(f"    Example: '{q1_short}' → '{q2_short}'")

            # Store label results
            for label, count in label_counts.items():
                label_results.append({
                    'dataset': name,
                    'label': label,
                    'count': count,
                    'percentage': count / total_pairs * 100 if total_pairs > 0 else 0
                })

            # Store overlap results
            overlap_results.append({
                'dataset': name,
                'total_pairs': total_pairs,
                'multi_label_pairs': multi_label_pairs,
                'overlap_percentage': overlap_pct
            })

            # Store combination details
            for combo, count in combination_counts.items():
                overlap_results.append({
                    'dataset': name,
                    'combination': ' + '.join(combo),
                    'count': count,
                    'percentage_of_overlaps': count / multi_label_pairs * 100 if multi_label_pairs > 0 else 0
                })

        label_df = pd.DataFrame(label_results)
        overlap_df = pd.DataFrame(overlap_results)

        # Save results
        label_file = self.data_out_dir / 'multi_label_results.csv'
        overlap_file = self.data_out_dir / 'overlap_analysis.csv'
        label_df.to_csv(label_file, index=False)
        overlap_df.to_csv(overlap_file, index=False)

        print(f"\n✓ Multi-label results saved to: {label_file}")
        print(f"✓ Overlap analysis saved to: {overlap_file}")

        return label_df, overlap_df

    def visualize_single_label(self, results_df: pd.DataFrame):
        """Create visualizations for single-label analysis."""
        print("\n" + "=" * 80)
        print("CREATING SINGLE-LABEL VISUALIZATIONS")
        print("=" * 80)

        # Figure 1: Reformulation type distribution (percentage)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()

        for idx, name in enumerate(self.dataset_names):
            if name not in results_df['dataset'].values:
                axes[idx].text(0.5, 0.5, f'{name.upper()}\nNo data',
                              ha='center', va='center', fontsize=14)
                axes[idx].axis('off')
                continue

            subset = results_df[results_df['dataset'] == name]

            # Top 10 reformulation types
            top_types = subset.nlargest(10, 'percentage')

            axes[idx].barh(range(len(top_types)), top_types['percentage'],
                          color=sns.color_palette("husl", len(top_types)))
            axes[idx].set_yticks(range(len(top_types)))
            axes[idx].set_yticklabels(top_types['reform_type'], fontsize=10)
            axes[idx].set_xlabel('Percentage (%)', fontsize=11)
            axes[idx].set_title(f'{name.upper()}\n{subset["count"].sum()} query pairs',
                               fontweight='bold', fontsize=12)
            axes[idx].invert_yaxis()
            axes[idx].grid(axis='x', alpha=0.3)

        plt.tight_layout()
        output_file = self.figures_dir / 'single_label_distribution.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {output_file}")
        plt.close()

        # Figure 2: Broader category comparison
        fig, ax = plt.subplots(figsize=(12, 6))

        # Aggregate by broader category
        category_data = results_df.groupby(['dataset', 'category'])['percentage'].sum().reset_index()

        # Pivot for grouped bar chart
        pivot_data = category_data.pivot(index='category', columns='dataset', values='percentage')

        # Filter datasets that exist
        available_datasets = [d for d in self.dataset_names if d in pivot_data.columns]
        pivot_data = pivot_data[available_datasets]

        pivot_data.plot(kind='bar', ax=ax, width=0.8)
        ax.set_title('Reformulation Strategies by Broader Category\n(Huang & Efthimiadis 2009)',
                    fontweight='bold', fontsize=14)
        ax.set_xlabel('Category', fontsize=12)
        ax.set_ylabel('Percentage (%)', fontsize=12)
        ax.legend(title='Dataset', loc='best')
        ax.grid(axis='y', alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        output_file = self.figures_dir / 'single_label_categories.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {output_file}")
        plt.close()

    def visualize_multi_label(self, label_df: pd.DataFrame, overlap_df: pd.DataFrame):
        """Create visualizations for multi-label analysis."""
        print("\n" + "=" * 80)
        print("CREATING MULTI-LABEL VISUALIZATIONS")
        print("=" * 80)

        # Figure 1: Overlap frequency across datasets
        fig, ax = plt.subplots(figsize=(10, 6))

        overlap_summary = overlap_df[overlap_df['total_pairs'].notna()][['dataset', 'overlap_percentage']]

        if not overlap_summary.empty:
            colors = sns.color_palette("viridis", len(overlap_summary))
            bars = ax.bar(overlap_summary['dataset'], overlap_summary['overlap_percentage'], color=colors)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%',
                       ha='center', va='bottom', fontsize=11, fontweight='bold')

            ax.set_title('Multi-Label Query Pairs by Dataset\n(% of query pairs matching multiple categories)',
                        fontweight='bold', fontsize=13)
            ax.set_ylabel('Percentage of Query Pairs (%)', fontsize=12)
            ax.set_xlabel('Dataset', fontsize=12)
            ax.grid(axis='y', alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            output_file = self.figures_dir / 'multi_label_frequency.png'
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {output_file}")
            plt.close()

        # Figure 2: Label comparison (single vs multi-label counts)
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        # Compare label frequencies for human data
        if 'human' in label_df['dataset'].values:
            human_labels = label_df[label_df['dataset'] == 'human']
            top_labels = human_labels.nlargest(12, 'count')

            axes[0].barh(range(len(top_labels)), top_labels['count'], color='steelblue')
            axes[0].set_yticks(range(len(top_labels)))
            axes[0].set_yticklabels(top_labels['label'], fontsize=10)
            axes[0].set_xlabel('Count (Cumulative)', fontsize=11)
            axes[0].set_title('Human: Multi-Label Frequencies\n(Labels can overlap)',
                             fontweight='bold', fontsize=12)
            axes[0].invert_yaxis()
            axes[0].grid(axis='x', alpha=0.3)

        # Most common combinations across all datasets
        combo_data = overlap_df[overlap_df['combination'].notna()]
        if not combo_data.empty:
            # Get top combinations across all datasets
            top_combos = combo_data.groupby('combination')['count'].sum().nlargest(10)

            axes[1].barh(range(len(top_combos)), top_combos.values, color='coral')
            axes[1].set_yticks(range(len(top_combos)))
            axes[1].set_yticklabels([c[:50] for c in top_combos.index], fontsize=9)
            axes[1].set_xlabel('Total Count', fontsize=11)
            axes[1].set_title('Most Common Label Combinations\n(All datasets)',
                             fontweight='bold', fontsize=12)
            axes[1].invert_yaxis()
            axes[1].grid(axis='x', alpha=0.3)

        plt.tight_layout()
        output_file = self.figures_dir / 'multi_label_details.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {output_file}")
        plt.close()

    def generate_summary_report(self, single_df: pd.DataFrame, multi_df: pd.DataFrame, overlap_df: pd.DataFrame):
        """Generate a comprehensive summary report."""
        print("\n" + "=" * 80)
        print("GENERATING SUMMARY REPORT")
        print("=" * 80)

        report_file = self.reports_dir / 'REFORMULATION_ANALYSIS_REPORT.md'

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Query Reformulation Analysis Report\n\n")
            f.write("**Taxonomy**: Huang & Efthimiadis (2009)\n\n")
            f.write("**Reference**: Huang, J., & Efthimiadis, E. N. (2009). Analyzing and evaluating query ")
            f.write("reformulation strategies in web search logs. In CIKM '09 (pp. 77-86). ")
            f.write("https://doi.org/10.1145/1645953.1645966\n\n")
            f.write("---\n\n")

            f.write("## Executive Summary\n\n")
            f.write("This report presents a comprehensive analysis of query reformulation patterns ")
            f.write("across human and LLM search trajectories using the validated Huang & Efthimiadis (2009) ")
            f.write("taxonomy of 13 reformulation types.\n\n")

            f.write("### Key Findings\n\n")

            # Calculate key statistics
            for name in self.dataset_names:
                if name not in single_df['dataset'].values:
                    continue

                subset = single_df[single_df['dataset'] == name]
                total = subset['count'].sum()

                top_type = subset.nlargest(1, 'count').iloc[0]

                overlap_info = overlap_df[
                    (overlap_df['dataset'] == name) &
                    (overlap_df['total_pairs'].notna())
                ]

                if not overlap_info.empty:
                    overlap_pct = overlap_info.iloc[0]['overlap_percentage']
                else:
                    overlap_pct = 0

                f.write(f"**{name.upper()}**:\n")
                f.write(f"- Total query pairs analyzed: {total}\n")
                f.write(f"- Most common reformulation: `{top_type['reform_type']}` ({top_type['percentage']:.1f}%)\n")
                f.write(f"- Multi-label pairs: {overlap_pct:.1f}%\n\n")

            f.write("---\n\n")

            f.write("## Methodology\n\n")
            f.write("### Single-Label Classification\n\n")
            f.write("Each query pair is classified into **ONE** category based on a strict precedence order ")
            f.write("defined in the paper. This approach achieved 98.2% precision on AOL query logs.\n\n")

            f.write("**13 Reformulation Types**:\n")
            types = [
                "1. `word_reorder`: Words reordered without changes",
                "2. `whitespace_punctuation`: Only whitespace/punctuation altered",
                "3. `remove_words`: Terms removed from query",
                "4. `add_words`: Terms added to query",
                "5. `url_stripping`: URL components removed",
                "6. `stemming`: Word forms changed to stems",
                "7. `form_acronym`: Query converted to acronym",
                "8. `expand_acronym`: Acronym expanded",
                "9. `substring`: Query is prefix/suffix of original",
                "10. `superstring`: Query contains original as prefix/suffix",
                "11. `abbreviation`: Corresponding words are prefixes",
                "12. `word_substitution`: Semantically related words (WordNet)",
                "13. `spelling_correction`: Edit distance ≤ 2"
            ]
            for t in types:
                f.write(f"- {t}\n")
            f.write("\n")

            f.write("### Multi-Label Classification\n\n")
            f.write("Query pairs can match **MULTIPLE** categories simultaneously. This reveals ")
            f.write("overlapping reformulation strategies. Common overlaps include:\n\n")
            f.write("- `add_words` + `superstring`\n")
            f.write("- `remove_words` + `substring`\n")
            f.write("- `whitespace_punctuation` + `spelling_correction`\n\n")

            f.write("---\n\n")

            f.write("## Detailed Results\n\n")

            # Single-label results
            f.write("### Single-Label Analysis\n\n")
            for name in self.dataset_names:
                if name not in single_df['dataset'].values:
                    continue

                subset = single_df[single_df['dataset'] == name].sort_values('count', ascending=False)
                total = subset['count'].sum()

                f.write(f"#### {name.upper()}\n\n")
                f.write(f"Total: {total} query pairs\n\n")
                f.write("| Reformulation Type | Count | Percentage |\n")
                f.write("|-------------------|-------|------------|\n")

                for _, row in subset.iterrows():
                    f.write(f"| {row['reform_type']} | {row['count']} | {row['percentage']:.1f}% |\n")
                f.write("\n")

            # Multi-label results
            f.write("### Multi-Label Analysis\n\n")

            overlap_summary = overlap_df[overlap_df['total_pairs'].notna()]
            if not overlap_summary.empty:
                f.write("#### Overlap Frequency\n\n")
                f.write("| Dataset | Total Pairs | Multi-Label Pairs | Percentage |\n")
                f.write("|---------|-------------|-------------------|------------|\n")

                for _, row in overlap_summary.iterrows():
                    f.write(f"| {row['dataset']} | {int(row['total_pairs'])} | ")
                    f.write(f"{int(row['multi_label_pairs'])} | {row['overlap_percentage']:.1f}% |\n")
                f.write("\n")

            f.write("---\n\n")

            f.write("## Files Generated\n\n")
            f.write("### Data Files\n")
            f.write("- `outputs/data/single_label_results.csv`: Single-label classification results\n")
            f.write("- `outputs/data/multi_label_results.csv`: Multi-label classification results\n")
            f.write("- `outputs/data/overlap_analysis.csv`: Overlap patterns and combinations\n\n")

            f.write("### Visualizations\n")
            f.write("- `outputs/figures/single_label_distribution.png`: Reformulation type distributions\n")
            f.write("- `outputs/figures/single_label_categories.png`: Broader category comparison\n")
            f.write("- `outputs/figures/multi_label_frequency.png`: Multi-label frequency by dataset\n")
            f.write("- `outputs/figures/multi_label_details.png`: Label combinations analysis\n\n")

            f.write("### Reports\n")
            f.write("- `outputs/reports/REFORMULATION_ANALYSIS_REPORT.md`: This report\n\n")

            f.write("---\n\n")

            f.write("## Interpretation\n\n")
            f.write("### Human vs LLM Differences\n\n")

            if 'human' in single_df['dataset'].values:
                human_subset = single_df[single_df['dataset'] == 'human']
                human_top3 = human_subset.nlargest(3, 'count')

                f.write("**Human search patterns** show:\n")
                for _, row in human_top3.iterrows():
                    f.write(f"- {row['percentage']:.1f}% `{row['reform_type']}`\n")
                f.write("\n")

            llm_datasets = [d for d in ['rag', 'vanilla_agent', 'browser_agent'] if d in single_df['dataset'].values]
            if llm_datasets:
                f.write("**LLM search patterns** show:\n")
                for llm_name in llm_datasets:
                    llm_subset = single_df[single_df['dataset'] == llm_name]
                    llm_top = llm_subset.nlargest(1, 'count').iloc[0]
                    f.write(f"- {llm_name}: {llm_top['percentage']:.1f}% `{llm_top['reform_type']}`\n")
                f.write("\n")

            f.write("---\n\n")
            f.write("*Report generated using Huang & Efthimiadis (2009) taxonomy*\n")

        print(f"✓ Report saved to: {report_file}")


def main():
    """Run complete reformulation analysis."""
    analyzer = ReformulationAnalyzer()

    # Load data
    analyzer.load_data()

    # Single-label analysis
    single_df = analyzer.analyze_single_label()
    analyzer.visualize_single_label(single_df)

    # Multi-label analysis
    multi_df, overlap_df = analyzer.analyze_multi_label()
    analyzer.visualize_multi_label(multi_df, overlap_df)

    # Generate report
    analyzer.generate_summary_report(single_df, multi_df, overlap_df)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nAll outputs saved to: {analyzer.output_dir}/")
    print(f"  - Data: {analyzer.data_out_dir}/")
    print(f"  - Figures: {analyzer.figures_dir}/")
    print(f"  - Reports: {analyzer.reports_dir}/")
    print(f"  - Main report: {analyzer.reports_dir}/REFORMULATION_ANALYSIS_REPORT.md")


if __name__ == '__main__':
    main()
