"""
Task manager data export utilities.
"""

import json
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, List, Optional, Iterator, Callable
from pathlib import Path

from django.db.models import Prefetch

from .anonymizer import UserAnonymizer, ANONYMIZED_PLACEHOLDER


class ExportRedisKeys:
    TTL = 3600  # 1 hour auto-expire

    @staticmethod
    def progress(export_id: str) -> str:
        return f"export:progress:{export_id}"


class TaskManagerExporter:
    """
    Exports task_manager data to HuggingFace-compatible JSONL format.

    Usage:
        exporter = TaskManagerExporter(anonymize=True)
        exporter.export_to_file(output_dir, user_ids=[1, 2, 3])
    """

    def __init__(self, anonymize: bool = True):
        """
        Initialize exporter.

        Args:
            anonymize: Whether to anonymize user data
        """
        self.anonymize = anonymize
        self.anonymizer = UserAnonymizer()  # Always create for export_user_full

    def _get_users_queryset(self, user_ids: Optional[List[int]] = None, limit: Optional[int] = None):
        """Get users queryset with optional filtering."""
        from user_system.models import User
        from core.filters import Q_VALID_USER

        qs = User.objects.filter(Q_VALID_USER).select_related('profile')

        if user_ids:
            qs = qs.filter(id__in=user_ids)

        qs = qs.order_by('id')

        if limit:
            qs = qs[:limit]

        return qs

    def _get_tasks_for_user(self, user, exclude_dataset_ids: Optional[List[int]] = None):
        """Get all tasks for a user with related data."""
        from task_manager.models import Task, TaskTrial, Justification, Webpage

        tasks = Task.objects.filter(user=user, active=False)  # Only finished tasks

        if exclude_dataset_ids:
            tasks = tasks.exclude(content__belong_dataset_id__in=exclude_dataset_ids)

        tasks = tasks.prefetch_related(
            'pretaskannotation',
            'posttaskannotation',
            'cancelannotation',
            Prefetch(
                'tasktrial_set',
                queryset=TaskTrial.objects.prefetch_related(
                    'reflectionannotation',
                    Prefetch(
                        'justifications',
                        queryset=Justification.objects.order_by('timestamp')
                    ),
                    Prefetch(
                        'webpage_set',
                        queryset=Webpage.objects.order_by('start_timestamp')
                    )
                ).order_by('num_trial')
            ),
        ).select_related('content', 'content__belong_dataset').order_by('start_timestamp')

        return tasks

    def _serialize_pre_task_annotation(self, annotation) -> Optional[Dict[str, Any]]:
        """Serialize PreTaskAnnotation."""
        if not annotation:
            return None
        return {
            "familiarity": annotation.familiarity,
            "difficulty": annotation.difficulty,
            "effort": annotation.effort,
            "first_search_query": annotation.first_search_query,
            "initial_guess": annotation.initial_guess,
            "initial_guess_unknown": annotation.initial_guess_unknown,
            "initial_guess_reason": annotation.initial_guess_reason,
            "expected_source": annotation.expected_source,
            "expected_source_other": annotation.expected_source_other,
            "submission_timestamp": annotation.submission_timestamp.isoformat() if annotation.submission_timestamp else None,
            "duration": annotation.duration,
        }

    def _serialize_post_task_annotation(self, annotation) -> Optional[Dict[str, Any]]:
        """Serialize PostTaskAnnotation."""
        if not annotation:
            return None
        return {
            "difficulty_actual": annotation.difficulty_actual,
            "aha_moment_type": annotation.aha_moment_type,
            "aha_moment_other": annotation.aha_moment_other,
            "unhelpful_paths": annotation.unhelpful_paths,
            "unhelpful_paths_other": annotation.unhelpful_paths_other,
            "strategy_shift": annotation.strategy_shift,
            "strategy_shift_other": annotation.strategy_shift_other,
            "submission_timestamp": annotation.submission_timestamp.isoformat() if annotation.submission_timestamp else None,
            "duration": annotation.duration,
        }

    def _serialize_cancel_annotation(self, annotation) -> Optional[Dict[str, Any]]:
        """Serialize CancelAnnotation."""
        if not annotation:
            return None
        return {
            "category": annotation.category,
            "reason": annotation.reason,
            "missing_resources": annotation.missing_resources,
            "missing_resources_other": annotation.missing_resources_other,
            "submission_timestamp": annotation.submission_timestamp.isoformat() if annotation.submission_timestamp else None,
            "duration": annotation.duration,
        }

    def _serialize_reflection_annotation(self, annotation) -> Optional[Dict[str, Any]]:
        """Serialize ReflectionAnnotation."""
        if not annotation:
            return None
        return {
            "failure_category": annotation.failure_category,
            "failure_category_other": annotation.failure_category_other,
            "future_plan_actions": annotation.future_plan_actions,
            "future_plan_other": annotation.future_plan_other,
            "estimated_time": annotation.estimated_time,
            "adjusted_difficulty": annotation.adjusted_difficulty,
            "additional_reflection": annotation.additional_reflection,
            "submission_timestamp": annotation.submission_timestamp.isoformat() if annotation.submission_timestamp else None,
            "duration": annotation.duration,
        }

    def _serialize_justification(self, justification) -> Dict[str, Any]:
        """Serialize Justification."""
        return {
            "id": justification.id,
            "url": justification.url,
            "page_title": justification.page_title,
            "text": justification.text,
            "dom_position": justification.dom_position,
            "status": justification.status,
            "evidence_type": justification.evidence_type,
            "element_details": justification.element_details,
            "relevance": justification.relevance,
            "credibility": justification.credibility,
            "timestamp": justification.timestamp.isoformat() if justification.timestamp else None,
            "evidence_image": str(justification.evidence_image) if justification.evidence_image else None,
        }

    def _serialize_webpage(self, webpage) -> Dict[str, Any]:
        """Serialize Webpage."""
        return {
            "id": webpage.id,
            "title": webpage.title,
            "url": webpage.url,
            "referrer": webpage.referrer,
            "start_timestamp": webpage.start_timestamp.isoformat() if webpage.start_timestamp else None,
            "end_timestamp": webpage.end_timestamp.isoformat() if webpage.end_timestamp else None,
            "dwell_time": webpage.dwell_time,
            "width": webpage.width,
            "height": webpage.height,
            "page_switch_record": webpage.page_switch_record,
            "mouse_moves": webpage.mouse_moves,
            "event_list": webpage.event_list,
            "rrweb_record": webpage.rrweb_record,
            "is_redirected": webpage.is_redirected,
            "during_annotation": webpage.during_annotation,
            "annotation_name": webpage.annotation_name,
        }

    def _serialize_trial(self, trial) -> Dict[str, Any]:
        """Serialize TaskTrial with related data."""
        # Get reflection annotation
        reflection = None
        try:
            reflection = self._serialize_reflection_annotation(trial.reflectionannotation)
        except Exception:
            pass

        # Get justifications
        justifications = [
            self._serialize_justification(j) for j in trial.justifications.all()
        ]

        # Get webpages
        webpages = [
            self._serialize_webpage(w) for w in trial.webpage_set.all()
        ]

        return {
            "trial_num": trial.num_trial,
            "start_timestamp": trial.start_timestamp.isoformat() if trial.start_timestamp else None,
            "end_timestamp": trial.end_timestamp.isoformat() if trial.end_timestamp else None,
            "answer": trial.answer,
            "is_correct": trial.is_correct,
            "confidence": trial.confidence,
            "answer_formulation_method": trial.answer_formulation_method,
            "answer_formulation_method_other": trial.answer_formulation_method_other,
            "reflection_annotation": reflection,
            "justifications": justifications,
            "webpages": webpages,
        }

    def _serialize_task(self, task, participant_id: Any) -> Dict[str, Any]:
        """Serialize a single task with all related data."""
        # Get annotations
        pre_task = None
        post_task = None
        cancel = None

        try:
            pre_task = self._serialize_pre_task_annotation(task.pretaskannotation)
        except Exception:
            pass

        try:
            post_task = self._serialize_post_task_annotation(task.posttaskannotation)
        except Exception:
            pass

        try:
            cancel = self._serialize_cancel_annotation(task.cancelannotation)
        except Exception:
            pass

        # Get trials
        trials = [self._serialize_trial(t) for t in task.tasktrial_set.all()]

        # Determine status
        if task.cancelled:
            status = "cancelled"
        elif not task.active:
            status = "completed"
        else:
            status = "active"

        # Get dataset info
        dataset_info = None
        if task.content:
            dataset_info = {
                "dataset_name": task.content.belong_dataset.name if task.content.belong_dataset else None,
                "entry_id": task.content.id,
            }

        return {
            "task_id": task.id,
            "participant_id": participant_id,
            "question": task.content.question if task.content else None,
            "ground_truth": task.content.answer if task.content else None,
            "status": status,
            "start_timestamp": task.start_timestamp.isoformat() if task.start_timestamp else None,
            "end_timestamp": task.end_timestamp.isoformat() if task.end_timestamp else None,
            "num_trial": task.num_trial,
            "dataset": dataset_info,
            "pre_task_annotation": pre_task,
            "post_task_annotation": post_task,
            "cancel_annotation": cancel,
            "trials": trials,
        }

    def export_user_tasks(self, user, exclude_dataset_ids: Optional[List[int]] = None) -> Iterator[Dict[str, Any]]:
        """
        Export all tasks for a user.

        Args:
            user: User model instance
            exclude_dataset_ids: Optional list of dataset IDs to exclude

        Yields:
            Task dictionaries
        """
        # Get participant info
        if self.anonymize:
            participant = self.anonymizer.anonymize_user(user)
            participant_id = participant["participant_id"]
        else:
            participant = self.anonymizer.export_user_full(user)
            participant_id = user.id

        # Get tasks
        tasks = self._get_tasks_for_user(user, exclude_dataset_ids)

        for task in tasks:
            task_data = self._serialize_task(task, participant_id)
            task_data["participant"] = participant
            yield task_data

    def export_all(
        self,
        user_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        exclude_dataset_ids: Optional[List[int]] = None,
        on_user_start: Optional[Callable[[int, int], None]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Export all task data.

        Args:
            user_ids: Optional list of user IDs to export
            limit: Optional limit on number of users (for test mode)
            exclude_dataset_ids: Optional list of dataset IDs to exclude
            on_user_start: Optional callback(current_index, total_users) called before each user

        Yields:
            Task dictionaries
        """
        users = list(self._get_users_queryset(user_ids, limit))
        total_users = len(users)

        for idx, user in enumerate(users):
            if on_user_start:
                on_user_start(idx, total_users)
            yield from self.export_user_tasks(user, exclude_dataset_ids)

    def export_to_file(
        self,
        output_dir: str,
        user_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        exclude_dataset_ids: Optional[List[int]] = None,
        on_progress: Optional[Callable[[int, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export data to JSONL file.

        Args:
            output_dir: Output directory path
            user_ids: Optional list of user IDs to export
            limit: Optional limit on number of users (for test mode)
            exclude_dataset_ids: Optional list of dataset IDs to exclude
            on_progress: Optional callback(current_user, total_users, tasks_exported)

        Returns:
            Export statistics
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        data_file = output_path / "data.jsonl"

        stats = {
            "task_count": 0,
            "participant_count": 0,
            "trial_count": 0,
            "webpage_count": 0,
            "exported_at": datetime.now(dt_timezone.utc).isoformat(),
            "anonymized": self.anonymize,
        }

        seen_participants = set()

        # Progress tracking state shared with on_user_start closure
        progress_state = {"current_user": 0, "total_users": 0}

        def _on_user_start(idx, total):
            progress_state["current_user"] = idx
            progress_state["total_users"] = total
            if on_progress:
                on_progress(idx, total, stats["task_count"])

        with open(data_file, 'w', encoding='utf-8') as f:
            for task_data in self.export_all(
                user_ids, limit, exclude_dataset_ids,
                on_user_start=_on_user_start,
            ):
                # Write JSONL
                f.write(json.dumps(task_data, ensure_ascii=False, default=str) + '\n')

                # Update stats
                stats["task_count"] += 1
                stats["trial_count"] += len(task_data.get("trials", []))

                for trial in task_data.get("trials", []):
                    stats["webpage_count"] += len(trial.get("webpages", []))

                pid = task_data.get("participant_id")
                if pid not in seen_participants:
                    seen_participants.add(pid)
                    stats["participant_count"] += 1

        return stats

    def get_export_preview(
        self,
        user_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
        exclude_dataset_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Get preview of what would be exported (for dry-run/UI).

        Args:
            user_ids: Optional list of user IDs
            limit: Optional limit on number of users
            exclude_dataset_ids: Optional list of dataset IDs to exclude

        Returns:
            Preview statistics
        """
        from task_manager.models import Task, TaskTrial, Webpage

        users = self._get_users_queryset(user_ids, limit)
        user_ids_list = list(users.values_list('id', flat=True))

        # Build task filter
        task_filter = {'user_id__in': user_ids_list, 'active': False}
        task_qs = Task.objects.filter(**task_filter)
        if exclude_dataset_ids:
            task_qs = task_qs.exclude(content__belong_dataset_id__in=exclude_dataset_ids)

        task_count = task_qs.count()
        task_ids = list(task_qs.values_list('id', flat=True))

        trial_count = TaskTrial.objects.filter(belong_task_id__in=task_ids).count()
        webpage_count = Webpage.objects.filter(belong_task_id__in=task_ids).count()

        return {
            "participant_count": len(user_ids_list),
            "task_count": task_count,
            "trial_count": trial_count,
            "webpage_count": webpage_count,
            "anonymized": self.anonymize,
        }
