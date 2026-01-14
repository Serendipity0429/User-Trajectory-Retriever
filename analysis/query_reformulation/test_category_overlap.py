#!/usr/bin/env python
"""
Test whether Huang & Efthimiadis (2009) reformulation categories are mutually exclusive.
Answers: Does the order of if clauses matter? Should we use multi-label classification?
"""

from metrics_huang2009 import (
    is_word_reorder, is_whitespace_punctuation, is_remove_words, is_add_words,
    is_url_stripping, is_stemming, is_form_acronym, is_expand_acronym,
    is_substring, is_superstring, is_abbreviation, is_word_substitution,
    is_spelling_correction
)

# All detection functions
DETECTORS = [
    ('word_reorder', is_word_reorder),
    ('whitespace_punctuation', is_whitespace_punctuation),
    ('remove_words', is_remove_words),
    ('add_words', is_add_words),
    ('url_stripping', is_url_stripping),
    ('stemming', is_stemming),
    ('form_acronym', is_form_acronym),
    ('expand_acronym', is_expand_acronym),
    ('substring', is_substring),
    ('superstring', is_superstring),
    ('abbreviation', is_abbreviation),
    ('word_substitution', is_word_substitution),
    ('spelling_correction', is_spelling_correction),
]


def find_all_matching_categories(query1, query2):
    """Run ALL detection functions and return all matches (multi-label)."""
    matches = []
    for name, detector in DETECTORS:
        try:
            if detector(query1, query2):
                matches.append(name)
        except:
            pass  # Some detectors may fail without NLTK
    return matches


def test_mutual_exclusivity():
    """Test whether categories overlap for various query pairs."""

    test_cases = [
        # From paper examples
        ("seattle pizza palace", "pizza seattle palace"),
        ("wal mart", "walmart"),
        ("yahoo stock price", "price yahoo"),
        ("eastlake home", "eastlake home price index"),
        ("http www.yahoo.com", "yahoo"),
        ("running over bridges", "run over bridge"),
        ("personal computer", "pc"),
        ("pda", "personal digital assistant"),
        ("is there spyware on my computer", "is there spywa"),
        ("nevada police rec", "nevada police records 2008"),
        ("shortened dict", "short dictionary"),
        ("easter egg search", "easter egg hunt"),
        ("reformualtion", "reformulation"),

        # Additional edge cases that might overlap
        ("walmart", "wal mart"),  # Reverse of whitespace
        ("ny times", "newyorktimes"),  # Could be whitespace + spelling?
        ("usa", "united states america"),  # Acronym + add words?
        ("searching google", "search google"),  # Stemming + remove words?
        ("comp sci", "computer science"),  # Abbreviation + add words?
        ("weather nyc", "weather new york city"),  # Acronym expansion?
    ]

    print("=" * 80)
    print("TESTING CATEGORY OVERLAP")
    print("=" * 80)
    print("\nQuestion: Are Huang & Efthimiadis categories mutually exclusive?")
    print("Method: Run ALL detection functions, see if multiple categories match\n")

    overlapping_count = 0
    total_pairs = 0

    for q1, q2 in test_cases:
        matches = find_all_matching_categories(q1, q2)
        total_pairs += 1

        if len(matches) > 1:
            overlapping_count += 1
            print(f"✗ OVERLAP FOUND:")
            print(f"  '{q1}' → '{q2}'")
            print(f"  Matches: {matches}")
            print()
        elif len(matches) == 1:
            print(f"✓ Single match: '{q1}' → '{q2}'")
            print(f"  Category: {matches[0]}")
        else:
            print(f"○ No match: '{q1}' → '{q2}'")
        print()

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total pairs tested: {total_pairs}")
    print(f"Pairs with multiple matches: {overlapping_count} ({overlapping_count/total_pairs*100:.1f}%)")
    print(f"Pairs with single match: {total_pairs - overlapping_count}")

    if overlapping_count > 0:
        print("\n⚠️  CATEGORIES ARE NOT MUTUALLY EXCLUSIVE")
        print("\nImplications:")
        print("1. YES, the order of if clauses DOES matter")
        print("2. Current implementation uses PRECEDENCE ORDER from the paper")
        print("3. This prioritizes certain types over others")
        print("\nShould we use multi-label classification?")
        print("  PROS:")
        print("    - Captures full complexity of reformulations")
        print("    - More accurate representation of user behavior")
        print("    - Could reveal interesting co-occurrence patterns")
        print("  CONS:")
        print("    - More complex analysis (need to handle label combinations)")
        print("    - Harder to visualize and interpret")
        print("    - Deviates from the paper's validated approach (98.2% precision)")
        print("\nRECOMMENDATION:")
        print("  - Keep single-label for PRIMARY analysis (follows paper)")
        print("  - Add OPTIONAL multi-label analysis for deeper insights")
        print("  - Document that precedence order follows Huang & Efthimiadis (2009)")
    else:
        print("\n✓ CATEGORIES ARE MUTUALLY EXCLUSIVE")
        print("Order of if clauses does NOT matter for correctness")


if __name__ == '__main__':
    test_mutual_exclusivity()
