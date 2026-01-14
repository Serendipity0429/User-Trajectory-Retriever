# Query Diversity & Reformulation Metrics Documentation

This document explains each metric used in the query analysis, including its calculation method, interpretation, and implications for understanding human vs. LLM query behavior.

---

## Lexical Diversity Metrics

### 1. Type-Token Ratio (TTR)

**Calculation:**
```
TTR = (Number of unique words) / (Total number of words)
```

**Range:** 0.0 to 1.0

**Interpretation:**
- **Higher TTR (closer to 1.0):** Greater vocabulary diversity; uses many different words
- **Lower TTR (closer to 0.0):** More repetition; uses fewer unique words

**Implications:**
- **High TTR in queries:** Indicates exploratory search with varied vocabulary, trying different phrasings and terms
- **Low TTR:** Suggests focused search with consistent terminology, or repetitive query patterns
- **Human vs. LLM:** Humans typically show higher TTR due to natural language variation and exploratory behavior

**Limitations:**
- Sensitive to text length (longer texts naturally have lower TTR)
- Does not account for semantic similarity (synonyms counted as different)

---

### 2. Moving-Average Type-Token Ratio (MATTR)

**Calculation:**
```
MATTR = Average TTR across sliding windows of fixed size (default: 10 tokens)
```

**Range:** 0.0 to 1.0

**Interpretation:**
- Similar to TTR but addresses length sensitivity
- Measures local vocabulary diversity within windows

**Implications:**
- **More robust** than TTR for comparing texts of different lengths
- Better reflects sustained vocabulary diversity across the query sequence

**Advantages over TTR:**
- Controls for text length effects
- More stable across different corpus sizes

---

### 3. Vocabulary Size

**Calculation:**
```
Vocabulary Size = Count of unique words across all queries in a session
```

**Range:** Integer ≥ 0

**Interpretation:**
- **Larger vocabulary:** More diverse word usage within a session
- **Smaller vocabulary:** Focused on specific terms

**Implications:**
- **High vocabulary size:** Indicates breadth of exploration, trying many different concepts/terms
- **Low vocabulary size:** Suggests narrow focus or lack of query diversity
- **Per-session metric:** Shows how much lexical ground each user/agent covers

**Use Cases:**
- Comparing exploratory depth between humans and LLMs
- Identifying users who pivot topics vs. those who stay focused

---

### 4. Query Length (Words & Characters)

**Calculation:**
```
Mean Words = Average number of words per query
Mean Characters = Average number of characters per query
```

**Range:** Real numbers ≥ 0

**Interpretation:**
- **Longer queries:** More specific, detailed information needs
- **Shorter queries:** More concise, potentially broader searches

**Implications:**
- **Human patterns:** Often start broad (short) then get specific (longer)
- **LLM patterns:** May generate longer, more structured queries
- **Search effectiveness:** Very short (<3 words) may be too broad; very long (>15 words) may be too specific

**Statistics Provided:**
- Mean, Std Dev, Min, Max for both word and character counts
- Reveals query formulation strategies

---

## Semantic Diversity Metrics

### 5. Intra-Session Similarity

**Calculation:**
```
Average pairwise cosine similarity between query embeddings within a session
Similarity_ij = 1 - cosine_distance(embedding_i, embedding_j)
Intra_Session_Sim = Average(all pairs Similarity_ij)
```

**Range:** 0.0 to 1.0

**Interpretation:**
- **High similarity (>0.8):** Queries are semantically close; minimal topic shift
- **Low similarity (<0.5):** Queries cover diverse topics; significant exploration

**Implications:**
- **High intra-session similarity:** Focused search strategy, refining around same concept
- **Low intra-session similarity:** Exploratory search, trying different angles/topics
- **Inverse of diversity:** Lower similarity = Higher diversity

**Use Cases:**
- Detecting topic pivoting behavior
- Measuring exploratory vs. focused search patterns

---

### 6. Inter-Session Similarity

**Calculation:**
```
Each session represented by mean of its query embeddings
Inter_Session_Sim = Average pairwise similarity between session centroids (for same question)
```

**Range:** 0.0 to 1.0

**Interpretation:**
- **High similarity:** Different users/agents use similar search strategies
- **Low similarity:** High variance in how different users approach the same question

**Implications:**
- **Low inter-session similarity (humans):** Individual differences in search strategies
- **High inter-session similarity (LLMs):** Consistent/deterministic approach
- **Indicates personalization needs:** Lower similarity suggests need for personalized search

---

## Query Reformulation Strategy Metrics

**Theoretical Foundation:**
The query reformulation categories used in this analysis are grounded in established information retrieval and human information-seeking behavior research:

- **Query Expansion/Refinement**: Inspired by comprehensive surveys of query modification techniques in IR systems [Azad & Deepak, 2019; Carpineto & Romano, 2012]
- **Berrypicking and Pivoting**: Conceptually derived from Marcia Bates' seminal berrypicking model [Bates, 1989], which characterizes human search as non-linear, evolving, and involving lateral moves through information space
- **Backtracking**: Related to browsing strategies including footnote chasing and citation searching [Bates, 1989]
- **Recent Conversational Search**: Modern work on conversational query reformulation using LLMs [Mo et al., 2023; Yang et al., 2023; Dhole et al., 2024]

**Implementation Note:** The classification algorithm in `metrics.py` uses heuristic token-overlap thresholds (0.3, 0.7, 0.9) empirically chosen for this analysis, not directly derived from a single published algorithm. The categories are conceptually aligned with the literature above but represent a practical implementation for analyzing human vs. LLM query behavior in our dataset.

These categories capture the diverse strategies humans employ when reformulating queries, from incremental refinements to exploratory pivots, reflecting the dynamic nature of real-world information seeking.

### 7. Expansion

**Detection:**
- New terms added to query
- Original terms mostly retained
- Token overlap > 30%, additions > 0, removals = 0

**Example:**
```
Query 1: "Leo Dalton"
Query 2: "Leo Dalton Silent Witness"  ← Expansion
```

**Interpretation:**
- Query becomes more specific by adding context

**Implications:**
- **Common human strategy:** Adding context when initial query too broad
- **Indicates:** Progressive specification, building on previous attempts

---

### 8. Refinement

**Detection:**
- Mix of additions and removals
- Moderate token overlap (30-70%)
- Both add and remove operations present

**Example:**
```
Query 1: "Leo Dalton die"
Query 2: "how did Leo Dalton die in Silent Witness"  ← Refinement
```

**Interpretation:**
- Significant query restructuring while maintaining topic

**Implications:**
- **Sophisticated strategy:** Reframing the question based on feedback
- **Indicates:** Adaptation based on search results

---

### 9. Pivoting

**Detection:**
- Low token overlap (<70%)
- Major topic/concept change
- Few shared terms between consecutive queries

**Example:**
```
Query 1: "Leo Dalton"
Query 2: "Silent Witness season 16 plot"  ← Pivoting
```

**Interpretation:**
- Lateral move to related but different topic

**Implications:**
- **Exploratory behavior:** Trying alternative entry points
- **Indicates:** Original path unproductive, seeking related information
- **Human characteristic:** Flexible navigation through information space

---

### 10. Specification

**Detection:**
- Terms removed (making query more specific)
- Token overlap > 30%, additions = 0, removals > 0

**Example:**
```
Query 1: "Silent Witness Leo Dalton death episode season"
Query 2: "Leo Dalton death episode"  ← Specification
```

**Interpretation:**
- Removing unnecessary terms to focus query

**Implications:**
- **Refinement strategy:** Streamlining based on what didn't work
- **Indicates:** Learning from verbose queries

---

### 11. Minimal Change

**Detection:**
- Very high overlap (>90%)
- Only 1-2 tokens changed

**Example:**
```
Query 1: "Leo Dalton death"
Query 2: "Leo Dalton died"  ← Minimal
```

**Interpretation:**
- Small adjustments (typo correction, tense change, minor rephrasing)

**Implications:**
- **Fine-tuning:** Small tweaks rather than major reformulation
- **May indicate:** Good initial query, just needs minor adjustment

---

### 12. Backtracking

**Detection:**
- Current query similar to earlier query (not immediate predecessor)
- Jaccard similarity ≥ 0.8 with query from 2+ steps ago

**Example:**
```
Query 1: "Leo Dalton Silent Witness"
Query 2: "Silent Witness season 16"
Query 3: "Silent Witness cast"
Query 4: "Leo Dalton Silent Witness"  ← Backtracking to Query 1
```

**Interpretation:**
- Returning to previously abandoned search path

**Implications:**
- **Strategic behavior:** Recognizing that alternative paths didn't work
- **Indicates:** Non-linear search, memory of previous attempts
- **Distinctive human trait:** Conscious backtracking suggests higher-level strategy

---

## Aggregate Statistics

### 13. Number of Queries per Session

**Calculation:**
```
Count of distinct queries issued within a single session
```

**Interpretation:**
- **More queries:** More exploratory/thorough search
- **Fewer queries:** Quick convergence or premature stopping

**Implications:**
- **Human variability:** Wide range (1-20+ queries) depending on task difficulty and user persistence
- **LLM consistency:** Typically fixed number based on max turns
- **Task complexity indicator:** Harder questions → more queries needed

---

### 14. Number of Turns per Session

**Calculation:**
```
Count of interaction turns (query-result-decision cycles)
```

**Interpretation:**
- **More turns:** Iterative refinement process
- **Fewer turns:** Quick success or giving up

**Implications:**
- **Multi-turn reasoning:** Ability to chain information across attempts
- **Persistence measure:** Willingness to continue despite initial failures

---

## Statistical Comparison Metrics

### 15. Mann-Whitney U Test

**Purpose:** Non-parametric test for comparing two independent groups

**Null Hypothesis:** Two groups have identical distributions

**Output:**
- **Statistic:** U value
- **p-value:** Probability of observing data if null hypothesis true
- **Significant if p < 0.05**

**Use Case:**
- Comparing human vs. LLM metrics when distributions may not be normal

---

### 16. Cohen's d (Effect Size)

**Calculation:**
```
Cohen's d = (Mean_1 - Mean_2) / Pooled_Std_Dev
```

**Interpretation:**
- **|d| < 0.2:** Small effect
- **|d| = 0.2-0.5:** Small to medium effect
- **|d| = 0.5-0.8:** Medium to large effect
- **|d| > 0.8:** Large effect

**Implications:**
- **Practical significance:** Even if statistically significant (p<0.05), small effect size may not be meaningful
- **Magnitude of difference:** How much groups actually differ in practical terms

---

## Summary: What Each Metric Tells Us

| Metric | Measures | High Value Means | Low Value Means | Human vs. LLM Expectation |
|--------|----------|------------------|-----------------|---------------------------|
| TTR | Vocabulary diversity | Varied word usage | Repetitive terminology | Humans higher (exploratory) |
| MATTR | Length-adjusted diversity | Sustained variety | Consistent vocabulary | Humans higher |
| Vocab Size | Lexical breadth | Wide exploration | Narrow focus | Humans higher (more topics) |
| Query Length | Specificity | Detailed queries | Concise queries | Variable by strategy |
| Intra-Session Sim | Topic coherence | Focused search | Exploratory search | LLMs higher (focused) |
| Inter-Session Sim | Strategy consistency | Similar approaches | Diverse strategies | LLMs higher (deterministic) |
| Expansion | Specification | Adding context | - | Humans use more |
| Refinement | Adaptation | Query restructuring | - | Humans use more |
| Pivoting | Flexibility | Topic switching | - | Humans use more |
| Backtracking | Strategic memory | Revisiting paths | - | Distinctive human trait |

---

## Interpretation Guidelines

### High Diversity (TTR, Vocab Size) + Low Similarity
**Interpretation:** Exploratory search behavior with wide topic coverage

**Typical of:** Humans tackling unfamiliar topics, struggling with difficult questions

**Strategy:** Trying multiple angles until something works

---

### Low Diversity + High Similarity
**Interpretation:** Focused, systematic search with consistent terminology

**Typical of:** LLMs with narrow search strategy, experts with known terminology

**Strategy:** Refining around central concept

---

### High Reformulation Variety (Expansion + Refinement + Pivoting)
**Interpretation:** Flexible search strategy adapting to feedback

**Typical of:** Humans with strong information literacy

**Strategy:** Multi-modal approach, switching tactics based on results

---

### Low Reformulation Variety
**Interpretation:** Limited strategic repertoire

**Typical of:** Current LLMs, novice searchers

**Strategy:** Repetitive patterns without adaptation

---

## Implications for LLM Design

1. **Increase Query Diversity:** Generate multiple paraphrases, not just refinements
2. **Enable Topic Pivoting:** Allow lateral moves when direct path fails
3. **Implement Backtracking:** Maintain search tree, return to promising branches
4. **Vary Reformulation Strategies:** Mix expansion, refinement, and pivoting
5. **Adapt to Feedback:** Change strategy based on result quality, not just iterate

---

## References

### Query Reformulation and Expansion

**Azad, H. K., & Deepak, A. (2019).** Query expansion techniques for information retrieval: A survey. *Information Processing & Management*, 56(5), 1698-1735.
- Comprehensive survey covering query expansion techniques, data sources, weighting methodologies from 1960-2017
- [Link to paper](https://www.sciencedirect.com/science/article/abs/pii/S0306457318305466)

**Carpineto, C., & Romano, G. (2012).** A survey of automatic query expansion in information retrieval. *ACM Computing Surveys*, 44(1), 1-50.
- Foundational survey on automatic query expansion methods
- [Link to paper](https://arxiv.org/abs/1708.00247)

**Boldi, P., Bonchi, F., Castillo, C., Donato, D., Gionis, A., & Vigna, S. (2008).** Analyzing and evaluating query reformulation strategies in web search logs. *Proceedings of the 17th ACM Conference on Information and Knowledge Management (CIKM)*, 677-686.
- Analysis of query reformulation strategies from real web search logs
- [Link to paper](https://dl.acm.org/doi/10.1145/1645953.1645966)

### Human Information-Seeking Behavior

**Bates, M. J. (1989).** The design of browsing and berrypicking techniques for the online search interface. *Online Review*, 13(5), 407-424.
- Seminal work introducing the berrypicking model: search as non-linear, evolving process with lateral moves
- Describes query reformulation as "bit by bit" information gathering with changing search directions
- [Link to paper](https://pages.gseis.ucla.edu/faculty/bates/berrypicking.html)

**Bates, M. J. (2002).** Toward an integrated model of information seeking and searching. *The New Review of Information Behaviour Research*, 3, 1-15.
- Extended berrypicking model with broader information seeking context

### Query Modification Taxonomy

**Huang, J., & Efthimiadis, E. N. (2009).** Analyzing and evaluating query reformulation strategies in web search logs. *Proceedings of the 18th International Conference on World Wide Web (WWW)*, 77-86.
- Empirical analysis of reformulation strategies: word reorder, add/remove words, stemming
- Provides operational definitions for reformulation classification

**Jansen, B. J., Booth, D. L., & Spink, A. (2009).** Patterns of query reformulation during web searching. *Journal of the American Society for Information Science and Technology*, 60(7), 1358-1371.
- Large-scale analysis of query reformulation patterns in web search
- Identifies common reformulation types and their frequencies

### Information Foraging and Exploratory Search

**Pirolli, P., & Card, S. (1999).** Information foraging. *Psychological Review*, 106(4), 643-675.
- Information Foraging Theory: adaptive information gathering based on "information scent"
- Theoretical foundation for understanding pivoting and backtracking behaviors

**White, R. W., & Roth, R. A. (2009).** *Exploratory Search: Beyond the Query-Response Paradigm*. Morgan & Claypool Publishers.
- Comprehensive treatment of exploratory search involving browsing, learning, topic pivoting

### Recent Work on Conversational Search and LLM-Based Reformulation (2022-2024)

**Dhole, K. D., Chandradevan, R., & Agichtein, E. (2024).** Generative query reformulation using ensemble prompting, document fusion, and relevance feedback. *arXiv preprint arXiv:2405.17658*.
- Ensemble-based prompting for generating multiple query reformulations using LLMs
- Achieves 18% improvement on nDCG@10 through query ensemble and relevance feedback
- [Link to paper](https://arxiv.org/pdf/2405.17658v1)

**Mo, F., Mao, K., Zhu, Y., Wu, Y., Huang, K., & Nie, J. Y. (2023).** ConvGQR: Generative query reformulation for conversational search. *Proceedings of ACL*.
- Uses generative PLMs for conversational query reformulation
- Combines query rewriting with potential answer generation
- [Link to paper](https://arxiv.org/pdf/2305.15645v3)

**Yang, D., Zhang, Y., & Fang, H. (2023).** ZeQR: Zero-shot query reformulation for conversational search. *arXiv preprint arXiv:2307.09384*.
- Zero-shot approach explicitly resolving coreference and omission ambiguities
- Uses machine reading comprehension models for query reformulation
- [Link to paper](https://arxiv.org/pdf/2307.09384v3)

**Lai, Y., Wu, J., Zhang, C., Sun, H., & Zhou, D. (2024).** AdaCQR: Enhancing query reformulation for conversational search via sparse and dense retrieval alignment. *arXiv preprint arXiv:2407.01965*.
- Aligns reformulation models with both term-based and semantic-based retrieval systems
- Improves generalizability across diverse retrieval environments
- [Link to paper](https://arxiv.org/pdf/2407.01965v3)

**Jang, Y., Lee, K. I., Bae, H., Lee, H., & Jung, K. (2023).** IterCQR: Iterative conversational query reformulation with retrieval guidance. *arXiv preprint arXiv:2311.09820*.
- Iteratively trains reformulation models using IR signals as rewards
- Does not rely on human-annotated query rewrites
- [Link to paper](https://arxiv.org/pdf/2311.09820v2)

**Chen, H., Dou, Z., Zhu, Y., Cao, Z., Cheng, X., & Wen, J. R. (2022).** Enhancing user behavior sequence modeling by generative tasks for session search. *Proceedings of SIGIR*.
- Models historical user behaviors in search sessions using encoder-decoder architecture
- Predicts future queries and clicked documents to help understand search intent
- [Link to paper](https://arxiv.org/pdf/2208.10846v1)

**Note:** While these recent papers focus on *automatic* query reformulation by LLMs, they provide valuable context on modern approaches to understanding and generating reformulated queries in conversational settings. Our analysis focuses on *classifying* reformulation strategies in human vs. LLM search behavior, which remains a less-studied area in recent literature.

---

**Document Version:** 1.2
**Last Updated:** 2026-01-15
**Related Files:** `metrics.py`, `query_analysis.ipynb`

**Version History:**
- v1.2: Added recent citations (2022-2024) and implementation transparency note
- v1.1: Added comprehensive references and theoretical foundation
- v1.0: Initial documentation
