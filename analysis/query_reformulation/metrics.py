"""
Utility functions for query diversity and reformulation analysis.
"""

import json
import numpy as np
from typing import List, Dict, Tuple, Set
from collections import Counter
import re
from scipy.spatial.distance import cosine
from scipy.stats import mannwhitneyu, kruskal
import Levenshtein


def load_query_data(filepath: str) -> Dict:
    """Load query data from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_query(query: str) -> str:
    """Normalize query text (lowercase, whitespace handling)."""
    query = query.lower().strip()
    query = re.sub(r'\s+', ' ', query)  # Replace multiple spaces with single space
    return query


def tokenize(text: str) -> List[str]:
    """Simple tokenization: split on whitespace and punctuation."""
    # Keep words and numbers, remove punctuation
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens


# === Lexical Diversity Metrics ===

def type_token_ratio(queries: List[str]) -> float:
    """
    Calculate Type-Token Ratio (TTR) for a list of queries.
    TTR = unique tokens / total tokens
    """
    all_tokens = []
    for q in queries:
        all_tokens.extend(tokenize(q))

    if len(all_tokens) == 0:
        return 0.0

    unique_tokens = len(set(all_tokens))
    total_tokens = len(all_tokens)
    return unique_tokens / total_tokens


def moving_average_ttr(queries: List[str], window_size: int = 10) -> float:
    """
    Calculate Moving-Average TTR (MATTR) with specified window size.
    Addresses the sensitivity of TTR to text length.
    """
    all_tokens = []
    for q in queries:
        all_tokens.extend(tokenize(q))

    if len(all_tokens) < window_size:
        return type_token_ratio(queries)

    ttrs = []
    for i in range(len(all_tokens) - window_size + 1):
        window = all_tokens[i:i + window_size]
        window_ttr = len(set(window)) / len(window)
        ttrs.append(window_ttr)

    return np.mean(ttrs)


def vocabulary_size(queries: List[str]) -> int:
    """Count unique tokens across all queries."""
    all_tokens = set()
    for q in queries:
        all_tokens.update(tokenize(q))
    return len(all_tokens)


def ngram_coverage(queries: List[str], n: int = 2) -> Dict[str, int]:
    """
    Generate n-gram frequency distribution.
    Returns dict of n-gram -> count
    """
    ngrams = []
    for q in queries:
        tokens = tokenize(q)
        if len(tokens) >= n:
            for i in range(len(tokens) - n + 1):
                ngram = ' '.join(tokens[i:i+n])
                ngrams.append(ngram)

    return dict(Counter(ngrams))


def query_length_stats(queries: List[str]) -> Dict[str, float]:
    """
    Calculate query length statistics (words and characters).
    Returns dict with mean, std, min, max for both.
    """
    word_lengths = [len(tokenize(q)) for q in queries]
    char_lengths = [len(q) for q in queries]

    return {
        'mean_words': np.mean(word_lengths) if word_lengths else 0,
        'std_words': np.std(word_lengths) if word_lengths else 0,
        'min_words': np.min(word_lengths) if word_lengths else 0,
        'max_words': np.max(word_lengths) if word_lengths else 0,
        'mean_chars': np.mean(char_lengths) if char_lengths else 0,
        'std_chars': np.std(char_lengths) if char_lengths else 0,
        'min_chars': np.min(char_lengths) if char_lengths else 0,
        'max_chars': np.max(char_lengths) if char_lengths else 0,
    }


# === Semantic Diversity Metrics ===

def intra_session_similarity(query_embeddings: np.ndarray) -> float:
    """
    Calculate average pairwise cosine similarity within a session.
    Lower similarity = higher diversity
    """
    if len(query_embeddings) < 2:
        return 0.0

    similarities = []
    for i in range(len(query_embeddings)):
        for j in range(i + 1, len(query_embeddings)):
            sim = 1 - cosine(query_embeddings[i], query_embeddings[j])
            similarities.append(sim)

    return np.mean(similarities) if similarities else 0.0


def inter_session_similarity(all_session_embeddings: List[np.ndarray]) -> float:
    """
    Calculate average similarity between different sessions (for same question).
    Each session represented by mean of its query embeddings.
    """
    if len(all_session_embeddings) < 2:
        return 0.0

    session_means = [np.mean(sess_embs, axis=0) for sess_embs in all_session_embeddings]

    similarities = []
    for i in range(len(session_means)):
        for j in range(i + 1, len(session_means)):
            sim = 1 - cosine(session_means[i], session_means[j])
            similarities.append(sim)

    return np.mean(similarities) if similarities else 0.0


# === Reformulation Strategy Detection ===

def edit_distance(query1: str, query2: str) -> int:
    """Calculate Levenshtein edit distance between two queries."""
    return Levenshtein.distance(query1, query2)


def token_overlap(query1: str, query2: str) -> Dict[str, Set[str]]:
    """
    Analyze token-level changes between consecutive queries.
    Returns: {
        'added': tokens in query2 but not query1,
        'removed': tokens in query1 but not query2,
        'shared': tokens in both
    }
    """
    tokens1 = set(tokenize(query1))
    tokens2 = set(tokenize(query2))

    return {
        'added': tokens2 - tokens1,
        'removed': tokens1 - tokens2,
        'shared': tokens1 & tokens2
    }


def classify_reformulation(query1: str, query2: str,
                          min_overlap_for_expansion: float = 0.5,
                          max_overlap_for_pivot: float = 0.3) -> str:
    """
    Classify reformulation type based on token overlap.

    DATA-DRIVEN THRESHOLDS (from human trajectory analysis):
    - Human overlap median: 0.625, 25th percentile: 0.182, 75th percentile: 1.000
    - Pivot threshold (0.3): Bottom ~30% of overlaps = true topic changes
    - Expansion threshold (0.5): Above median = clear additions with context retained
    - Minimal threshold (0.9): Top ~10% with ≤2 changes = typos/minor edits

    Types:
    - 'expansion': Adds terms while retaining context (overlap > 0.5, only additions)
    - 'specification': Removes terms to focus (overlap > 0.5, only removals)
    - 'refinement': Mixed changes (medium overlap, both add and remove)
    - 'pivoting': Major topic change (overlap < 0.3)
    - 'minimal': Very small change (overlap > 0.9, ≤2 token changes)

    Args:
        min_overlap_for_expansion: Minimum overlap for expansion/specification (default: 0.5)
        max_overlap_for_pivot: Maximum overlap for pivoting (default: 0.3)
    """
    overlap = token_overlap(query1, query2)

    n_added = len(overlap['added'])
    n_removed = len(overlap['removed'])
    n_shared = len(overlap['shared'])
    n_total = n_added + n_removed + n_shared

    if n_total == 0:
        return 'identical'

    overlap_ratio = n_shared / n_total

    # Very high overlap, small change
    if overlap_ratio > 0.9 and (n_added + n_removed) <= 2:
        return 'minimal'

    # Check expansion/specification FIRST (before pivot check)
    # High overlap with additions = expansion
    if n_added > 0 and n_removed == 0 and overlap_ratio > min_overlap_for_expansion:
        return 'expansion'

    # High overlap with removals = specification
    if n_removed > 0 and n_added == 0 and overlap_ratio > min_overlap_for_expansion:
        return 'specification'

    # Low overlap = topic pivot
    if overlap_ratio < max_overlap_for_pivot:
        return 'pivoting'

    # Medium overlap with mixed changes = refinement
    return 'refinement'


def detect_backtracking(query_history: List[str], current_idx: int,
                       similarity_threshold: float = 0.8) -> Tuple[bool, int]:
    """
    Detect if current query is backtracking to an earlier query.
    Returns: (is_backtracking, index_of_similar_earlier_query)
    """
    if current_idx < 2:
        return False, -1

    current_query = query_history[current_idx]
    current_tokens = set(tokenize(current_query))

    # Check against earlier queries (not immediate predecessor)
    for i in range(current_idx - 2, -1, -1):
        earlier_query = query_history[i]
        earlier_tokens = set(tokenize(earlier_query))

        # Calculate Jaccard similarity
        intersection = len(current_tokens & earlier_tokens)
        union = len(current_tokens | earlier_tokens)

        if union > 0:
            jaccard = intersection / union
            if jaccard >= similarity_threshold:
                return True, i

    return False, -1


def reformulation_transition_matrix(trajectories: List[List[str]]) -> np.ndarray:
    """
    Build transition matrix of reformulation types.
    Rows = current reformulation type, Cols = next reformulation type
    """
    reformulation_types = ['expansion', 'refinement', 'pivoting', 'specification',
                          'minimal', 'backtracking']
    n_types = len(reformulation_types)
    type_to_idx = {rt: i for i, rt in enumerate(reformulation_types)}

    transition_counts = np.zeros((n_types, n_types))

    for trajectory in trajectories:
        if len(trajectory) < 3:
            continue

        reform_sequence = []
        for i in range(len(trajectory) - 1):
            reform_type = classify_reformulation(trajectory[i], trajectory[i+1])
            reform_sequence.append(reform_type)

        # Count transitions
        for i in range(len(reform_sequence) - 1):
            curr_type = reform_sequence[i]
            next_type = reform_sequence[i+1]

            if curr_type in type_to_idx and next_type in type_to_idx:
                curr_idx = type_to_idx[curr_type]
                next_idx = type_to_idx[next_type]
                transition_counts[curr_idx, next_idx] += 1

    # Normalize to get probabilities
    row_sums = transition_counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    transition_probs = transition_counts / row_sums

    return transition_probs


# === Statistical Tests ===

def compare_distributions(group1: List[float], group2: List[float],
                         test: str = 'mannwhitney') -> Dict:
    """
    Compare two distributions using specified statistical test.

    Args:
        group1: First group of values
        group2: Second group of values
        test: 'mannwhitney' or 'kruskal'

    Returns:
        Dict with statistic, p-value, and effect size (Cohen's d)
    """
    if test == 'mannwhitney':
        stat, pval = mannwhitneyu(group1, group2, alternative='two-sided')
    else:
        stat, pval = kruskal(group1, group2)

    # Calculate Cohen's d effect size
    mean1, mean2 = np.mean(group1), np.mean(group2)
    std1, std2 = np.std(group1), np.std(group2)
    pooled_std = np.sqrt((std1**2 + std2**2) / 2)
    cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0

    return {
        'statistic': stat,
        'p_value': pval,
        'cohens_d': cohens_d,
        'mean_group1': mean1,
        'mean_group2': mean2,
        'significant': pval < 0.05
    }


# === Trajectory Analysis ===

def extract_trajectories(data: Dict) -> List[Dict]:
    """
    Extract all query trajectories from nested data structure.

    Returns list of trajectory dicts with:
    - question: question text
    - trajectory_id: session/user ID
    - queries: list of query strings
    - metadata: additional info
    """
    trajectories = []

    for question, question_data in data.items():
        for traj_id, turns_data in question_data.get('trajectories', {}).items():
            queries = []
            metadata = []

            for turn_num in sorted(turns_data.keys(), key=lambda x: int(x)):
                turn_queries = turns_data[turn_num]
                for q in turn_queries:
                    queries.append(q['query'])
                    metadata.append({
                        'turn': turn_num,
                        'source': q.get('source'),
                        'domain': q.get('domain'),
                        'url': q.get('url'),
                        'timestamp': q.get('timestamp')
                    })

            trajectories.append({
                'question': question_data.get('question', question),
                'trajectory_id': traj_id,
                'queries': queries,
                'metadata': metadata,
                'num_queries': len(queries),
                'num_turns': len(turns_data)
            })

    return trajectories


def session_metrics(trajectory: Dict) -> Dict:
    """Calculate all metrics for a single session/trajectory."""
    queries = trajectory['queries']

    if not queries:
        return {}

    metrics = {
        'ttr': type_token_ratio(queries),
        'mattr': moving_average_ttr(queries),
        'vocab_size': vocabulary_size(queries),
        'num_queries': len(queries),
        'num_turns': trajectory['num_turns'],
    }

    # Add length stats
    metrics.update(query_length_stats(queries))

    # Reformulation types
    reform_types = []
    for i in range(len(queries) - 1):
        reform_type = classify_reformulation(queries[i], queries[i+1])
        reform_types.append(reform_type)

    if reform_types:
        reform_counts = Counter(reform_types)
        for rtype in ['expansion', 'refinement', 'pivoting', 'specification', 'minimal']:
            metrics[f'reform_{rtype}'] = reform_counts.get(rtype, 0)

    return metrics
