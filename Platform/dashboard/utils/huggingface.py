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
        "description": "Web trajectory dataset for information-seeking behavior research. "
                      "Contains user search trajectories, task annotations, and behavioral data.",
        "citation": "",
        "homepage": "",
        "license": "",
        "features": {
            "task_id": {"dtype": "int32", "_type": "Value"},
            "participant_id": {"dtype": "string", "_type": "Value"},
            "question": {"dtype": "string", "_type": "Value"},
            "ground_truth": {"_type": "Value", "dtype": "string"},
            "status": {"dtype": "string", "_type": "Value"},
            "start_timestamp": {"dtype": "string", "_type": "Value"},
            "end_timestamp": {"dtype": "string", "_type": "Value"},
            "num_trial": {"dtype": "int32", "_type": "Value"},
            "participant": {
                "_type": "Value",
                "dtype": "string",
                "description": "JSON-encoded participant information"
            },
            "dataset": {
                "_type": "Value",
                "dtype": "string",
                "description": "JSON-encoded dataset information"
            },
            "pre_task_annotation": {
                "_type": "Value",
                "dtype": "string",
                "description": "JSON-encoded pre-task annotation"
            },
            "post_task_annotation": {
                "_type": "Value",
                "dtype": "string",
                "description": "JSON-encoded post-task annotation"
            },
            "cancel_annotation": {
                "_type": "Value",
                "dtype": "string",
                "description": "JSON-encoded cancel annotation"
            },
            "trials": {
                "_type": "Sequence",
                "feature": {
                    "_type": "Value",
                    "dtype": "string",
                    "description": "JSON-encoded trial data including webpages and justifications"
                }
            }
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
        "pretty_name": "Web Trajectory Dataset",
        "tags": ["web-trajectory", "information-seeking", "user-behavior"],
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
license: ""
task_categories:
  - other
tags:
  - web-trajectory
  - information-seeking
  - user-behavior
size_categories:
  - {_get_size_category(stats.get("task_count", 0))}
---

# Web Trajectory Dataset

A dataset of web search trajectories for information-seeking behavior research.

## Dataset Description

This dataset contains user web search trajectories captured during information-seeking tasks.
Each record represents a task completed by a participant, including:

- **Task information**: Question, ground truth answer, status
- **Participant profile**: Demographics, expertise levels (anonymized if applicable)
- **Pre-task annotation**: Initial familiarity, difficulty prediction, search strategy
- **Post-task annotation**: Actual difficulty, aha moments, strategy shifts
- **Trials**: Multiple attempts with answers, confidence levels, and justifications
- **Web trajectories**: Page visits with rrweb recordings, mouse movements, and events

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
  "question": "What is the capital of France?",
  "ground_truth": ["Paris"],
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
    "first_search_query": "capital of France"
  }},
  "post_task_annotation": {{
    "difficulty_actual": 1,
    "aha_moment_type": null
  }},
  "trials": [
    {{
      "trial_num": 1,
      "answer": "Paris",
      "is_correct": true,
      "confidence": 4,
      "justifications": [...],
      "webpages": [...]
    }}
  ]
}}
```

### Webpage Data

Each webpage record includes:
- `url`, `title`, `referrer`
- `dwell_time`: Time spent on page (seconds)
- `rrweb_record`: Full DOM recording for replay
- `event_list`: User interaction events
- `mouse_moves`: Mouse movement data

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("path/to/dataset", split="train")

# Access a single task
task = dataset[0]
print(task["question"])
print(task["trials"][0]["answer"])
```

## License

[Add license information]

## Citation

[Add citation information]

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
