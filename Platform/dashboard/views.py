#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import tempfile
import threading
import uuid
import logging

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET
from django.core.signing import Signer, BadSignature
from django.contrib.auth import login as auth_login
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import markdown

logger = logging.getLogger(__name__)

from user_system.models import User, InformedConsent
from task_manager.models import Task, ExtensionVersion, CancelAnnotation, ReflectionAnnotation
from discussion.models import Bulletin, Post, Comment

from user_system.forms import InformedConsentForm
from task_manager.forms import ExtensionVersionForm
from core.filters import Q_VALID_TASK_USER, Q_VALID_TRIAL_USER, Q_VALID_USER
from .utils import (
    calculate_task_success_metrics,
    get_user_signup_stats,
    get_all_profile_distributions,
    get_task_creation_stats,
    get_time_distributions,
    get_all_annotation_distributions,
    get_trial_statistics,
    get_json_field_distribution,
    get_navigation_stats,
    get_top_domains,
)

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def view_current_consent(request):
    latest_consent = InformedConsent.get_latest()
    total_users_count = User.participants.count()

    if latest_consent and latest_consent.pk:
        signed_users_count = User.participants.filter(
            agreed_consent_version=latest_consent
        ).count()
        return JsonResponse(
            {
                "version": latest_consent.version,
                "content": markdown.markdown(latest_consent.content),
                "signed_users_count": signed_users_count,
                "total_users_count": total_users_count,
                "created_at": latest_consent.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    elif latest_consent:  # Default unsaved consent
        return JsonResponse(
            {
                "version": latest_consent.version,
                "content": markdown.markdown(latest_consent.content),
                "signed_users_count": 0,
                "total_users_count": total_users_count,
                "created_at": "Not saved yet",
            }
        )
    return JsonResponse({"error": "No consent form found."}, status=404)


@login_required
@user_passes_test(is_superuser)
def manage_informed_consent(request):
    latest_consent = InformedConsent.get_latest()
    if request.method == "POST":
        form = InformedConsentForm(request.POST)
        if form.is_valid():
            # If latest_consent is saved (pk exists), increment version.
            # If it's default (unsaved), start at 1.
            new_version = (latest_consent.version + 1) if latest_consent.pk else 1
            new_consent = form.save(commit=False)
            new_consent.version = new_version
            new_consent.save()
            # Reset consent for all users
            User.objects.update(agreed_consent_version=None)
            messages.success(
                request,
                f"Informed consent has been updated to v{new_version}. All users will be required to re-consent.",
            )
            return HttpResponseRedirect(reverse("dashboard:index"))
    else:
        initial_data = {"content": latest_consent.content}
        form = InformedConsentForm(initial=initial_data)

    preview_html = markdown.markdown(latest_consent.content)

    return render(
        request,
        "dashboard/manage_informed_consent.html",
        {
            "form": form,
            "latest_consent": latest_consent if latest_consent.pk else None,
            "preview_html": preview_html,
            "is_default": latest_consent.pk is None,
        },
    )


@login_required
@user_passes_test(is_superuser)
def admin_statistics_api(request):
    """
    API endpoint to asynchronously fetch all statistics for the admin dashboard.
    Uses helper functions from utils.py for cleaner code and reusability.
    """
    statistics = {}

    # User statistics
    statistics["user_signups"] = get_user_signup_stats()
    statistics.update(get_all_profile_distributions())

    # Task statistics
    statistics["task_creations"] = get_task_creation_stats()

    # Time distributions (task times, trial times, histograms, box plots)
    time_stats = get_time_distributions()
    statistics["task_time_distribution"] = time_stats["task_time_distribution"]
    statistics["trial_time_distribution"] = time_stats["trial_time_distribution"]
    statistics["task_time_histogram"] = time_stats["task_time_histogram"]
    statistics["trial_time_distribution_detail"] = time_stats["trial_time_distribution_detail"]
    statistics["trial_count_distribution"] = time_stats["trial_count_distribution"]

    # Success metrics
    total_valid_tasks = Task.valid_objects.count()
    success_metrics = calculate_task_success_metrics()

    cancel_rate = (success_metrics['total_cancelled'] / total_valid_tasks * 100) if total_valid_tasks > 0 else 0
    statistics["cancel_rate"] = round(cancel_rate, 1)
    statistics["success_rate"] = success_metrics['success_rate']
    statistics["self_correction_rate"] = success_metrics['self_correction_rate']
    statistics["first_try_success_rate"] = success_metrics['first_try_success_rate']
    statistics["success_metrics_counts"] = {
        "total_completed": success_metrics['total_completed'],
        "successful": success_metrics['successful_count'],
        "self_corrected": success_metrics['self_corrected_count'],
        "first_try_success": success_metrics['first_try_success_count']
    }

    # Annotation distributions (familiarity, difficulty, effort, confidence)
    statistics.update(get_all_annotation_distributions())

    # Trial statistics (aha moments, correctness, answer methods, evidence)
    statistics.update(get_trial_statistics())

    # JSON field distributions (cancellation reasons, reflection failures)
    statistics["cancellation_reasons"] = get_json_field_distribution(
        CancelAnnotation, "category", Q_VALID_TASK_USER
    )
    statistics["reflection_failures"] = get_json_field_distribution(
        ReflectionAnnotation, "failure_category", Q_VALID_TRIAL_USER
    )

    # Navigation & behavior statistics
    nav_stats = get_navigation_stats()
    statistics["avg_trajectory_length"] = nav_stats["avg_trajectory_length"]
    statistics["avg_pre_task_duration"] = nav_stats["avg_pre_task_duration"]
    statistics["avg_post_task_duration"] = nav_stats["avg_post_task_duration"]
    statistics["dwell_time_distribution"] = nav_stats["dwell_time_distribution"]

    # Top visited domains
    statistics["top_domains"] = get_top_domains()

    return JsonResponse(statistics)

@login_required
@user_passes_test(is_superuser)
def admin_page(request):
    # User search and sort
    user_search_query = request.GET.get("user_search", "")
    user_sort_by = request.GET.get("user_sort_by", "id")
    user_sort_dir = request.GET.get("user_sort_dir", "asc")
    if user_sort_dir not in ["asc", "desc"]:
        user_sort_dir = "asc"
    user_order = f"{'-' if user_sort_dir == 'desc' else ''}{user_sort_by}"

    user_list_query = User.objects.all()
    if user_search_query:
        user_list_query = user_list_query.filter(
            Q(username__icontains=user_search_query)
            | Q(email__icontains=user_search_query)
            | Q(profile__name__icontains=user_search_query)
        )
    users_list = user_list_query.order_by(user_order)

    user_paginator = Paginator(users_list, 10)
    user_page_number = request.GET.get("user_page")
    users = user_paginator.get_page(user_page_number)

    # Task filter and sort
    task_id_filter = request.GET.get("task_id", "")
    task_user_filter = request.GET.get("task_user", "")
    task_status_filter = request.GET.get("task_status", "")
    task_date_start_filter = request.GET.get("task_date_start", "")
    task_date_end_filter = request.GET.get("task_date_end", "")
    task_sort_by = request.GET.get("task_sort_by", "start_timestamp")
    task_sort_dir = request.GET.get("task_sort_dir", "desc")
    if task_sort_dir not in ["asc", "desc"]:
        task_sort_dir = "asc"
    task_order = f"{'-' if task_sort_dir == 'desc' else ''}{task_sort_by}"

    tasks_list = Task.objects.select_related("user").all()
    if task_id_filter:
        tasks_list = tasks_list.filter(id=task_id_filter)
    if task_user_filter:
        tasks_list = tasks_list.filter(user__id=task_user_filter)
    if task_status_filter:
        if task_status_filter == "active":
            tasks_list = tasks_list.filter(active=True)
        elif task_status_filter == "completed":
            tasks_list = tasks_list.filter(active=False, cancelled=False)
        elif task_status_filter == "cancelled":
            tasks_list = tasks_list.filter(cancelled=True)
    if task_date_start_filter:
        tasks_list = tasks_list.filter(
            start_timestamp__date__gte=task_date_start_filter
        )
    if task_date_end_filter:
        tasks_list = tasks_list.filter(start_timestamp__date__lte=task_date_end_filter)
    tasks_list = tasks_list.order_by(task_order)

    task_paginator = Paginator(tasks_list, 10)
    task_page_number = request.GET.get("task_page")
    tasks = task_paginator.get_page(task_page_number)

    context = {
        "users": users,
        "user_search_query": user_search_query,
        "user_sort_by": user_sort_by,
        "user_sort_dir": user_sort_dir,
        "tasks": tasks,
        "task_id_filter": task_id_filter,
        "task_user_filter": task_user_filter,
        "task_status_filter": task_status_filter,
        "task_date_start_filter": task_date_start_filter,
        "task_date_end_filter": task_date_end_filter,
        "task_sort_by": task_sort_by,
        "task_sort_dir": task_sort_dir,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        partial_target = request.GET.get("partial")
        if partial_target == "user-table-container":
            return render(request, "dashboard/partials/_user_table.html", context)
        elif partial_target == "task-table-container":
            # Add all_users to context for the filter dropdown in the partial
            context["all_users"] = User.objects.all()
            return render(request, "dashboard/partials/_task_table.html", context)

    # Dashboard metrics for full page load
    context.update(
        {
            "total_users": User.participants.count(),
            "superusers": User.objects.filter(is_superuser=True).count(),
            "active_users": User.participants.filter(
                last_login__gte=timezone.now() - timedelta(days=30)
            ).count(),
            "total_tasks": Task.valid_objects.count(),
            "completed_tasks": Task.valid_objects.filter(
                cancelled=False, active=False
            ).count(),
            "cancelled_tasks": Task.valid_objects.filter(cancelled=True).count(),
            "active_tasks": Task.valid_objects.filter(active=True).count(),
            "total_bulletins": Bulletin.objects.count(),
            "total_posts": Post.objects.count(),
            "total_comments": Comment.objects.count(),
            "all_users": User.objects.all(),
        }
    )

    return render(request, "dashboard/index.html", context)


@login_required
@user_passes_test(is_superuser)
def delete_user(request, user_id):
    if request.method == "POST":
        user_to_delete = get_object_or_404(User, id=user_id)
        if request.user.id == user_to_delete.id:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error", "message": "You cannot delete yourself."},
                    status=400,
                )
            else:
                return HttpResponseRedirect(reverse("dashboard:index"))

        user_to_delete.delete()

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"status": "success", "message": "User deleted successfully."}
            )
        else:
            return HttpResponseRedirect(reverse("dashboard:index"))

    return HttpResponseRedirect(reverse("dashboard:index"))


@login_required
@user_passes_test(is_superuser)
def toggle_superuser(request, user_id):
    if request.method == "POST" and request.user.is_primary_superuser:
        user_to_toggle = get_object_or_404(User, id=user_id)
        if request.user.id != user_to_toggle.id:
            user_to_toggle.is_superuser = not user_to_toggle.is_superuser
            user_to_toggle.save()
            return JsonResponse(
                {"status": "success", "is_superuser": user_to_toggle.is_superuser}
            )
    return JsonResponse({"status": "error"}, status=400)


@login_required
@user_passes_test(is_superuser)
def login_as_user(request, user_id):
    if request.method == "POST":
        user_to_login = get_object_or_404(User, id=user_id)
        if (
            not user_to_login.is_primary_superuser
            and request.user.id != user_to_login.id
        ):
            original_admin_id = request.user.id

            # Log in as the new user first, as this may flush the session
            auth_login(request, user_to_login)

            # Now, set the token in the new session
            signer = Signer()
            request.session["original_user_token"] = signer.sign(original_admin_id)

            return HttpResponseRedirect(reverse("task_manager:home"))
    return HttpResponseRedirect(reverse("dashboard:index"))


@login_required
@require_POST
def return_to_admin(request):
    signed_token = request.session.pop("original_user_token", None)
    if signed_token:
        signer = Signer()
        try:
            admin_id = signer.unsign(signed_token)
            admin_user = get_object_or_404(User, id=admin_id)
            auth_login(request, admin_user)
        except (BadSignature, User.DoesNotExist):
            # The invalid token has already been removed.
            # We can simply redirect without any further action.
            pass
    return HttpResponseRedirect(reverse("dashboard:index"))


@login_required
@user_passes_test(is_superuser)
def manage_extension_versions(request):
    if request.method == "POST":
        form = ExtensionVersionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New extension version added successfully.")
            return HttpResponseRedirect(reverse("dashboard:manage_extension_versions"))
    else:
        form = ExtensionVersionForm()

    versions = ExtensionVersion.objects.all().order_by("-id")
    return render(
        request, "dashboard/manage_extension_versions.html", {"form": form, "versions": versions}
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def view_user_info(request, user_id):
    user_info = get_object_or_404(User, id=user_id)
    return render(
        request,
        "info.html",
        {
            "cur_user": user_info,
        },
    )


@login_required
@user_passes_test(is_superuser)
@require_POST
def revert_latest_extension_version(request):
    latest_version = ExtensionVersion.objects.order_by("-id").first()
    if latest_version:
        version_number = latest_version.version
        latest_version.delete()
        messages.success(request, f"Successfully reverted version {version_number}.")
    else:
        messages.warning(request, "No extension versions to revert.")
    return HttpResponseRedirect(reverse("dashboard:manage_extension_versions"))


# ============================================
# Data Export/Import Views
# ============================================

@login_required
@user_passes_test(is_superuser)
def export_users_list(request):
    """Get list of valid users with finished tasks for export selection."""
    from django.db.models import Count, Q as DQ

    # Get dataset filter from request
    exclude_datasets_str = request.GET.get('exclude_datasets', '')
    exclude_dataset_ids = []
    if exclude_datasets_str:
        try:
            exclude_dataset_ids = [int(d.strip()) for d in exclude_datasets_str.split(',') if d.strip()]
        except ValueError:
            pass

    # Build task filter - fields are relative to the 'task' relationship
    task_filter = DQ(task__active=False)  # Only finished tasks
    if exclude_dataset_ids:
        task_filter &= ~DQ(task__content__belong_dataset_id__in=exclude_dataset_ids)

    # Get users with finished task counts (excluding specified datasets)
    users = User.objects.filter(Q_VALID_USER).select_related('profile').annotate(
        finished_task_count=Count('task', filter=task_filter)
    ).filter(finished_task_count__gt=0).order_by('id')

    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.profile.name if hasattr(user, 'profile') else '',
            'task_count': user.finished_task_count,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        })
    return JsonResponse({'users': user_list})


@login_required
@user_passes_test(is_superuser)
def export_datasets_list(request):
    """Get list of datasets for export selection."""
    from task_manager.models import TaskDataset
    from django.db.models import Count

    datasets = TaskDataset.objects.annotate(
        task_count=Count('taskdatasetentry__task', filter=Q(
            taskdatasetentry__task__user__is_superuser=False,
            taskdatasetentry__task__user__is_test_account=False,
            taskdatasetentry__task__active=False
        ))
    ).filter(task_count__gt=0).order_by('name')

    dataset_list = []
    for ds in datasets:
        # Check if it's a tutorial dataset (by name)
        is_tutorial = 'tutorial' in ds.name.lower()
        dataset_list.append({
            'id': ds.id,
            'name': ds.name,
            'task_count': ds.task_count,
            'is_tutorial': is_tutorial,
        })
    return JsonResponse({'datasets': dataset_list})


@login_required
@user_passes_test(is_superuser)
@require_POST
def export_preview(request):
    """Get preview of what would be exported."""
    from .utils.export import TaskManagerExporter

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_ids = data.get('user_ids', [])
    anonymize = data.get('anonymize', True)
    exclude_dataset_ids = data.get('exclude_datasets', [])

    # Validate types
    if not isinstance(user_ids, list):
        return JsonResponse({'error': 'user_ids must be a list'}, status=400)
    if not isinstance(exclude_dataset_ids, list):
        return JsonResponse({'error': 'exclude_datasets must be a list'}, status=400)

    exporter = TaskManagerExporter(anonymize=anonymize)
    preview = exporter.get_export_preview(
        user_ids=user_ids if user_ids else None,
        exclude_dataset_ids=exclude_dataset_ids if exclude_dataset_ids else None
    )

    return JsonResponse({
        'preview': preview,
    })


def _run_export(export_id, temp_dir, user_ids, anonymize, exclude_dataset_ids):
    """Background thread function that runs the export and updates Redis progress."""
    import django.db
    import redis as redis_lib
    import zipfile
    import shutil

    from .utils.export import TaskManagerExporter, ExportRedisKeys
    from .utils.huggingface import save_huggingface_files

    r = redis_lib.Redis()
    progress_key = ExportRedisKeys.progress(export_id)

    def _update_progress(**fields):
        r.hset(progress_key, mapping={k: json.dumps(v) for k, v in fields.items()})
        r.expire(progress_key, ExportRedisKeys.TTL)

    try:
        _update_progress(status="running", current_user=0, total_users=0, tasks_exported=0)

        def on_progress(current_user, total_users, tasks_exported):
            _update_progress(
                status="running",
                current_user=current_user,
                total_users=total_users,
                tasks_exported=tasks_exported,
            )

        exporter = TaskManagerExporter(anonymize=anonymize)
        stats = exporter.export_to_file(
            temp_dir,
            user_ids=user_ids if user_ids else None,
            exclude_dataset_ids=exclude_dataset_ids if exclude_dataset_ids else None,
            on_progress=on_progress,
        )
        save_huggingface_files(temp_dir, stats, anonymized=anonymize)

        _update_progress(status="zipping", tasks_exported=stats["task_count"],
                         current_user=stats["participant_count"],
                         total_users=stats["participant_count"])

        # Create zip file
        zip_path = os.path.join(temp_dir, 'export.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in ['data.jsonl', 'dataset_info.json', 'README.md']:
                filepath = os.path.join(temp_dir, filename)
                if os.path.exists(filepath):
                    zf.write(filepath, filename)

        mode_suffix = 'anonymized' if anonymize else 'full'
        _update_progress(
            status="complete",
            zip_path=zip_path,
            filename=f'task_data_export_{mode_suffix}.zip',
            tasks_exported=stats["task_count"],
            current_user=stats["participant_count"],
            total_users=stats["participant_count"],
        )

    except Exception as e:
        logger.exception("Export %s failed", export_id)
        _update_progress(status="error", error=str(e))
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
    finally:
        django.db.connections.close_all()


@login_required
@user_passes_test(is_superuser)
@require_POST
def start_export(request):
    """Start a background export and return the export ID immediately."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_ids = data.get('user_ids', [])
    anonymize = data.get('anonymize', True)
    exclude_dataset_ids = data.get('exclude_datasets', [])

    export_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp()

    t = threading.Thread(
        target=_run_export,
        args=(export_id, temp_dir, user_ids, anonymize, exclude_dataset_ids),
        daemon=True,
    )
    t.start()

    return JsonResponse({'export_id': export_id})


@login_required
@user_passes_test(is_superuser)
@require_GET
def export_progress(request, export_id):
    """Poll the progress of a running export."""
    import redis as redis_lib
    from .utils.export import ExportRedisKeys

    r = redis_lib.Redis()
    progress_key = ExportRedisKeys.progress(export_id)
    raw = r.hgetall(progress_key)

    if not raw:
        return JsonResponse({'error': 'Export not found or expired'}, status=404)

    data = {k.decode(): json.loads(v.decode()) for k, v in raw.items()}
    return JsonResponse(data)


@login_required
@user_passes_test(is_superuser)
@require_GET
def download_export(request, export_id):
    """Download the completed export zip file."""
    import redis as redis_lib
    import shutil
    from .utils.export import ExportRedisKeys

    r = redis_lib.Redis()
    progress_key = ExportRedisKeys.progress(export_id)
    raw = r.hgetall(progress_key)

    if not raw:
        return JsonResponse({'error': 'Export not found or expired'}, status=404)

    data = {k.decode(): json.loads(v.decode()) for k, v in raw.items()}

    if data.get('status') != 'complete':
        return JsonResponse({'error': 'Export not ready'}, status=400)

    zip_path = data.get('zip_path', '')
    if not zip_path or not os.path.exists(zip_path):
        return JsonResponse({'error': 'Export file not found'}, status=404)

    file_size = os.path.getsize(zip_path)
    temp_dir = os.path.dirname(zip_path)
    filename = data.get('filename', 'task_data_export.zip')

    def file_iterator(file_path, chunk_size=8192):
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        finally:
            r.delete(progress_key)
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

    response = StreamingHttpResponse(
        file_iterator(zip_path),
        content_type='application/zip'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = file_size
    return response


@login_required
@user_passes_test(is_superuser)
@require_POST
def import_preview(request):
    """Validate and preview import from uploaded file."""
    from .utils.importer import TaskManagerImporter

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    uploaded_file = request.FILES['file']

    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.jsonl', delete=False) as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_path = temp_file.name

    try:
        mode = request.POST.get('mode', 'full')
        if mode not in ('full', 'incremental'):
            mode = 'full'

        importer = TaskManagerImporter()
        preview = importer.validate_and_preview(temp_path, mode=mode)
        # Store temp path and mode in session for actual import
        request.session['import_temp_path'] = temp_path
        request.session['import_mode'] = mode
        return JsonResponse(preview)
    except Exception as e:
        os.unlink(temp_path)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(is_superuser)
@require_POST
def import_data(request):
    """Import data from previously uploaded file."""
    from .utils.importer import TaskManagerImporter, ImportValidationError

    # Get temp path and mode from session
    temp_path = request.session.get('import_temp_path')
    if not temp_path or not os.path.exists(temp_path):
        return JsonResponse({'error': 'No file to import. Please upload again.'}, status=400)

    mode = request.session.get('import_mode', 'full')

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    # Verify admin password only for full mode (destructive)
    if mode == 'full':
        password = data.get('password')
        if not password:
            return JsonResponse({'error': 'Password required'}, status=400)

        user = authenticate(username=request.user.username, password=password)
        if not user or not user.is_superuser:
            return JsonResponse({'error': 'Invalid password'}, status=401)

    try:
        importer = TaskManagerImporter()
        stats = importer.import_from_file(temp_path, mode=mode)

        # Clean up
        os.unlink(temp_path)
        del request.session['import_temp_path']
        if 'import_mode' in request.session:
            del request.session['import_mode']

        return JsonResponse({
            'success': True,
            'stats': stats,
        })
    except ImportValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)