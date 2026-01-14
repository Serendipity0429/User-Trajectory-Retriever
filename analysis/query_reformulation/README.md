# Query Formulation & Reformulation Analysis

**Analyzing the differences between human and LLM query behavior in open-domain question answering**

Dataset: `nq_hard_questions` (tutorial questions excluded)

---

## Overview

This analysis investigates why humans outperform LLMs in open-domain question answering by examining query diversity and reformulation strategies. Through mixed-methods analysis combining quantitative metrics and qualitative trajectory analysis, we extract actionable strategies for LLM improvement.

### Research Questions

1. **RQ1 (Diversity Gap):** How much more diverse are human queries compared to LLM queries?
2. **RQ2 (Reformulation Sophistication):** Do humans use more varied reformulation strategies?
3. **RQ3 (Exploratory Depth):** Do humans explore more topics/branches before converging?
4. **RQ4 (Recovery Mechanisms):** How do humans recover from unproductive search paths?
5. **RQ5 (Knowledge Gaps):** Where do LLMs show systematic knowledge gaps vs. humans?

---

## Project Structure

```
query_reformulation/
├── README.md                          # This file
├── METRICS_DOCUMENTATION.md           # Complete metric definitions
├── metrics.py                         # Metric calculation utilities
├── query_analysis.ipynb               # Main analysis notebook
├── extract_human_queries.py           # Data extraction (human)
├── extract_llm_queries.py             # Data extraction (LLM)
├── threshold_analysis.py              # Data-driven threshold selection
├── manual_validation.py               # Manual label validation tool
├── sensitivity_analysis.py            # Robustness testing
├── extracted_queries/                 # Raw query data (JSON)
│   ├── human_trajectories.json
│   ├── rag.json
│   ├── vanilla_agent.json
│   └── browser_agent.json
└── outputs/                           # All analysis results
    ├── README.md                      # Output documentation
    ├── data/                          # CSV files
    │   ├── 01_dataset_summary.csv
    │   ├── 02_aggregate_lexical_metrics.csv
    │   ├── 03_statistical_tests.csv
    │   ├── 04_reformulation_statistics.csv
    │   ├── 05_all_session_metrics.csv
    │   └── sensitivity_analysis_results.csv  # Threshold robustness
    ├── figures/                       # Visualizations
    │   ├── 01_lexical_diversity_comparison.png
    │   ├── 02_reformulation_strategies.png
    │   ├── threshold_analysis_distributions.png
    │   └── sensitivity_analysis_entropy.png
    └── reports/                       # Analysis reports (generated)
```

---

## Quick Start

### 1. Data Extraction

Extract queries from the `nq_hard_questions` dataset:

```bash
# Extract human queries
cd Platform
python ../analysis/query_reformulation/extract_human_queries.py

# LLM queries (already extracted from benchmark data)
cd ../analysis/query_reformulation
python extract_llm_queries.py
```

### 2. (Recommended) Validate Reformulation Thresholds

**Important:** The reformulation classification uses heuristic thresholds (see "Threshold Validation" section below). We recommend running sensitivity analysis to ensure robustness:

```bash
# Test robustness across different threshold configurations
python sensitivity_analysis.py
```

If sensitivity is high (CV > 30%), consider:
- Data-driven threshold selection: `python threshold_analysis.py`
- Manual validation: `python manual_validation.py --create`

### 3. Run Analysis

```bash
cd analysis/query_reformulation
jupyter notebook query_analysis.ipynb
# Run all cells
```

### 4. View Results

All outputs are saved to `outputs/`:
- **Data:** CSV files with metrics and statistics
- **Figures:** Publication-quality visualizations
- **Reports:** Comprehensive analysis documents

See `outputs/README.md` for detailed file descriptions.

---

## Threshold Validation

### Problem Statement

The reformulation classification in `metrics.py` uses **heuristic token-overlap thresholds**:
- `pivot_threshold = 0.7` (overlap < 0.7 = pivoting)
- `expansion_threshold = 0.3` (overlap > 0.3 with additions = expansion)
- `minimal_threshold = 0.9` (overlap > 0.9 with ≤2 changes = minimal)

These thresholds are **empirically chosen** for this analysis, not derived from a published algorithm. We provide three tools to validate and improve these choices:

### Tool 1: Sensitivity Analysis (Recommended First Step)

Tests whether key findings are robust across different threshold configurations.

```bash
python sensitivity_analysis.py
```

**What it does:**
- Tests 9 different threshold configurations
- Computes strategy diversity (Shannon entropy) for each
- Measures coefficient of variation (CV) as robustness metric
- Checks if "human > LLM diversity" holds across all configs

**Interpretation:**
- **CV < 20%**: Results are robust, current thresholds reasonable
- **CV 20-30%**: Moderate sensitivity, consider validation
- **CV > 30%**: High sensitivity, use data-driven thresholds or manual validation

**Output:**
- `outputs/data/sensitivity_analysis_results.csv`
- `outputs/figures/sensitivity_analysis_entropy.png`

### Tool 2: Data-Driven Threshold Analysis

Analyzes token overlap distributions in your data to recommend thresholds.

```bash
python threshold_analysis.py
```

**What it does:**
- Computes overlap ratios for all consecutive query pairs
- Shows distribution histograms with current thresholds overlaid
- Recommends percentile-based thresholds (30th, 70th, 90th)
- Samples example reformulations at each overlap level

**Output:**
- `outputs/figures/threshold_analysis_distributions.png`
- Console output with percentile recommendations

**Use case:** When you want thresholds that reflect natural clusters in the data rather than arbitrary values.

### Tool 3: Manual Validation & Threshold Tuning

Creates gold-standard labels and optimizes thresholds to match human judgment.

```bash
# Step 1: Create sample for manual labeling
python manual_validation.py --create --sample-size 100

# Step 2: Edit validation_sample.json
#         Set 'manual_label' field to: expansion, refinement, pivoting,
#         specification, minimal, or other

# Step 3: Compute agreement
python manual_validation.py --validate validation_sample.json

# Step 4: Optimize thresholds via grid search
python manual_validation.py --tune validation_sample.json
```

**What it does:**
- Samples 100 random query pairs for manual annotation
- Computes agreement between manual and automatic labels
- Shows confusion matrix and misclassification examples
- Grid search over threshold combinations to maximize agreement

**Output:**
- `validation_sample.json` (edit this file with manual labels)
- Console output with agreement rate and optimized thresholds

**Use case:** When you need highest confidence in classification accuracy and have time for manual annotation.

### Recommended Workflow

```
1. Run sensitivity_analysis.py
   ↓
2. If CV < 20%: Proceed with current thresholds (robust)
   ↓
3. If CV > 20%: Run threshold_analysis.py to see data distributions
   ↓
4. If needed: Run manual_validation.py for gold-standard tuning
   ↓
5. Update thresholds in metrics.py:classify_reformulation()
   ↓
6. Re-run query_analysis.ipynb with new thresholds
```

---

## Analysis Pipeline

### Phase A: Cross-Task Aggregate Analysis

**Goal:** Compare human vs. LLM behavior across all tasks

#### A1. Lexical Diversity Metrics
- Type-Token Ratio (TTR)
- Moving-Average TTR (MATTR)
- Vocabulary size
- Query length distributions

#### A2. Query Reformulation Strategies
- Expansion (adding context)
- Refinement (rephrasing)
- Pivoting (topic changes)
- Specification (narrowing focus)
- Minimal changes
- Backtracking (strategic returns)

#### A3. Statistical Testing
- Mann-Whitney U tests (group comparisons)
- Cohen's d (effect sizes)
- Significance testing (p < 0.05)

#### A4. Visualization
- Box plots comparing diversity metrics
- Bar charts showing reformulation patterns
- Distribution analyses

**Outputs:**
- `outputs/data/01-05_*.csv`
- `outputs/figures/01-02_*.png`

---

### Phase B: Within-Task Deep Dives

**Goal:** Understand micro-level patterns in selected tasks

#### B1. Task Selection
- High variance tasks
- Multi-hop reasoning tasks
- Ambiguous tasks
- Domain-specific tasks
- 5-7 representative tasks total

#### B2. Trajectory Analysis
- Query evolution diagrams
- Network graphs (query relationships)
- Qualitative coding of strategies
- Success pattern identification

#### B3. Error Analysis
- LLM failure modes
- Human failure modes
- Recovery strategies

**Outputs:**
- `outputs/reports/case_study_*.md`
- `outputs/figures/trajectories_*.png`

---

## Key Metrics Explained

### Lexical Diversity

| Metric | Calculation | Interpretation |
|--------|-------------|----------------|
| **TTR** | unique_words / total_words | Higher = more vocabulary diversity |
| **MATTR** | Average TTR across sliding windows | Robust to length differences |
| **Vocab Size** | Count of unique words | Breadth of exploration |
| **Query Length** | Words per query (mean) | Specificity of queries |

### Reformulation Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| **Expansion** | Add context | "Leo" → "Leo Dalton Silent Witness" |
| **Refinement** | Rephrase | "Leo die" → "how did Leo die" |
| **Pivoting** | Change topic | "Leo Dalton" → "Silent Witness S16" |
| **Specification** | Remove terms | "Leo death episode" → "Leo death" |
| **Backtracking** | Return to earlier query | Strategic revisiting |

See `METRICS_DOCUMENTATION.md` for complete definitions and implications.

---

## Dataset Information

### Source
- **Human Data:** Django database (Task, Webpage models)
- **LLM Data:** Benchmark runs (MultiTurnRun, MultiTurnSession, MultiTurnTrial models)

### Filtering
- **Dataset:** `nq_hard_questions` only
- **Exclusions:** Tutorial tasks
- **Filtering Method:** Task → TaskDatasetEntry → TaskDataset (belong_dataset='nq_hard_questions')

### Statistics

| Dataset | Questions | Sessions | Total Queries | Avg Queries/Session |
|---------|-----------|----------|---------------|---------------------|
| Human | Variable | ~2,000+ | ~6,000+ | ~2.7 |
| RAG | 58 | 58 | ~138 | ~2.4 |
| Vanilla Agent | 58 | 58 | ~103 | ~1.8 |
| Browser Agent | 58 | 58 | ~22 | ~0.4 |

*Note: Exact numbers depend on data extraction results*

---

## Dependencies

### Python Packages
```bash
pip install pandas numpy scipy matplotlib seaborn jupyter python-Levenshtein
```

### Data Access
- Django database connection required for human query extraction
- Benchmark data files required for LLM query extraction

---

## Methodology

### Approach
**Mixed Methods:** Quantitative metrics + qualitative trajectory analysis

### Comparison Strategy
- **Baseline:** Human search behavior
- **Comparisons:** Human vs. each LLM method (RAG, Vanilla Agent, Browser Agent)
- **Order:** Human first, then LLMs in order of complexity

### Statistical Rigor
- Non-parametric tests (Mann-Whitney U)
- Effect size reporting (Cohen's d)
- Significance threshold: p < 0.05
- Multiple comparison awareness

### Limitations
- LLM data: n=1 per question (no within-task variance)
- Human data: Uncontrolled conditions, variable expertise
- Dataset: Limited to nq_hard_questions
- Temporal: Human data has timestamps, LLM data doesn't

---

## Findings Summary

*To be completed after running analysis*

### Preliminary Hypotheses

**Diversity:**
- Humans show higher lexical diversity (TTR, vocab size)
- LLMs show more consistent/deterministic patterns

**Reformulation:**
- Humans use wider variety of strategies
- Pivoting and backtracking are human-distinctive
- LLMs rely heavily on expansion/refinement

**Implications:**
- LLMs need multi-modal reformulation strategies
- Topic pivoting capability essential
- Backtracking/search tree maintenance beneficial

---

## Actionable LLM Strategies

*To be refined after analysis*

### Strategy 1: Multi-Stage Search Expansion
**Human Pattern:** Broad → entities → narrow → verify
**LLM Implementation:** Explicit search stage planning

### Strategy 2: Lateral Search (Pivoting)
**Human Pattern:** Pivot to related entities when stuck
**LLM Implementation:** Knowledge graph-based alternative paths

### Strategy 3: Query Paraphrasing
**Human Pattern:** Multiple phrasings for diverse results
**LLM Implementation:** Generate paraphrase variants

### Strategy 4: Backtracking with Memory
**Human Pattern:** Return to promising earlier paths
**LLM Implementation:** Maintain search tree, enable returns

### Strategy 5: Multi-Language/Multi-Format
**Human Pattern:** Switch languages or search media types
**LLM Implementation:** Multi-modal retrieval

### Strategy 6: Incremental Verification
**Human Pattern:** Small queries to verify before building
**LLM Implementation:** Fact-checking sub-module

---

## Future Work

### Short Term
1. Semantic diversity analysis (sentence embeddings)
2. Deep dive on 5-7 selected tasks
3. Temporal analysis (human data timestamps)
4. Multi-language analysis (Chinese queries)

### Long Term
1. Success prediction models based on query features
2. Automated strategy detection in new trajectories
3. Real-time strategy recommendation for LLMs
4. A/B testing of LLM improvements

---

## References

### Related Work
See comprehensive literature review in approved plan:
- LLM query expansion (Query2Doc, GenQR, CSQE)
- Human search behavior (Information Foraging Theory)
- Exploratory search (Berrypicking, conversational search)

### Key Papers
- Information Foraging Theory (Pirolli & Card, 1999)
- Query reformulation in IR (Huang & Efthimiadis, 2009)
- LLM-based query expansion (Jagerman et al., 2023)

---

## Citation

If using this analysis framework:

```bibtex
@misc{query_reformulation_analysis_2026,
  title={Query Formulation and Reformulation Analysis: Human vs. LLM Comparison},
  author={Research Team},
  year={2026},
  dataset={nq_hard_questions},
  institution={User Trajectory Retriever Project}
}
```

---

## Contact & Support

For questions or issues:
1. Review `METRICS_DOCUMENTATION.md` for metric definitions
2. Check `outputs/README.md` for output interpretations
3. Examine code comments in `metrics.py` and notebook
4. Contact research team for methodology questions

---

## Version History

- **v1.0** (2026-01-15): Initial framework with lexical diversity and reformulation analysis
- **v1.1** (Planned): Add semantic diversity metrics
- **v2.0** (Planned): Deep dive case studies and final report

---

**Last Updated:** 2026-01-15
**Status:** Phase A Complete, Phase B Pending
**Dataset:** nq_hard_questions (tutorial excluded)
