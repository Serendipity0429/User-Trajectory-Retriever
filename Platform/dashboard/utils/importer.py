"""
Task manager data import utilities.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .anonymizer import ANONYMIZED_PLACEHOLDER


class ImportValidationError(Exception):
    """Custom exception for import validation errors."""
    pass


class ImportRedisKeys:
    TTL = 3600  # 1 hour auto-expire

    @staticmethod
    def progress(import_id: str) -> str:
        return f"import:progress:{import_id}"


class TaskManagerImporter:
    """
    Imports task_manager data from HuggingFace-compatible JSONL format.

    Usage:
        importer = TaskManagerImporter()

        # Dry run
        stats = importer.validate_and_preview(input_file)

        # Real import
        stats = importer.import_from_file(input_file)
    """

    MODE_FULL = "full"
    MODE_INCREMENTAL = "incremental"

    def __init__(self):
        self._user_map: Dict[str, Any] = {}  # participant_id -> User instance
        self._dataset_map: Dict[str, Any] = {}  # dataset_name -> TaskDataset instance
        self._entry_map: Dict[int, Any] = {}  # old_entry_id -> TaskDatasetEntry instance
        self._mode: str = self.MODE_FULL

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not value:
            return None
        return parse_datetime(value)

    def _get_or_create_user(self, participant_data: Dict[str, Any], participant_id: str):
        """Get or create a user from participant data.

        In full mode: reuses existing users by username match.
        In incremental mode: reuses existing users by username match (idempotent).
        """
        from user_system.models import User, Profile

        if participant_id in self._user_map:
            return self._user_map[participant_id]

        # Determine username
        username = participant_data.get("username", participant_id)
        if username == ANONYMIZED_PLACEHOLDER:
            username = participant_id  # Use participant_000001 as username

        # Check if user exists
        user = User.objects.filter(username=username).first()

        if not user:
            # Create new user
            email = participant_data.get("email", "")
            if email == ANONYMIZED_PLACEHOLDER:
                email = f"{username}@anonymized.local"

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=participant_data.get("first_name", ANONYMIZED_PLACEHOLDER),
                last_name=participant_data.get("last_name", ANONYMIZED_PLACEHOLDER),
            )
            user.login_num = participant_data.get("login_num", 0)
            user.consent_agreed = participant_data.get("consent_agreed", False)
            user.save()

            # Update profile (already created by post_save signal)
            profile_data = participant_data.get("profile", {})
            profile = Profile.objects.get(user=user)
            profile.name = profile_data.get("name", ANONYMIZED_PLACEHOLDER)
            profile.phone = profile_data.get("phone", ANONYMIZED_PLACEHOLDER)
            profile.age = 0 if profile_data.get("age") in [ANONYMIZED_PLACEHOLDER, None] else (
                profile_data.get("age") if isinstance(profile_data.get("age"), int) else 0
            )
            profile.gender = profile_data.get("gender", "")
            profile.occupation = profile_data.get("occupation", "")
            profile.education = profile_data.get("education", "")
            profile.field_of_expertise = profile_data.get("field_of_expertise", ANONYMIZED_PLACEHOLDER)
            profile.llm_frequency = profile_data.get("llm_frequency", "")
            profile.llm_history = profile_data.get("llm_history", "")
            profile.english_proficiency = profile_data.get("english_proficiency", "")
            profile.web_search_proficiency = profile_data.get("web_search_proficiency", "")
            profile.web_agent_familiarity = profile_data.get("web_agent_familiarity", "")
            profile.web_agent_frequency = profile_data.get("web_agent_frequency", "")
            profile.save()

        self._user_map[participant_id] = user
        return user

    def _get_or_create_dataset_entry(self, dataset_info: Dict[str, Any], question: str, ground_truth: Any):
        """Get or create dataset and entry."""
        from task_manager.models import TaskDataset, TaskDatasetEntry

        if not dataset_info:
            return None

        dataset_name = dataset_info.get("dataset_name")
        old_entry_id = dataset_info.get("entry_id")

        if old_entry_id and old_entry_id in self._entry_map:
            return self._entry_map[old_entry_id]

        # Get or create dataset
        if dataset_name:
            if dataset_name not in self._dataset_map:
                dataset, _ = TaskDataset.objects.get_or_create(
                    name=dataset_name,
                    defaults={"path": "imported"}
                )
                self._dataset_map[dataset_name] = dataset
            dataset = self._dataset_map[dataset_name]
        else:
            dataset, _ = TaskDataset.objects.get_or_create(
                name="Imported",
                defaults={"path": "imported"}
            )

        # Create entry
        entry = TaskDatasetEntry.objects.create(
            belong_dataset=dataset,
            question=question or "",
            answer=ground_truth or [],
        )

        if old_entry_id:
            self._entry_map[old_entry_id] = entry

        return entry

    def _create_task(self, task_data: Dict[str, Any], user) -> Any:
        """Create a task with all related data."""
        from task_manager.models import (
            Task, TaskTrial, PreTaskAnnotation, PostTaskAnnotation,
            CancelAnnotation, ReflectionAnnotation, Justification, Webpage
        )

        # Get or create dataset entry
        entry = self._get_or_create_dataset_entry(
            task_data.get("dataset"),
            task_data.get("question"),
            task_data.get("ground_truth")
        )

        # Create task
        status = task_data.get("status", "completed")
        task = Task.objects.create(
            user=user,
            content=entry,
            cancelled=(status == "cancelled"),
            active=(status == "active"),
            num_trial=task_data.get("num_trial", 0),
        )

        # Update timestamps (bypass auto_now_add)
        if task_data.get("start_timestamp"):
            Task.objects.filter(pk=task.pk).update(
                start_timestamp=self._parse_datetime(task_data["start_timestamp"])
            )
        if task_data.get("end_timestamp"):
            task.end_timestamp = self._parse_datetime(task_data["end_timestamp"])
            task.save(update_fields=["end_timestamp"])

        # Create annotations
        pre_task = task_data.get("pre_task_annotation")
        if pre_task:
            obj = PreTaskAnnotation.objects.create(
                belong_task=task,
                familiarity=pre_task.get("familiarity"),
                difficulty=pre_task.get("difficulty"),
                effort=pre_task.get("effort"),
                first_search_query=pre_task.get("first_search_query"),
                initial_guess=pre_task.get("initial_guess"),
                initial_guess_unknown=pre_task.get("initial_guess_unknown", False),
                initial_guess_reason=pre_task.get("initial_guess_reason"),
                expected_source=pre_task.get("expected_source"),
                expected_source_other=pre_task.get("expected_source_other"),
                duration=pre_task.get("duration"),
            )
            if pre_task.get("submission_timestamp"):
                PreTaskAnnotation.objects.filter(pk=obj.pk).update(
                    submission_timestamp=self._parse_datetime(pre_task["submission_timestamp"])
                )

        post_task = task_data.get("post_task_annotation")
        if post_task:
            obj = PostTaskAnnotation.objects.create(
                belong_task=task,
                difficulty_actual=post_task.get("difficulty_actual"),
                aha_moment_type=post_task.get("aha_moment_type"),
                aha_moment_other=post_task.get("aha_moment_other"),
                unhelpful_paths=post_task.get("unhelpful_paths"),
                unhelpful_paths_other=post_task.get("unhelpful_paths_other"),
                strategy_shift=post_task.get("strategy_shift"),
                strategy_shift_other=post_task.get("strategy_shift_other"),
                duration=post_task.get("duration"),
            )
            if post_task.get("submission_timestamp"):
                PostTaskAnnotation.objects.filter(pk=obj.pk).update(
                    submission_timestamp=self._parse_datetime(post_task["submission_timestamp"])
                )

        cancel = task_data.get("cancel_annotation")
        if cancel:
            obj = CancelAnnotation.objects.create(
                belong_task=task,
                category=cancel.get("category"),
                reason=cancel.get("reason"),
                missing_resources=cancel.get("missing_resources"),
                missing_resources_other=cancel.get("missing_resources_other"),
                duration=cancel.get("duration"),
            )
            if cancel.get("submission_timestamp"):
                CancelAnnotation.objects.filter(pk=obj.pk).update(
                    submission_timestamp=self._parse_datetime(cancel["submission_timestamp"])
                )

        # Create trials
        for trial_data in task_data.get("trials", []):
            trial = TaskTrial.objects.create(
                belong_task=task,
                num_trial=trial_data.get("trial_num", 1),
                answer=trial_data.get("answer", ""),
                is_correct=trial_data.get("is_correct"),
                confidence=trial_data.get("confidence", -1),
                answer_formulation_method=trial_data.get("answer_formulation_method", []),
                answer_formulation_method_other=trial_data.get("answer_formulation_method_other"),
            )

            # Update timestamps (use .filter().update() to bypass auto_now_add)
            ts_updates = {}
            if trial_data.get("start_timestamp"):
                ts_updates["start_timestamp"] = self._parse_datetime(trial_data["start_timestamp"])
            if trial_data.get("end_timestamp"):
                ts_updates["end_timestamp"] = self._parse_datetime(trial_data["end_timestamp"])
            if ts_updates:
                TaskTrial.objects.filter(pk=trial.pk).update(**ts_updates)

            # Create reflection annotation
            reflection = trial_data.get("reflection_annotation")
            if reflection:
                obj = ReflectionAnnotation.objects.create(
                    belong_task_trial=trial,
                    failure_category=reflection.get("failure_category"),
                    failure_category_other=reflection.get("failure_category_other", ""),
                    future_plan_actions=reflection.get("future_plan_actions"),
                    future_plan_other=reflection.get("future_plan_other"),
                    estimated_time=reflection.get("estimated_time", 0),
                    adjusted_difficulty=reflection.get("adjusted_difficulty"),
                    additional_reflection=reflection.get("additional_reflection"),
                    duration=reflection.get("duration"),
                )
                if reflection.get("submission_timestamp"):
                    ReflectionAnnotation.objects.filter(pk=obj.pk).update(
                        submission_timestamp=self._parse_datetime(reflection["submission_timestamp"])
                    )

            # Create justifications
            for just_data in trial_data.get("justifications", []):
                obj = Justification.objects.create(
                    belong_task_trial=trial,
                    url=just_data.get("url", ""),
                    page_title=just_data.get("page_title"),
                    text=just_data.get("text"),
                    dom_position=just_data.get("dom_position"),
                    status=just_data.get("status", "active"),
                    evidence_type=just_data.get("evidence_type", "text_selection"),
                    element_details=just_data.get("element_details"),
                    relevance=just_data.get("relevance", 0),
                    credibility=just_data.get("credibility", 0),
                )
                if just_data.get("timestamp"):
                    Justification.objects.filter(pk=obj.pk).update(
                        timestamp=self._parse_datetime(just_data["timestamp"])
                    )

            # Create webpages
            for wp_data in trial_data.get("webpages", []):
                Webpage.objects.create(
                    user=user,
                    belong_task=task,
                    belong_task_trial=trial,
                    title=wp_data.get("title"),
                    url=wp_data.get("url", ""),
                    referrer=wp_data.get("referrer"),
                    start_timestamp=self._parse_datetime(wp_data.get("start_timestamp")),
                    end_timestamp=self._parse_datetime(wp_data.get("end_timestamp")),
                    dwell_time=wp_data.get("dwell_time"),
                    width=wp_data.get("width"),
                    height=wp_data.get("height"),
                    page_switch_record=wp_data.get("page_switch_record"),
                    mouse_moves=wp_data.get("mouse_moves", []),
                    event_list=wp_data.get("event_list", []),
                    rrweb_record=wp_data.get("rrweb_record", []),
                    is_redirected=wp_data.get("is_redirected", False),
                    during_annotation=wp_data.get("during_annotation", False),
                    annotation_name=wp_data.get("annotation_name"),
                )

        return task

    def validate_jsonl(self, file_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate JSONL file format and structure.

        Args:
            file_path: Path to JSONL file

        Returns:
            Tuple of (is_valid, error_messages, preview_stats)
        """
        errors = []
        stats = {
            "task_count": 0,
            "participant_ids": set(),
            "trial_count": 0,
            "webpage_count": 0,
        }

        path = Path(file_path)
        if not path.exists():
            return False, [f"File not found: {file_path}"], stats

        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as e:
                        errors.append(f"Line {line_num}: Invalid JSON - {e}")
                        continue

                    # Validate required fields
                    if "participant_id" not in data:
                        errors.append(f"Line {line_num}: Missing participant_id")

                    if "task_id" not in data:
                        errors.append(f"Line {line_num}: Missing task_id")

                    # Collect stats
                    stats["task_count"] += 1
                    stats["participant_ids"].add(data.get("participant_id"))

                    for trial in data.get("trials", []):
                        stats["trial_count"] += 1
                        stats["webpage_count"] += len(trial.get("webpages", []))

        except Exception as e:
            errors.append(f"Error reading file: {e}")
            return False, errors, stats

        stats["participant_count"] = len(stats["participant_ids"])
        del stats["participant_ids"]

        return len(errors) == 0, errors, stats

    def get_existing_data_stats(self) -> Dict[str, Any]:
        """Get statistics of existing data in database."""
        from user_system.models import User
        from task_manager.models import Task, TaskTrial, Webpage
        from core.filters import Q_VALID_USER, Q_VALID_USER_REL

        user_count = User.objects.filter(Q_VALID_USER).count()
        admin_count = User.objects.filter(is_superuser=True).count()
        task_count = Task.objects.filter(Q_VALID_USER_REL).count()
        trial_count = TaskTrial.objects.filter(
            belong_task__user__is_superuser=False,
            belong_task__user__is_test_account=False
        ).count()
        webpage_count = Webpage.objects.filter(Q_VALID_USER_REL).count()

        return {
            "user_count": user_count,
            "admin_count": admin_count,
            "task_count": task_count,
            "trial_count": trial_count,
            "webpage_count": webpage_count,
            "has_data": task_count > 0,
        }

    def validate_and_preview(self, file_path: str, mode: str = "full") -> Dict[str, Any]:
        """
        Validate file and preview import (dry run).

        Args:
            file_path: Path to JSONL file
            mode: "full" (delete + replace) or "incremental" (add alongside)

        Returns:
            Preview information including validation results
        """
        is_valid, errors, import_stats = self.validate_jsonl(file_path)
        existing_stats = self.get_existing_data_stats()

        result = {
            "is_valid": is_valid,
            "errors": errors,
            "mode": mode,
            "import_stats": import_stats,
            "existing_stats": existing_stats,
            "would_import": {
                "participants": import_stats.get("participant_count", 0),
                "tasks": import_stats.get("task_count", 0),
                "trials": import_stats.get("trial_count", 0),
                "webpages": import_stats.get("webpage_count", 0),
            },
        }

        if mode == self.MODE_FULL:
            result["would_delete"] = {
                "users": existing_stats["user_count"],
                "tasks": existing_stats["task_count"],
                "trials": existing_stats["trial_count"],
                "webpages": existing_stats["webpage_count"],
            }
        else:
            result["would_delete"] = None

        return result

    def _clear_existing_data(self):
        """Clear all existing non-admin user data."""
        from user_system.models import User, Profile
        from task_manager.models import (
            Task, TaskTrial, PreTaskAnnotation, PostTaskAnnotation,
            CancelAnnotation, ReflectionAnnotation, Justification, Webpage,
            EventAnnotation
        )
        from core.filters import Q_VALID_USER

        # Delete in order due to foreign keys
        users_to_delete = User.objects.filter(Q_VALID_USER)
        user_ids = list(users_to_delete.values_list('id', flat=True))

        # Delete related data
        Webpage.objects.filter(user_id__in=user_ids).delete()
        Justification.objects.filter(
            belong_task_trial__belong_task__user_id__in=user_ids
        ).delete()
        ReflectionAnnotation.objects.filter(
            belong_task_trial__belong_task__user_id__in=user_ids
        ).delete()
        EventAnnotation.objects.filter(belong_task__user_id__in=user_ids).delete()
        TaskTrial.objects.filter(belong_task__user_id__in=user_ids).delete()
        CancelAnnotation.objects.filter(belong_task__user_id__in=user_ids).delete()
        PostTaskAnnotation.objects.filter(belong_task__user_id__in=user_ids).delete()
        PreTaskAnnotation.objects.filter(belong_task__user_id__in=user_ids).delete()
        Task.objects.filter(user_id__in=user_ids).delete()
        Profile.objects.filter(user_id__in=user_ids).delete()
        users_to_delete.delete()

    def _is_duplicate_task(self, user, task_data: Dict[str, Any]) -> bool:
        """Check if a task already exists for this user with the same question."""
        from task_manager.models import Task

        question = task_data.get("question", "")
        if not question:
            return False

        return Task.objects.filter(
            user=user,
            content__question=question,
        ).exists()

    @transaction.atomic
    def import_from_file(self, file_path: str, mode: str = "full",
                         on_progress: Optional[callable] = None,
                         total_tasks: Optional[int] = None,
                         skip_validation: bool = False) -> Dict[str, Any]:
        """
        Import data from JSONL file.

        Args:
            file_path: Path to JSONL file
            mode: "full" (delete + replace) or "incremental" (add alongside existing)
            on_progress: Optional callback(current_task, total_tasks, stats) for progress updates
            total_tasks: Pre-computed task count (from preview) to avoid re-reading the file
            skip_validation: Skip validation if already done in preview step

        Returns:
            Import statistics
        """
        self._mode = mode

        if not skip_validation:
            is_valid, errors, preview_stats = self.validate_jsonl(file_path)
            if not is_valid:
                raise ImportValidationError(f"Validation failed: {'; '.join(errors)}")
            if total_tasks is None:
                total_tasks = preview_stats.get("task_count", 0)

        if total_tasks is None:
            total_tasks = 0

        # Only clear data in full mode
        if mode == self.MODE_FULL:
            if on_progress:
                on_progress(0, total_tasks, {"phase": "deleting"})
            self._clear_existing_data()

        # Reset maps
        self._user_map = {}
        self._dataset_map = {}
        self._entry_map = {}

        stats = {
            "tasks_imported": 0,
            "participants_imported": 0,
            "trials_imported": 0,
            "webpages_imported": 0,
            "tasks_skipped": 0,
        }

        seen_participants = set()
        current_task = 0
        # Throttle progress updates to avoid excessive Redis writes
        last_progress_task = 0
        progress_interval = max(1, total_tasks // 200) if total_tasks else 10

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                current_task += 1
                task_data = json.loads(line)

                # Get or create user
                participant_id = str(task_data.get("participant_id"))
                participant_data = task_data.get("participant", {})
                user = self._get_or_create_user(participant_data, participant_id)

                if participant_id not in seen_participants:
                    seen_participants.add(participant_id)
                    stats["participants_imported"] += 1

                # In incremental mode, skip duplicate tasks
                if mode == self.MODE_INCREMENTAL and self._is_duplicate_task(user, task_data):
                    stats["tasks_skipped"] += 1
                else:
                    # Create task
                    self._create_task(task_data, user)
                    stats["tasks_imported"] += 1

                    for trial in task_data.get("trials", []):
                        stats["trials_imported"] += 1
                        stats["webpages_imported"] += len(trial.get("webpages", []))

                if on_progress and (current_task - last_progress_task) >= progress_interval:
                    last_progress_task = current_task
                    on_progress(current_task, total_tasks, stats)

        # Final progress update
        if on_progress:
            on_progress(current_task, total_tasks, stats)

        return stats
