#!/usr/bin/env python
"""
Extended Huang & Efthimiadis (2009) Taxonomy with Semantic Reformulation Detection

This extends the original 13-type taxonomy with semantic reformulation types
to reduce the "unclassified" category.

New categories:
- semantic_reformulation: High semantic similarity but different wording
- language_switch: Different languages with semantic equivalence
- complex_refinement: Mixed add/remove/reorder operations
"""

from metrics_huang2009 import classify_reformulation_huang2009, classify_reformulation_multilabel
from metrics import tokenize, token_overlap
import Levenshtein
from typing import Tuple
import re


def detect_language(text: str) -> str:
    """Detect if text is primarily English, Chinese, or mixed."""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(re.sub(r'\s', '', text))

    if total_chars == 0:
        return 'unknown'

    chinese_ratio = chinese_chars / total_chars

    if chinese_ratio > 0.5:
        return 'chinese'
    elif chinese_ratio > 0.1:
        return 'mixed'
    else:
        return 'english'


def is_language_switch(query1: str, query2: str) -> bool:
    """
    Detect if query switched languages (e.g., Chinese ↔ English).

    Example: "CPU的发明者" → "Who developed the central processing unit (cpu)"
    """
    lang1 = detect_language(query1)
    lang2 = detect_language(query2)

    # Different primary languages
    if lang1 != lang2 and lang1 != 'unknown' and lang2 != 'unknown':
        return True

    return False


def is_complex_refinement(query1: str, query2: str) -> bool:
    """
    Detect complex refinements: both add AND remove with significant changes.

    These are queries that modify multiple aspects simultaneously:
    - Add new terms
    - Remove old terms
    - Change word forms or phrasing

    Example: "Kevin psychiatrist" → "Kevin character abstract"
    Example: "Goku vs cell episode" → "In what episode does Goku give up against Cell"
    """
    overlap = token_overlap(query1, query2)

    n_added = len(overlap['added'])
    n_removed = len(overlap['removed'])
    n_shared = len(overlap['shared'])

    # Must have both additions and removals
    if n_added == 0 or n_removed == 0:
        return False

    # Must have at least some shared content
    if n_shared == 0:
        return False

    # Significant changes (not just 1-2 tokens)
    if n_added + n_removed < 2:
        return False

    return True


def is_semantic_reformulation(query1: str, query2: str, similarity_threshold: float = 0.3) -> bool:
    """
    Detect semantic reformulation: different wording but related meaning.

    Uses token overlap as a proxy for semantic similarity.
    If queries share some tokens but also have significant differences,
    they're likely paraphrases.

    Example: "battle ended Britain's support" → "american civil war"
    Example: "Goku give up against Cell" → "Goku cell final"
    """
    overlap = token_overlap(query1, query2)

    n_added = len(overlap['added'])
    n_removed = len(overlap['removed'])
    n_shared = len(overlap['shared'])
    n_total = n_added + n_removed + n_shared

    if n_total == 0:
        return False

    overlap_ratio = n_shared / n_total

    # Low-to-medium overlap with both changes
    if overlap_ratio >= similarity_threshold and overlap_ratio < 0.7:
        if n_added > 0 and n_removed > 0:
            return True

    # Very low overlap but both queries non-empty (topic pivot with connection)
    if overlap_ratio < similarity_threshold and overlap_ratio > 0:
        if n_shared >= 1:  # At least one shared keyword
            return True

    # Complete paraphrase: zero overlap but both non-empty, similar length
    if overlap_ratio == 0 and n_added > 0 and n_removed > 0:
        # Similar query lengths suggest related topics
        len1 = len(tokenize(query1))
        len2 = len(tokenize(query2))
        if len1 > 0 and len2 > 0:
            len_ratio = min(len1, len2) / max(len1, len2)
            if len_ratio > 0.3:  # Within reasonable length range
                return True

    return False


def classify_reformulation_extended(query1: str, query2: str) -> str:
    """
    Extended classification including semantic reformulation types.

    First tries original Huang & Efthimiadis taxonomy (13 types).
    If unclassified, applies extended semantic checks.

    Returns one of:
    - Original 13 types (word_reorder, add_words, etc.)
    - 'language_switch': Different languages
    - 'complex_refinement': Mixed add/remove/reorder
    - 'semantic_reformulation': Paraphrasing/rewording
    - 'unclassified': Truly unclassifiable
    """
    # Try original taxonomy first
    original_classification = classify_reformulation_huang2009(query1, query2)

    if original_classification != 'unclassified':
        return original_classification

    # Apply extended rules for unclassified pairs

    # Check language switch first (strongest signal)
    if is_language_switch(query1, query2):
        return 'language_switch'

    # Check complex refinement
    if is_complex_refinement(query1, query2):
        return 'complex_refinement'

    # Check semantic reformulation
    if is_semantic_reformulation(query1, query2):
        return 'semantic_reformulation'

    # Still unclassified
    return 'unclassified'


def get_extended_reformulation_category(reformulation_type: str) -> str:
    """
    Map extended reformulation types to broader categories.

    Returns one of: 'lexical', 'semantic', 'structural', 'error_correction', 'other'
    """
    lexical = {'add_words', 'remove_words', 'substring', 'superstring',
               'abbreviation', 'stemming', 'form_acronym', 'expand_acronym'}

    semantic = {'word_substitution', 'semantic_reformulation', 'complex_refinement',
                'language_switch'}

    structural = {'word_reorder', 'whitespace_punctuation', 'url_stripping'}

    error_correction = {'spelling_correction'}

    if reformulation_type in lexical:
        return 'lexical'
    elif reformulation_type in semantic:
        return 'semantic'
    elif reformulation_type in structural:
        return 'structural'
    elif reformulation_type in error_correction:
        return 'error_correction'
    else:
        return 'other'


if __name__ == '__main__':
    # Test extended classification on problematic examples
    test_cases = [
        ("battle ended Britain's support for the South", "american civil war", "semantic_reformulation"),
        ("太空堡垒卡拉狄加中布玛什么时候发现自己是赛隆人", "Boomer find out she a Cylon", "language_switch"),
        ("CPU的发明者", "Who developed the central processing unit (cpu)", "language_switch"),
        ("Kevin (Probably) Saves the World Kevin psychiatrist", "Kevin (Probably) Saves the World character abstract", "complex_refinement"),
        ("Goku give up against Cell", "Goku cell final", "complex_refinement"),
        ("how to check chrome for linux updates", "how to check chrome for linux history versions", "complex_refinement"),
        ("seattle pizza palace", "pizza seattle palace", "word_reorder"),
        ("eastlake home", "eastlake home price index", "add_words"),
    ]

    print("Testing Extended Huang & Efthimiadis Taxonomy")
    print("=" * 80)

    correct = 0
    for q1, q2, expected in test_cases:
        result = classify_reformulation_extended(q1, q2)
        status = "✓" if result == expected else "✗"
        correct += (result == expected)

        q1_short = q1[:50] + '...' if len(q1) > 50 else q1
        q2_short = q2[:50] + '...' if len(q2) > 50 else q2

        print(f"{status} '{q1_short}' → '{q2_short}'")
        print(f"  Expected: {expected}, Got: {result}\n")

    print(f"Accuracy: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.1f}%)")
