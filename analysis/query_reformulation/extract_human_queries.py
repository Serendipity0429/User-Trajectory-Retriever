#!/usr/bin/env python
"""
Extract search queries from human trajectories stored in the database.
Standardized output format: task > entities > trials > queries
"""
import os
import sys
import json
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../Platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annotation_platform.settings')
django.setup()

from task_manager.models import Task, TaskTrial, Webpage, TaskDatasetEntry
from extract_llm_queries import extract_query_from_url


def extract_human_queries():
    """Extract queries from human trajectories, grouped by task > trajectory (user) > trial."""

    # Filter for nq_hard_questions dataset only (exclude tutorial)
    dataset_name = 'nq_hard_questions'

    try:
        from task_manager.models import TaskDataset
        dataset = TaskDataset.objects.get(name=dataset_name)
        print(f"Filtering for dataset: {dataset_name}")

        # Get dataset entries (questions) for this dataset
        dataset_entries = TaskDatasetEntry.objects.filter(belong_dataset=dataset)
        print(f"Found {dataset_entries.count()} questions in {dataset_name}")

        # Get all valid tasks with their content, filtered by dataset
        tasks = Task.valid_objects.select_related('content', 'user').prefetch_related('tasktrial_set').filter(
            content__in=dataset_entries
        )
        print(f"Found {tasks.count()} tasks for {dataset_name}\n")

    except TaskDataset.DoesNotExist:
        print(f"Warning: Dataset '{dataset_name}' not found. Using all tasks.")
        tasks = Task.valid_objects.select_related('content', 'user').prefetch_related('tasktrial_set').all()

    results = {}

    for task in tasks:
        if not task.content:
            continue

        question = task.content.question
        user_key = f"user_{task.user.id}"

        if question not in results:
            results[question] = {
                'question': question,
                'trajectories': {}
            }

        if user_key not in results[question]['trajectories']:
            results[question]['trajectories'][user_key] = {}

        # Get all trials for this task, ordered by trial number
        for trial in task.tasktrial_set.order_by('num_trial').all():
            trial_num = trial.num_trial

            # Get all webpages for this trial
            webpages = Webpage.objects.filter(
                belong_task=task,
                belong_task_trial=trial
            ).order_by('start_timestamp')

            queries = []
            for webpage in webpages:
                timestamp = webpage.start_timestamp.isoformat() if webpage.start_timestamp else None
                query_obj = extract_query_from_url(webpage.url, timestamp=timestamp)
                if query_obj:
                    queries.append(query_obj)

            # Deduplicate based on query text while preserving order
            seen = set()
            deduped_queries = []
            for q in queries:
                if q['query'] not in seen:
                    seen.add(q['query'])
                    deduped_queries.append(q)

            results[question]['trajectories'][user_key][trial_num] = deduped_queries

    return results


def main():
    output_dir = os.path.join(os.path.dirname(__file__), 'extracted_queries')
    os.makedirs(output_dir, exist_ok=True)

    print("Extracting queries from human trajectories...")
    results = extract_human_queries()

    # Compute statistics
    total_tasks = len(results)
    total_trajectories = sum(len(task_data['trajectories']) for task_data in results.values())
    total_trials = sum(
        len(trials)
        for task_data in results.values()
        for trials in task_data['trajectories'].values()
    )
    total_queries = sum(
        len(queries)
        for task_data in results.values()
        for trajectory_trials in task_data['trajectories'].values()
        for queries in trajectory_trials.values()
    )

    print(f"Extracted {total_queries} queries from {total_trials} trials")
    print(f"Across {total_trajectories} user trajectories and {total_tasks} tasks")

    # Save results
    output_path = os.path.join(output_dir, 'human_trajectories.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"Saved to {output_path}\n")


if __name__ == '__main__':
    main()
