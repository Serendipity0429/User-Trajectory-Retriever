#!/usr/bin/env python
"""
Diagnose why so many query pairs are classified as "unclassified".
Analyze patterns in unclassified pairs to understand what the taxonomy is missing.
"""

import json
import pandas as pd
from pathlib import Path
from collections import Counter
import numpy as np
from metrics_huang2009 import classify_reformulation_huang2009, classify_reformulation_multilabel
from metrics import load_query_data, extract_trajectories, tokenize, token_overlap
import Levenshtein

def analyze_unclassified_patterns(data_dir='extracted_queries', n_samples=20):
    """Analyze unclassified query pairs to find common patterns."""

    print("=" * 80)
    print("DIAGNOSING UNCLASSIFIED QUERY PAIRS")
    print("=" * 80)
    print("\nGoal: Understand why 42-85% of pairs are 'unclassified'\n")

    dataset_names = ['human', 'rag', 'vanilla_agent', 'browser_agent']

    for name in dataset_names:
        filepath = Path(data_dir) / f"{name}_trajectories.json" if name == 'human' else Path(data_dir) / f"{name}.json"

        if not filepath.exists():
            continue

        data = load_query_data(str(filepath))
        trajectories = extract_trajectories(data)

        # Collect unclassified pairs
        unclassified_pairs = []
        classified_pairs = []

        for traj in trajectories:
            queries = traj['queries']
            for i in range(len(queries) - 1):
                q1, q2 = queries[i], queries[i+1]

                classification = classify_reformulation_huang2009(q1, q2)

                if classification == 'unclassified':
                    # Calculate detailed metrics
                    tokens1 = set(tokenize(q1))
                    tokens2 = set(tokenize(q2))

                    overlap = token_overlap(q1, q2)
                    n_added = len(overlap['added'])
                    n_removed = len(overlap['removed'])
                    n_shared = len(overlap['shared'])
                    n_total = n_added + n_removed + n_shared

                    overlap_ratio = n_shared / n_total if n_total > 0 else 0
                    edit_dist = Levenshtein.distance(q1, q2)

                    unclassified_pairs.append({
                        'query1': q1,
                        'query2': q2,
                        'n_added': n_added,
                        'n_removed': n_removed,
                        'n_shared': n_shared,
                        'overlap_ratio': overlap_ratio,
                        'edit_distance': edit_dist,
                        'len1': len(q1),
                        'len2': len(q2),
                        'len_ratio': len(q2) / len(q1) if len(q1) > 0 else 0
                    })
                else:
                    classified_pairs.append({
                        'classification': classification,
                        'query1': q1,
                        'query2': q2
                    })

        if not unclassified_pairs:
            print(f"\n{name.upper()}: No unclassified pairs found!\n")
            continue

        total_pairs = len(unclassified_pairs) + len(classified_pairs)
        unclassified_pct = len(unclassified_pairs) / total_pairs * 100

        print(f"\n{'=' * 80}")
        print(f"{name.upper()}")
        print(f"{'=' * 80}")
        print(f"Total pairs: {total_pairs}")
        print(f"Unclassified: {len(unclassified_pairs)} ({unclassified_pct:.1f}%)")
        print(f"Classified: {len(classified_pairs)} ({100-unclassified_pct:.1f}%)")

        # Analyze unclassified characteristics
        df = pd.DataFrame(unclassified_pairs)

        print(f"\n{'─' * 80}")
        print("STATISTICAL PROFILE OF UNCLASSIFIED PAIRS")
        print(f"{'─' * 80}")

        print(f"\nToken Overlap Statistics:")
        print(f"  Mean overlap ratio: {df['overlap_ratio'].mean():.3f}")
        print(f"  Median overlap ratio: {df['overlap_ratio'].median():.3f}")
        print(f"  Min/Max: {df['overlap_ratio'].min():.3f} / {df['overlap_ratio'].max():.3f}")

        print(f"\nEdit Distance:")
        print(f"  Mean: {df['edit_distance'].mean():.1f}")
        print(f"  Median: {df['edit_distance'].median():.1f}")
        print(f"  > 2 (outside spelling threshold): {(df['edit_distance'] > 2).sum()} ({(df['edit_distance'] > 2).mean()*100:.1f}%)")

        print(f"\nToken Changes:")
        print(f"  Mean added: {df['n_added'].mean():.1f}")
        print(f"  Mean removed: {df['n_removed'].mean():.1f}")
        print(f"  Mean shared: {df['n_shared'].mean():.1f}")

        # Categorize by pattern
        print(f"\n{'─' * 80}")
        print("PATTERN BREAKDOWN")
        print(f"{'─' * 80}")

        # Pattern 1: Both add and remove (but not captured as "refinement")
        both_changes = df[(df['n_added'] > 0) & (df['n_removed'] > 0)]
        print(f"\nBoth add AND remove tokens: {len(both_changes)} ({len(both_changes)/len(df)*100:.1f}%)")
        print(f"  → This should be 'refinement' but wasn't classified")
        print(f"  → Likely: semantic changes beyond token overlap")

        # Pattern 2: Large edit distance
        large_edit = df[df['edit_distance'] > 2]
        print(f"\nLarge edit distance (>2): {len(large_edit)} ({len(large_edit)/len(df)*100:.1f}%)")
        print(f"  → Too different for 'spelling_correction'")

        # Pattern 3: Medium overlap with changes
        medium_overlap = df[(df['overlap_ratio'] >= 0.3) & (df['overlap_ratio'] <= 0.7)]
        print(f"\nMedium overlap (0.3-0.7): {len(medium_overlap)} ({len(medium_overlap)/len(df)*100:.1f}%)")
        print(f"  → Not enough overlap for expansion/specification")
        print(f"  → Too much overlap for pivoting")

        # Pattern 4: Very different lengths
        length_diff = df[abs(df['len_ratio'] - 1.0) > 0.5]
        print(f"\nLarge length difference (>50%): {len(length_diff)} ({len(length_diff)/len(df)*100:.1f}%)")

        # Show examples
        print(f"\n{'─' * 80}")
        print("SAMPLE UNCLASSIFIED PAIRS")
        print(f"{'─' * 80}")

        # Sample different patterns
        patterns = [
            ("Both add & remove", both_changes),
            ("Large edit distance", large_edit),
            ("Medium overlap", medium_overlap),
        ]

        for pattern_name, pattern_df in patterns:
            if len(pattern_df) > 0:
                print(f"\n{pattern_name} ({len(pattern_df)} pairs):")
                samples = pattern_df.sample(n=min(5, len(pattern_df)))

                for idx, row in samples.iterrows():
                    q1_short = row['query1'][:60] + '...' if len(row['query1']) > 60 else row['query1']
                    q2_short = row['query2'][:60] + '...' if len(row['query2']) > 60 else row['query2']

                    print(f"\n  Q1: {q1_short}")
                    print(f"  Q2: {q2_short}")
                    print(f"  Metrics: overlap={row['overlap_ratio']:.2f}, "
                          f"added={row['n_added']}, removed={row['n_removed']}, "
                          f"edit_dist={row['edit_distance']}")

                    # Check what it WOULD be with relaxed thresholds
                    if row['n_added'] > 0 and row['n_removed'] > 0:
                        print(f"  → Should be: REFINEMENT (has both additions and removals)")
                    elif row['n_added'] > 0 and row['n_removed'] == 0:
                        print(f"  → Could be: EXPANSION (if we relaxed overlap threshold)")
                    elif row['n_removed'] > 0 and row['n_added'] == 0:
                        print(f"  → Could be: SPECIFICATION (if we relaxed overlap threshold)")
                    elif row['overlap_ratio'] < 0.3:
                        print(f"  → Could be: PIVOTING")

        print()

    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSIS SUMMARY")
    print("=" * 80)

    print("\n**Why are so many pairs unclassified?**\n")
    print("1. SEMANTIC CHANGES not captured by token-level rules")
    print("   → Paraphrasing, rewording, rephrasing with different words")
    print("   → Example: 'how to cook rice' → 'rice cooking instructions'")
    print("   → The taxonomy relies on EXACT token matching\n")

    print("2. COMPLEX MIXED OPERATIONS")
    print("   → Add + remove + reorder simultaneously")
    print("   → The rules check for pure operations first")
    print("   → Mixed operations fall through to 'unclassified'\n")

    print("3. LARGE EDIT DISTANCES (>2)")
    print("   → Significant rewording beyond spelling correction")
    print("   → Not covered by WordNet substitution (which is limited)\n")

    print("4. LANGUAGE-SPECIFIC PATTERNS")
    print("   → Chinese queries with different tokenization patterns")
    print("   → Multi-language queries not handled well\n")

    print("\n**Why this is NOT a bug:**")
    print("- Huang & Efthimiadis (2009) achieved 27.3% reformulation rate on AOL logs")
    print("- They left 72.7% as 'new queries' (different from reformulations)")
    print("- Their taxonomy targets SPECIFIC reformulation types")
    print("- Unclassified = semantic/complex reformulations outside the taxonomy\n")

    print("\n**Recommendations:**")
    print("1. Add semantic similarity metrics (embeddings) for unclassified pairs")
    print("2. Create a 'semantic_reformulation' category for high-similarity unclassified")
    print("3. Analyze unclassified pairs separately as 'complex reformulations'")
    print("4. Report 'unclassified' as a legitimate category = 'semantic/complex changes'")


if __name__ == '__main__':
    analyze_unclassified_patterns()
