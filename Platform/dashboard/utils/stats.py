"""
Dashboard utility functions for calculating statistics and metrics.
These are reusable across dashboard and benchmark apps.
"""
from collections import Counter, defaultdict
from urllib.parse import urlparse

from django.db.models import Count, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.conf import settings
from django.db import connection
from datetime import timedelta

import numpy as np

from task_manager.models import Task, TaskTrial, PreTaskAnnotation, PostTaskAnnotation, Justification, Webpage
from task_manager.mappings import ANSWER_FORMULATION_MAP, FAMILIARITY_MAP, DIFFICULTY_MAP, EFFORT_MAP, CONFIDENCE_MAP
from user_system.models import User, Profile
from core.filters import (
    Q_VALID_USER_REL, Q_VALID_TASK_USER, Q_VALID_TRIAL_USER,
    Q_TUTORIAL_TASK, Q_TUTORIAL_TASK_REL, Q_TUTORIAL_TRIAL_REL, Q_TUTORIAL_WEBPAGE
)


# =============================================================================
# Task Success Metrics
# =============================================================================

def calculate_task_success_metrics(task_queryset=None):
    """
    Calculate success metrics from completed task records.

    Args:
        task_queryset: Optional queryset of tasks to analyze.
                       If None, uses all valid finished tasks (both completed and cancelled),
                       excluding tutorial datasets.

    Returns:
        dict with success rates, counts, and timing metrics.
        Note: Cancelled tasks count as failures in success rate calculation.
    """
    if task_queryset is None:
        # Include ALL finished tasks - cancelled ones count as failures
        # Exclude tutorial datasets
        task_queryset = Task.valid_objects.filter(active=False).exclude(Q_TUTORIAL_TASK)

    tasks = task_queryset.prefetch_related('tasktrial_set')

    total_finished = 0
    total_cancelled = 0
    successful_count = 0
    first_try_success_count = 0
    self_corrected_count = 0
    total_trials = 0
    total_time_seconds = 0
    tasks_with_time = 0

    for task in tasks:
        total_finished += 1
        trials = list(task.tasktrial_set.all().order_by('start_timestamp'))

        if trials:
            total_trials += len(trials)

        # Cancelled tasks count as failures
        if task.cancelled:
            total_cancelled += 1
            continue

        # Check for success in non-cancelled tasks
        has_success = False
        first_trial_correct = False

        for idx, trial in enumerate(trials):
            if trial.is_correct:
                has_success = True
                if idx == 0:
                    first_trial_correct = True
                break

        if has_success:
            successful_count += 1
            if first_trial_correct:
                first_try_success_count += 1
            else:
                self_corrected_count += 1

        if task.end_timestamp and task.start_timestamp:
            duration = (task.end_timestamp - task.start_timestamp).total_seconds()
            total_time_seconds += duration
            tasks_with_time += 1

    # Success rate: successful / all finished (cancelled = failures)
    success_rate = (successful_count / total_finished * 100) if total_finished > 0 else 0
    first_try_success_rate = (first_try_success_count / successful_count * 100) if successful_count > 0 else 0
    self_correction_rate = (self_corrected_count / successful_count * 100) if successful_count > 0 else 0
    avg_trials = total_trials / total_finished if total_finished > 0 else 0
    avg_time_seconds = total_time_seconds / tasks_with_time if tasks_with_time > 0 else None

    total_completed = total_finished - total_cancelled  # Non-cancelled finished tasks

    return {
        'total_finished': total_finished,
        'total_completed': total_completed,
        'total_cancelled': total_cancelled,
        'successful_count': successful_count,
        'first_try_success_count': first_try_success_count,
        'self_corrected_count': self_corrected_count,
        'success_rate': round(success_rate, 1),
        'first_try_success_rate': round(first_try_success_rate, 1),
        'self_correction_rate': round(self_correction_rate, 1),
        'avg_trials': round(avg_trials, 2),
        'avg_time_seconds': round(avg_time_seconds, 1) if avg_time_seconds else None,
    }


# =============================================================================
# User Statistics
# =============================================================================

def get_user_signup_stats(days=30):
    """Get user signup counts by date for the last N days."""
    cutoff = timezone.now() - timedelta(days=days)
    signups = (
        User.participants.filter(date_joined__gte=cutoff)
        .annotate(date=TruncDate("date_joined"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    return {
        "labels": [x["date"] for x in signups],
        "data": [x["count"] for x in signups]
    }


def get_profile_distribution(field, choices):
    """Get distribution of a profile field."""
    counts = Profile.objects.filter(Q_VALID_USER_REL).values(field).annotate(count=Count(field))
    return {
        "labels": [dict(choices).get(c[field], "N/A") for c in counts if c[field]],
        "data": [c["count"] for c in counts if c[field]],
    }


def get_all_profile_distributions():
    """Get all profile field distributions."""
    return {
        "gender_distribution": get_profile_distribution("gender", Profile.GENDER_CHOICES),
        "occupation_distribution": get_profile_distribution("occupation", Profile.OCCUPATION_CHOICES),
        "education_distribution": get_profile_distribution("education", Profile.EDUCATION_CHOICES),
        "llm_frequency_distribution": get_profile_distribution("llm_frequency", Profile.LLM_FREQUENCY_CHOICES),
        "english_proficiency_distribution": get_profile_distribution("english_proficiency", Profile.ENGLISH_PROFICIENCY_CHOICES),
        "web_search_proficiency_distribution": get_profile_distribution("web_search_proficiency", Profile.WEB_SEARCH_PROFICIENCY_CHOICES),
    }


# =============================================================================
# Task Time Statistics
# =============================================================================

def get_task_creation_stats(days=30):
    """Get task creation counts by date for the last N days, excluding tutorials."""
    cutoff = timezone.now() - timedelta(days=days)
    creations = (
        Task.valid_objects.filter(start_timestamp__gte=cutoff)
        .exclude(Q_TUTORIAL_TASK)
        .annotate(date=TruncDate("start_timestamp"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    return {
        "labels": [x["date"] for x in creations],
        "data": [x["count"] for x in creations]
    }


def get_time_distributions():
    """Get task and trial time distributions, excluding tutorials."""
    completed_tasks = Task.valid_objects.filter(
        active=False, end_timestamp__isnull=False
    ).exclude(Q_TUTORIAL_TASK).prefetch_related('tasktrial_set')

    task_times = [
        (task.end_timestamp - task.start_timestamp).total_seconds()
        for task in completed_tasks
    ]

    all_trials = TaskTrial.objects.filter(Q_VALID_TASK_USER, end_timestamp__isnull=False).exclude(Q_TUTORIAL_TASK_REL)
    trial_times = [
        (trial.end_timestamp - trial.start_timestamp).total_seconds()
        for trial in all_trials
    ]

    # Task time histogram
    if task_times:
        hist, bins = np.histogram(task_times, bins=10)
        task_histogram = {"hist": hist.tolist(), "bins": bins.tolist()}
    else:
        task_histogram = {"hist": [], "bins": []}

    # Trial time by trial number (for box plots)
    trial_times_by_num = defaultdict(list)
    all_durations = [(t.end_timestamp - t.start_timestamp).total_seconds() for t in all_trials]
    cutoff = np.percentile(all_durations, 99) if all_durations else float('inf')

    for trial in all_trials:
        duration = (trial.end_timestamp - trial.start_timestamp).total_seconds()
        if duration <= cutoff:
            trial_times_by_num[trial.num_trial].append(duration)

    sorted_nums = sorted(trial_times_by_num.keys())
    trial_detail = {
        "labels": [f"Trial {n}" for n in sorted_nums],
        "data": [trial_times_by_num[n] for n in sorted_nums]
    }

    # Trial count distribution
    tasks_with_counts = completed_tasks.annotate(num_trials=Count('tasktrial'))
    trial_counts = [task.num_trials for task in tasks_with_counts]
    if trial_counts:
        freq = Counter(trial_counts)
        trial_count_dist = {
            "labels": [f"{c} trials" for c in sorted(freq.keys())],
            "data": [freq[c] for c in sorted(freq.keys())]
        }
    else:
        trial_count_dist = {"labels": [], "data": []}

    return {
        "task_time_distribution": task_times,
        "trial_time_distribution": trial_times,
        "task_time_histogram": task_histogram,
        "trial_time_distribution_detail": trial_detail,
        "trial_count_distribution": trial_count_dist,
    }


# =============================================================================
# Annotation Statistics
# =============================================================================

def get_annotation_distribution(model, field, mapping, q_obj, exclude_q=None):
    """Get distribution of an annotation field with label mapping, excluding tutorials."""
    qs = model.objects.filter(q_obj)
    if exclude_q is not None:
        qs = qs.exclude(exclude_q)
    counts = qs.values(field).annotate(count=Count(field))
    return {
        "labels": [mapping.get(str(c[field]), str(c[field])) for c in counts if c[field] is not None],
        "data": [c["count"] for c in counts if c[field] is not None],
    }


def get_all_annotation_distributions():
    """Get all annotation field distributions, excluding tutorials."""
    familiarity_map = {str(k): v for k, v in FAMILIARITY_MAP["mapping"].items()}
    difficulty_map = {str(k): v for k, v in DIFFICULTY_MAP["mapping"].items()}
    effort_map = {str(k): v for k, v in EFFORT_MAP["mapping"].items()}
    confidence_map = {str(k): v for k, v in CONFIDENCE_MAP["mapping"].items()}

    return {
        "familiarity_distribution": get_annotation_distribution(
            PreTaskAnnotation, "familiarity", familiarity_map, Q_VALID_TASK_USER, Q_TUTORIAL_TASK_REL
        ),
        "pre_task_difficulty_distribution": get_annotation_distribution(
            PreTaskAnnotation, "difficulty", difficulty_map, Q_VALID_TASK_USER, Q_TUTORIAL_TASK_REL
        ),
        "post_task_difficulty_distribution": get_annotation_distribution(
            PostTaskAnnotation, "difficulty_actual", difficulty_map, Q_VALID_TASK_USER, Q_TUTORIAL_TASK_REL
        ),
        "effort_distribution": get_annotation_distribution(
            PreTaskAnnotation, "effort", effort_map, Q_VALID_TASK_USER, Q_TUTORIAL_TASK_REL
        ),
        "confidence_distribution": get_annotation_distribution(
            TaskTrial, "confidence", confidence_map, Q_VALID_TASK_USER, Q_TUTORIAL_TASK_REL
        ),
    }


def get_trial_statistics():
    """Get trial-related statistics (correctness, aha moments, answer methods), excluding tutorials."""
    # Aha Moment
    aha_counts = (
        PostTaskAnnotation.objects.filter(Q_VALID_TASK_USER)
        .exclude(Q_TUTORIAL_TASK_REL)
        .values('aha_moment_type')
        .annotate(count=Count('aha_moment_type'))
        .exclude(aha_moment_type__isnull=True)
    )
    aha_dist = {
        "labels": [item['aha_moment_type'] for item in aha_counts],
        "data": [item['count'] for item in aha_counts]
    }

    # Trial Correctness
    correctness_counts = TaskTrial.objects.filter(Q_VALID_TASK_USER).exclude(Q_TUTORIAL_TASK_REL).values('is_correct').annotate(count=Count('is_correct'))
    def correctness_label(val):
        if val is True: return "Correct"
        if val is False: return "Incorrect"
        return "Not Evaluated"
    correctness_dist = {
        "labels": [correctness_label(item['is_correct']) for item in correctness_counts],
        "data": [item['count'] for item in correctness_counts]
    }

    # Answer Formulation Method
    afm_mapping = ANSWER_FORMULATION_MAP["mapping"]
    afm_data = TaskTrial.objects.filter(Q_VALID_TASK_USER).exclude(Q_TUTORIAL_TASK_REL).values_list('answer_formulation_method', flat=True)
    afm_flat = []
    for item in afm_data:
        if isinstance(item, list):
            afm_flat.extend(item)
        elif item and item != 'undefined':
            afm_flat.append(item)

    afm_counts = Counter(afm_flat)
    def clean_afm(key):
        val = afm_mapping.get(key, key)
        text = val.replace("<strong>", "").replace("</strong>", "")
        return text.split(':')[0].strip()

    afm_dist = {
        "labels": [clean_afm(k) for k in afm_counts.keys()],
        "data": list(afm_counts.values())
    }

    # Evidence Type
    evidence_counts = Justification.objects.filter(Q_VALID_TRIAL_USER).exclude(Q_TUTORIAL_TRIAL_REL).values('evidence_type').annotate(count=Count('evidence_type'))
    evidence_dist = {
        "labels": [item['evidence_type'] for item in evidence_counts],
        "data": [item['count'] for item in evidence_counts]
    }

    return {
        "aha_moment_distribution": aha_dist,
        "trial_correctness_distribution": correctness_dist,
        "answer_formulation_method_distribution": afm_dist,
        "evidence_type_distribution": evidence_dist,
    }


def get_json_field_distribution(model, field, q_obj):
    """Get distribution from a JSON list field."""
    import json
    all_values = model.objects.filter(q_obj).exclude(**{f"{field}__isnull": True}).values_list(field, flat=True)
    counts = Counter()
    for sublist in all_values:
        if isinstance(sublist, str):
            try:
                sublist = json.loads(sublist)
            except json.JSONDecodeError:
                continue
        if sublist:
            if isinstance(sublist, list):
                counts.update(sublist)
            else:
                counts.update([sublist])
    return {"labels": list(counts.keys()), "data": list(counts.values())}


# =============================================================================
# Navigation & Behavior Statistics
# =============================================================================

def get_navigation_stats():
    """Get navigation and behavior statistics, excluding tutorials."""
    # Average Trajectory Length
    trajectory_stats = (
        Webpage.objects.filter(Q_VALID_USER_REL)
        .exclude(Q_TUTORIAL_WEBPAGE)
        .values('belong_task')
        .annotate(page_count=Count('id'))
        .aggregate(avg_length=Avg('page_count'))
    )
    avg_trajectory = round(trajectory_stats['avg_length'] or 0, 1)

    # Annotation Burden
    avg_pre = PreTaskAnnotation.objects.filter(Q_VALID_TASK_USER).exclude(Q_TUTORIAL_TASK_REL).aggregate(avg=Avg('duration'))
    avg_post = PostTaskAnnotation.objects.filter(Q_VALID_TASK_USER).exclude(Q_TUTORIAL_TASK_REL).aggregate(avg=Avg('duration'))

    # Dwell Time
    dwell_times = Webpage.objects.filter(Q_VALID_USER_REL).exclude(Q_TUTORIAL_WEBPAGE).exclude(dwell_time__isnull=True).values_list('dwell_time', flat=True)
    cleaned_dwell = []
    for dt in dwell_times:
        try:
            val = int(dt)
            if val >= 0:
                cleaned_dwell.append(val / 1000.0)
        except (ValueError, TypeError):
            continue

    return {
        "avg_trajectory_length": avg_trajectory,
        "avg_pre_task_duration": round(avg_pre['avg'] or 0, 1),
        "avg_post_task_duration": round(avg_post['avg'] or 0, 1),
        "dwell_time_distribution": cleaned_dwell,
    }


def get_top_domains(limit=15):
    """Get top visited domains, excluding tutorials."""
    if getattr(settings, 'DATABASE_TYPE', 'sqlite') == 'postgres':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    substring(w.url from '.*://([^/]*)') as domain,
                    COUNT(*) as count
                FROM task_manager_webpage w
                INNER JOIN user_system_user u ON w.user_id = u.id
                INNER JOIN task_manager_task t ON w.belong_task_id = t.id
                INNER JOIN task_manager_taskdatasetentry e ON t.content_id = e.id
                INNER JOIN task_manager_taskdataset d ON e.belong_dataset_id = d.id
                WHERE u.is_superuser = false
                  AND u.is_staff = false
                  AND LOWER(d.name) != 'tutorial'
                GROUP BY domain
                ORDER BY count DESC
                LIMIT %s;
            """, [limit * 2])  # Get more to handle www. dedup
            rows = cursor.fetchall()

        final_counts = Counter()
        for domain, count in rows:
            if domain:
                d = domain.lower()
                if d.startswith('www.'):
                    d = d[4:]
                final_counts[d] += count
        top = final_counts.most_common(limit)
    else:
        # SQLite fallback
        urls = Webpage.objects.filter(Q_VALID_USER_REL).exclude(Q_TUTORIAL_WEBPAGE).values_list('url', flat=True).iterator()
        domains = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domain = parsed.netloc.lower()
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    domains.append(domain)
            except Exception:
                continue
        top = Counter(domains).most_common(limit)

    return {
        "labels": [item[0] for item in top],
        "data": [item[1] for item in top]
    }
