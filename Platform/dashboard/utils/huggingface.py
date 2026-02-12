"""
HuggingFace dataset format utilities.
"""

import json
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any
from pathlib import Path


def generate_dataset_info(stats: Dict[str, Any], anonymized: bool = True) -> Dict[str, Any]:
    """
    Generate HuggingFace dataset_info.json content.

    Args:
        stats: Export statistics
        anonymized: Whether data is anonymized

    Returns:
        dataset_info dictionary
    """
    return {
        "description": "TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving. "
                      "Contains 5,370 trials across 58 open-domain questions with per-trial labels, "
                      "structured failure reflections, evidence markers, and replayable behavioral traces.",
        "citation": "@article{zhang2026tec,\n"
                   "  title={TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving},\n"
                   "  author={Zhang, Xinkai and Zhan, Jingtao and Liu, Yiqun and Ai, Qingyao},\n"
                   "  year={2026}\n"
                   "}",
        "homepage": "https://github.com/Serendipity0429/TEC",
        "license": "mit",
        "features": {
            "task_id": {"dtype": "int32", "_type": "Value"},
            "participant_id": {"dtype": "string", "_type": "Value"},
            "question": {"dtype": "string", "_type": "Value"},
            "ground_truth": {"dtype": "string", "_type": "Value"},
            "status": {"dtype": "string", "_type": "Value"},
            "start_timestamp": {"dtype": "string", "_type": "Value"},
            "end_timestamp": {"dtype": "string", "_type": "Value"},
            "num_trial": {"dtype": "int32", "_type": "Value"},
            "participant": {
                "participant_id": {"dtype": "string", "_type": "Value"},
                "username": {"dtype": "string", "_type": "Value"},
                "email": {"dtype": "string", "_type": "Value"},
                "first_name": {"dtype": "string", "_type": "Value"},
                "last_name": {"dtype": "string", "_type": "Value"},
                "date_joined": {"dtype": "string", "_type": "Value"},
                "last_login": {"dtype": "string", "_type": "Value"},
                "login_num": {"dtype": "int32", "_type": "Value"},
                "consent_agreed": {"dtype": "bool", "_type": "Value"},
                "profile": {
                    "name": {"dtype": "string", "_type": "Value"},
                    "phone": {"dtype": "string", "_type": "Value"},
                    "age": {"dtype": "string", "_type": "Value"},
                    "gender": {"dtype": "string", "_type": "Value"},
                    "occupation": {"dtype": "string", "_type": "Value"},
                    "education": {"dtype": "string", "_type": "Value"},
                    "field_of_expertise": {"dtype": "string", "_type": "Value"},
                    "icon": {"dtype": "string", "_type": "Value"},
                    "llm_frequency": {"dtype": "string", "_type": "Value"},
                    "llm_history": {"dtype": "string", "_type": "Value"},
                    "english_proficiency": {"dtype": "string", "_type": "Value"},
                    "web_search_proficiency": {"dtype": "string", "_type": "Value"},
                    "web_agent_familiarity": {"dtype": "string", "_type": "Value"},
                    "web_agent_frequency": {"dtype": "string", "_type": "Value"},
                },
            },
            "dataset": {
                "dataset_name": {"dtype": "string", "_type": "Value"},
                "entry_id": {"dtype": "int32", "_type": "Value"},
            },
            "pre_task_annotation": {
                "familiarity": {"dtype": "int32", "_type": "Value"},
                "difficulty": {"dtype": "int32", "_type": "Value"},
                "effort": {"dtype": "int32", "_type": "Value"},
                "first_search_query": {"dtype": "string", "_type": "Value"},
                "initial_guess": {"dtype": "string", "_type": "Value"},
                "initial_guess_unknown": {"dtype": "bool", "_type": "Value"},
                "initial_guess_reason": {"dtype": "string", "_type": "Value"},
                "expected_source": {"_type": "Sequence", "feature": {"dtype": "string", "_type": "Value"}},
                "expected_source_other": {"dtype": "string", "_type": "Value"},
                "submission_timestamp": {"dtype": "string", "_type": "Value"},
                "duration": {"dtype": "int32", "_type": "Value"},
            },
            "post_task_annotation": {
                "difficulty_actual": {"dtype": "int32", "_type": "Value"},
                "aha_moment_type": {"dtype": "string", "_type": "Value"},
                "aha_moment_other": {"dtype": "string", "_type": "Value"},
                "unhelpful_paths": {"_type": "Sequence", "feature": {"dtype": "string", "_type": "Value"}},
                "unhelpful_paths_other": {"dtype": "string", "_type": "Value"},
                "strategy_shift": {"_type": "Sequence", "feature": {"dtype": "string", "_type": "Value"}},
                "strategy_shift_other": {"dtype": "string", "_type": "Value"},
                "submission_timestamp": {"dtype": "string", "_type": "Value"},
                "duration": {"dtype": "int32", "_type": "Value"},
            },
            "cancel_annotation": {
                "category": {"_type": "Sequence", "feature": {"dtype": "string", "_type": "Value"}},
                "reason": {"dtype": "string", "_type": "Value"},
                "missing_resources": {"dtype": "string", "_type": "Value"},
                "missing_resources_other": {"dtype": "string", "_type": "Value"},
                "submission_timestamp": {"dtype": "string", "_type": "Value"},
                "duration": {"dtype": "int32", "_type": "Value"},
            },
            "trials": {
                "_type": "Sequence",
                "feature": {
                    "trial_num": {"dtype": "int32", "_type": "Value"},
                    "start_timestamp": {"dtype": "string", "_type": "Value"},
                    "end_timestamp": {"dtype": "string", "_type": "Value"},
                    "answer": {"dtype": "string", "_type": "Value"},
                    "is_correct": {"dtype": "bool", "_type": "Value"},
                    "confidence": {"dtype": "int32", "_type": "Value"},
                    "answer_formulation_method": {"_type": "Sequence", "feature": {"dtype": "string", "_type": "Value"}},
                    "answer_formulation_method_other": {"dtype": "string", "_type": "Value"},
                    "reflection_annotation": {
                        "failure_category": {"dtype": "string", "_type": "Value"},
                        "failure_category_other": {"dtype": "string", "_type": "Value"},
                        "future_plan_actions": {"dtype": "string", "_type": "Value"},
                        "future_plan_other": {"dtype": "string", "_type": "Value"},
                        "estimated_time": {"dtype": "int32", "_type": "Value"},
                        "adjusted_difficulty": {"dtype": "int32", "_type": "Value"},
                        "additional_reflection": {"dtype": "string", "_type": "Value"},
                        "submission_timestamp": {"dtype": "string", "_type": "Value"},
                        "duration": {"dtype": "int32", "_type": "Value"},
                    },
                    "justifications": {
                        "_type": "Sequence",
                        "feature": {
                            "id": {"dtype": "int32", "_type": "Value"},
                            "url": {"dtype": "string", "_type": "Value"},
                            "page_title": {"dtype": "string", "_type": "Value"},
                            "text": {"dtype": "string", "_type": "Value"},
                            "dom_position": {"dtype": "string", "_type": "Value"},
                            "status": {"dtype": "string", "_type": "Value"},
                            "evidence_type": {"dtype": "string", "_type": "Value"},
                            "element_details": {
                                "tagName": {"dtype": "string", "_type": "Value"},
                                "attributes": {"dtype": "string", "_type": "Value"},
                            },
                            "relevance": {"dtype": "int32", "_type": "Value"},
                            "credibility": {"dtype": "int32", "_type": "Value"},
                            "timestamp": {"dtype": "string", "_type": "Value"},
                            "evidence_image": {"dtype": "string", "_type": "Value"},
                        },
                    },
                    "webpages": {
                        "_type": "Sequence",
                        "feature": {
                            "id": {"dtype": "int32", "_type": "Value"},
                            "title": {"dtype": "string", "_type": "Value"},
                            "url": {"dtype": "string", "_type": "Value"},
                            "referrer": {"dtype": "string", "_type": "Value"},
                            "start_timestamp": {"dtype": "string", "_type": "Value"},
                            "end_timestamp": {"dtype": "string", "_type": "Value"},
                            "dwell_time": {"dtype": "int32", "_type": "Value"},
                            "width": {"dtype": "int32", "_type": "Value"},
                            "height": {"dtype": "int32", "_type": "Value"},
                            "page_switch_record": {"dtype": "string", "_type": "Value"},
                            "mouse_moves": {"dtype": "string", "_type": "Value"},
                            "event_list": {"dtype": "string", "_type": "Value"},
                            "rrweb_record": {"dtype": "string", "_type": "Value"},
                            "is_redirected": {"dtype": "bool", "_type": "Value"},
                            "during_annotation": {"dtype": "bool", "_type": "Value"},
                            "annotation_name": {"dtype": "string", "_type": "Value"},
                        },
                    },
                },
            },
        },
        "splits": {
            "train": {
                "name": "train",
                "num_bytes": 0,
                "num_examples": stats.get("task_count", 0),
            }
        },
        "download_size": 0,
        "dataset_size": 0,
        "version": {
            "version_str": "1.0.0",
            "major": 1,
            "minor": 0,
            "patch": 0
        },
        "configs": [
            {
                "config_name": "default",
                "data_files": [
                    {"split": "train", "path": "data.jsonl"}
                ]
            }
        ],
        "task_categories": ["other"],
        "task_ids": [],
        "pretty_name": "TEC: Human Trial-and-error Trajectories",
        "tags": ["web-trajectory", "information-seeking", "user-behavior", "trial-and-error", "problem-solving"],
        "size_categories": [_get_size_category(stats.get("task_count", 0))],
        "annotations": {
            "anonymized": anonymized,
            "participant_count": stats.get("participant_count", 0),
            "task_count": stats.get("task_count", 0),
            "trial_count": stats.get("trial_count", 0),
            "webpage_count": stats.get("webpage_count", 0),
            "exported_at": stats.get("exported_at", datetime.now(dt_timezone.utc).isoformat()),
        }
    }


def _get_size_category(count: int) -> str:
    """Get HuggingFace size category based on example count."""
    if count < 1000:
        return "n<1K"
    elif count < 10000:
        return "1K<n<10K"
    elif count < 100000:
        return "10K<n<100K"
    elif count < 1000000:
        return "100K<n<1M"
    else:
        return "n>1M"


def generate_readme(stats: Dict[str, Any], anonymized: bool = True) -> str:
    """
    Generate HuggingFace README.md (dataset card) content.

    Args:
        stats: Export statistics
        anonymized: Whether data is anonymized

    Returns:
        README markdown content
    """
    anonymization_note = ""
    if anonymized:
        anonymization_note = """
## Anonymization

This dataset has been anonymized:
- User identifiers (username, email, name, phone) are replaced with `[ANONYMIZED]`
- Participant IDs are replaced with sequential identifiers (e.g., `participant_000001`)
- Age is binned into ranges (e.g., `25-34`)
- Profile images and field of expertise are anonymized
"""

    return f"""---
license: mit
task_categories:
  - other
tags:
  - web-trajectory
  - information-seeking
  - user-behavior
  - trial-and-error
  - problem-solving
size_categories:
  - {_get_size_category(stats.get("task_count", 0))}
---

# TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving

This is the dataset for the paper:

> **TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving**
> Xinkai Zhang, Jingtao Zhan, Yiqun Liu, and Qingyao Ai.

## Dataset Description

TEC captures the human trial-and-error process in web search with both behavioral traces and structured diagnostic reflections. Each record represents a multi-trial task trajectory where participants iteratively search, attempt answers, reflect on failures, and retry with corrective plans.

Each task record includes:

- **Task information**: Open-domain factoid question, ground truth answer, completion status
- **Participant profile**: Demographics and expertise levels (anonymized)
- **Pre-task annotation**: Familiarity, difficulty prediction, initial search query, initial guess
- **Trial outcomes**: Per-trial answers with correctness labels, confidence, and formulation method
- **Evidence markers**: Selected text, DOM position, source URL with relevance/credibility ratings
- **Reflection annotations** (on failure): Prioritized failure diagnosis, corrective plan, adjusted difficulty
- **Post-task annotation** (on success): Actual difficulty, "aha" moments, unhelpful paths, strategy shifts
- **Cancellation annotation** (on giving up): Cancellation reason, missing resources
- **Behavioral traces**: Full rrweb DOM recordings, interaction events, and mouse movements per page

## Dataset Statistics

| Metric | Count |
|--------|-------|
| Participants | {stats.get("participant_count", 0)} |
| Tasks | {stats.get("task_count", 0)} |
| Trials | {stats.get("trial_count", 0)} |
| Webpages | {stats.get("webpage_count", 0)} |
{anonymization_note}
## Data Format

The dataset is provided in JSONL format (JSON Lines), where each line is a complete task record.

### Schema

```json
{{
  "task_id": 1,
  "participant_id": "participant_000001",
  "question": "What is ...",
  "ground_truth": ["..."],
  "status": "completed",
  "start_timestamp": "2024-01-15T10:30:00Z",
  "end_timestamp": "2024-01-15T10:45:00Z",
  "num_trial": 2,
  "participant": {{
    "username": "[ANONYMIZED]",
    "profile": {{
      "age": "25-34",
      "gender": "M",
      "occupation": "researcher",
      "education": "phd"
    }}
  }},
  "pre_task_annotation": {{
    "familiarity": 2,
    "difficulty": 1,
    "first_search_query": "...",
    "initial_guess": "..."
  }},
  "post_task_annotation": {{
    "difficulty_actual": 3,
    "aha_moment_type": "search_result"
  }},
  "cancel_annotation": null,
  "trials": [
    {{
      "trial_num": 1,
      "answer": "...",
      "is_correct": false,
      "confidence": 3,
      "reflection_annotation": {{
        "failure_category": "Ineffective Search",
        "corrective_plan": "Improve Search",
        "adjusted_difficulty": 4,
        "notes": "..."
      }},
      "justifications": [
        {{
          "url": "https://...",
          "text": "selected text",
          "dom_position": 150,
          "relevance": 0.8,
          "credibility": 0.9
        }}
      ],
      "webpages": [
        {{
          "title": "Page Title",
          "url": "https://...",
          "referrer": "https://...",
          "dwell_time": 45,
          "rrweb_record": ["..."],
          "event_list": ["..."],
          "mouse_moves": ["..."]
        }}
      ]
    }}
  ]
}}
```

### Key Fields

| Record | Key Fields |
|--------|-----------|
| Webpage (per page) | URL, title, rrweb DOM recording, interaction events, mouse/scroll trajectory, dwell time, referrer |
| Trial outcome (per trial) | Answer, correctness, confidence, formulation method |
| Evidence | Selected text, DOM position, source URL, relevance/credibility ratings |
| Reflection (on failure) | Failure diagnosis (prioritized), corrective plan (prioritized), adjusted difficulty |
| Pre-task (per task) | Familiarity, difficulty estimate, initial query plan, initial guess |
| Post-task | Actual difficulty, "aha" moment type, unhelpful paths, strategy shifts |
| Cancellation | Cancellation reason, missing resources |

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("Serendipity2004/TEC", split="train")

# Access a task trajectory — all fields are native dicts/lists
task = dataset[0]
print(task["question"])
print(f"Number of trials: {{task['num_trial']}}")
print(f"Participant age: {{task['participant']['profile']['age']}}")

# Iterate over trials (native dicts, no json.loads needed)
for trial in task["trials"]:
    print(f"Trial {{trial['trial_num']}}: correct={{trial['is_correct']}}")
    if trial["reflection_annotation"]["failure_category"]:
        print(f"  Failure: {{trial['reflection_annotation']['failure_category']}}")

# Large behavioral data fields are JSON strings — parse when needed
import json
for trial in task["trials"]:
    for wp in trial["webpages"]:
        events = json.loads(wp["event_list"]) if wp["event_list"] else []
        print(f"  Page: {{wp['url']}} ({{len(events)}} events)")
```

## Citation

```bibtex
@article{{zhang2026tec,
  title={{TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving}},
  author={{Zhang, Xinkai and Zhan, Jingtao and Liu, Yiqun and Ai, Qingyao}},
  year={{2026}}
}}
```

## License

MIT License

## Exported

- **Date**: {stats.get("exported_at", "N/A")}
- **Anonymized**: {"Yes" if anonymized else "No"}
"""


def save_huggingface_files(output_dir: str, stats: Dict[str, Any], anonymized: bool = True):
    """
    Save HuggingFace dataset files (dataset_info.json and README.md).

    Args:
        output_dir: Output directory path
        stats: Export statistics
        anonymized: Whether data is anonymized
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save dataset_info.json
    dataset_info = generate_dataset_info(stats, anonymized)
    with open(output_path / "dataset_info.json", 'w', encoding='utf-8') as f:
        json.dump(dataset_info, f, indent=2, ensure_ascii=False)

    # Save README.md
    readme = generate_readme(stats, anonymized)
    with open(output_path / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme)
