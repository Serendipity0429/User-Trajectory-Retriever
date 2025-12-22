#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.signing import Signer, BadSignature
from django.contrib.auth import login as auth_login
from django.db.models import Count, Q, Avg
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import markdown
import json
from collections import Counter, defaultdict
import numpy as np
from urllib.parse import urlparse
from django.conf import settings
from django.db import connection

from user_system.models import User, InformedConsent, Profile
from task_manager.models import (
    Task, ExtensionVersion, TaskTrial, PreTaskAnnotation, PostTaskAnnotation,
    CancelAnnotation, ReflectionAnnotation, Justification, Webpage
)
from task_manager.mappings import (
    ANSWER_FORMULATION_MAP, FAMILIARITY_MAP, DIFFICULTY_MAP, EFFORT_MAP, CONFIDENCE_MAP
)
from discussion.models import Bulletin, Post, Comment

from user_system.forms import InformedConsentForm
from task_manager.forms import ExtensionVersionForm
from core.filters import Q_VALID_USER, Q_VALID_USER_REL, Q_VALID_TASK_USER, Q_VALID_TRIAL_USER

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
    """
    statistics = {}

    # User statistics
    thirty_days_ago = timezone.now() - timedelta(days=30)
    user_signups = (
        User.participants.filter(date_joined__gte=thirty_days_ago)
        .annotate(date=TruncDate("date_joined"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    statistics["user_signups"] = {
        "labels": [x["date"] for x in user_signups], "data": [x["count"] for x in user_signups]
    }

    def get_profile_distribution(field, choices):
        counts = Profile.objects.filter(Q_VALID_USER_REL).values(field).annotate(count=Count(field))
        return {
            "labels": [
                dict(choices).get(c[field], "N/A") for c in counts if c[field]
            ],
            "data": [c["count"] for c in counts if c[field]],
        }

    statistics["gender_distribution"] = get_profile_distribution("gender", Profile.GENDER_CHOICES)
    statistics["occupation_distribution"] = get_profile_distribution("occupation", Profile.OCCUPATION_CHOICES)
    statistics["education_distribution"] = get_profile_distribution("education", Profile.EDUCATION_CHOICES)
    statistics["llm_frequency_distribution"] = get_profile_distribution("llm_frequency", Profile.LLM_FREQUENCY_CHOICES)
    statistics["english_proficiency_distribution"] = get_profile_distribution(
        "english_proficiency", Profile.ENGLISH_PROFICIENCY_CHOICES
    )
    statistics["web_search_proficiency_distribution"] = get_profile_distribution(
        "web_search_proficiency", Profile.WEB_SEARCH_PROFICIENCY_CHOICES
    )

    # Task statistics
    task_creations = (
        Task.valid_objects.filter(start_timestamp__gte=thirty_days_ago)
        .annotate(date=TruncDate("start_timestamp"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    statistics["task_creations"] = {
        "labels": [x["date"] for x in task_creations], "data": [x["count"] for x in task_creations]
    }

    completed_tasks = Task.valid_objects.filter(
        active=False, end_timestamp__isnull=False
    ).prefetch_related('tasktrial_set')
    
    task_time_distribution = [
        (task.end_timestamp - task.start_timestamp).total_seconds()
        for task in completed_tasks
    ]
    statistics["task_time_distribution"] = task_time_distribution

    all_trials = TaskTrial.objects.filter(Q_VALID_TASK_USER, end_timestamp__isnull=False)
    trial_time_distribution = [
        (trial.end_timestamp - trial.start_timestamp).total_seconds()
        for trial in all_trials
    ]
    statistics["trial_time_distribution"] = trial_time_distribution

    # Task time histogram data
    if task_time_distribution:
        hist, bins = np.histogram(task_time_distribution, bins=10)
        statistics["task_time_histogram"] = {
            "hist": hist.tolist(),
            "bins": bins.tolist()
        }
    else:
        statistics["task_time_histogram"] = {"hist": [], "bins": []}

    # Trial time box plot series data
    trial_times_by_num = defaultdict(list)
    
    # Calculate global 99th percentile to filter extreme outliers
    all_durations = [(t.end_timestamp - t.start_timestamp).total_seconds() for t in all_trials]
    if all_durations:
        cutoff_threshold = np.percentile(all_durations, 99)
    else:
        cutoff_threshold = float('inf')

    for trial in all_trials:
        duration = (trial.end_timestamp - trial.start_timestamp).total_seconds()
        if duration <= cutoff_threshold:
            trial_times_by_num[trial.num_trial].append(duration)
    
    sorted_trial_nums = sorted(trial_times_by_num.keys())
    trial_time_distribution_detail = {
        "labels": [f"Trial {n}" for n in sorted_trial_nums],
        "data": [trial_times_by_num[n] for n in sorted_trial_nums]
    }
    statistics["trial_time_distribution_detail"] = trial_time_distribution_detail

    # Trial count distribution
    tasks_with_trial_counts = completed_tasks.annotate(num_trials=Count('tasktrial'))
    trial_counts = [task.num_trials for task in tasks_with_trial_counts]
    if trial_counts:
        trial_count_freq = Counter(trial_counts)
        statistics["trial_count_distribution"] = {
            "labels": [f"{count} trials" for count in sorted(trial_count_freq.keys())],
            "data": [trial_count_freq[count] for count in sorted(trial_count_freq.keys())]
        }
    else:
        statistics["trial_count_distribution"] = {"labels": [], "data": []}

    # --- Advanced Success Metrics ---
    total_valid_tasks = Task.valid_objects.count()
    total_completed_count = completed_tasks.count()
    total_cancelled_count = Task.valid_objects.filter(cancelled=True).count()
    
    # Cancel Rate
    cancel_rate = (total_cancelled_count / total_valid_tasks * 100) if total_valid_tasks > 0 else 0
    statistics["cancel_rate"] = round(cancel_rate, 1)

    # Success Analysis (within completed tasks)
    successful_tasks_count = 0
    self_corrected_count = 0
    first_try_success_count = 0
    
    # Pre-fetch trials for efficiency
    # We need to know if a completed task has at least one correct trial
    # and if the first trial was correct or not.
    for task in tasks_with_trial_counts:
        trials = task.tasktrial_set.all().order_by('start_timestamp')
        if not trials:
            continue
        
        # Check for any correct trial
        has_success = False
        first_trial_correct = False
        
        for idx, trial in enumerate(trials):
            if trial.is_correct:
                has_success = True
                if idx == 0:
                    first_trial_correct = True
                break # Found success, stop checking for success status
        
        if has_success:
            successful_tasks_count += 1
            if first_trial_correct:
                first_try_success_count += 1
            else:
                self_corrected_count += 1

    # Success Rate (relative to completed tasks)
    success_rate = (successful_tasks_count / total_completed_count * 100) if total_completed_count > 0 else 0
    statistics["success_rate"] = round(success_rate, 1)

    # Self-Correction Rate (relative to SUCCESSFUL tasks)
    # i.e., what % of solved tasks required > 1 attempt?
    self_correction_rate = (self_corrected_count / successful_tasks_count * 100) if successful_tasks_count > 0 else 0
    statistics["self_correction_rate"] = round(self_correction_rate, 1)

    # First Attempt Success Rate (relative to SUCCESSFUL tasks)
    first_try_success_rate = (first_try_success_count / successful_tasks_count * 100) if successful_tasks_count > 0 else 0
    statistics["first_try_success_rate"] = round(first_try_success_rate, 1)
    
    statistics["success_metrics_counts"] = {
        "total_completed": total_completed_count,
        "successful": successful_tasks_count,
        "self_corrected": self_corrected_count,
        "first_try_success": first_try_success_count
    }

    def get_annotation_distribution(model, field, mapping, q_obj):
        counts = model.objects.filter(q_obj).values(field).annotate(count=Count(field))
        return {
            "labels": [mapping.get(str(c[field]), str(c[field])) for c in counts if c[field] is not None],
            "data": [c["count"] for c in counts if c[field] is not None],
        }

    familiarity_mapping = {str(k): v for k, v in FAMILIARITY_MAP["mapping"].items()}
    difficulty_mapping = {str(k): v for k, v in DIFFICULTY_MAP["mapping"].items()}
    effort_mapping = {str(k): v for k, v in EFFORT_MAP["mapping"].items()}
    confidence_mapping = {str(k): v for k, v in CONFIDENCE_MAP["mapping"].items()}


    statistics["familiarity_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "familiarity", familiarity_mapping, Q_VALID_TASK_USER
    )
    statistics["pre_task_difficulty_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "difficulty", difficulty_mapping, Q_VALID_TASK_USER
    )
    statistics["post_task_difficulty_distribution"] = get_annotation_distribution(
        PostTaskAnnotation, "difficulty_actual", difficulty_mapping, Q_VALID_TASK_USER
    )
    statistics["effort_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "effort", effort_mapping, Q_VALID_TASK_USER
    )

    # Aha Moment
    aha_moment_counts = PostTaskAnnotation.objects.filter(Q_VALID_TASK_USER).values('aha_moment_type').annotate(count=Count('aha_moment_type')).exclude(aha_moment_type__isnull=True)
    statistics["aha_moment_distribution"] = {
        "labels": [item['aha_moment_type'] for item in aha_moment_counts],
        "data": [item['count'] for item in aha_moment_counts]
    }

    # Trial Correctness
    is_correct_counts = TaskTrial.objects.filter(Q_VALID_TASK_USER).values('is_correct').annotate(count=Count('is_correct'))
    def get_correctness_label(value):
        if value is True: return "Correct"
        if value is False: return "Incorrect"
        return "Not Evaluated"
    statistics["trial_correctness_distribution"] = {
        "labels": [get_correctness_label(item['is_correct']) for item in is_correct_counts],
        "data": [item['count'] for item in is_correct_counts]
    }
    
    # Confidence
    statistics["confidence_distribution"] = get_annotation_distribution(
        TaskTrial, "confidence", confidence_mapping, Q_VALID_TASK_USER
    )
    
    # Answer Formulation Method
    afm_mapping = ANSWER_FORMULATION_MAP["mapping"]
    afm_data = TaskTrial.objects.filter(Q_VALID_TASK_USER).values_list('answer_formulation_method', flat=True)
    afm_flat = []
    for item in afm_data:
        if isinstance(item, list):
            afm_flat.extend(item)
        elif item and item != 'undefined':
            afm_flat.append(item)
    
    afm_counts = Counter(afm_flat)
    
    def clean_afm_label(key):
        val = afm_mapping.get(key, key)
        # Strip simple HTML tags if they exist
        text = val.replace("<strong>", "").replace("</strong>", "")
        # Get the part before colon if exists (e.g., "Direct Answer: ...")
        return text.split(':')[0].strip()

    statistics["answer_formulation_method_distribution"] = {
        "labels": [clean_afm_label(k) for k in afm_counts.keys()],
        "data": list(afm_counts.values())
    }
    
    # Evidence Type
    evidence_type_counts = Justification.objects.filter(Q_VALID_TRIAL_USER).values('evidence_type').annotate(count=Count('evidence_type'))
    statistics["evidence_type_distribution"] = {
        "labels": [item['evidence_type'] for item in evidence_type_counts],
        "data": [item['count'] for item in evidence_type_counts]
    }

    # Dwell Time
    dwell_times = Webpage.objects.filter(Q_VALID_USER_REL).exclude(dwell_time__isnull=True).values_list('dwell_time', flat=True)
    # Ensure values are integers and filter out errors
    cleaned_dwell_times = []
    for dt in dwell_times:
        try:
            val = int(dt)
            if val >= 0:
                cleaned_dwell_times.append(val)
        except (ValueError, TypeError):
            continue
    statistics["dwell_time_distribution"] = cleaned_dwell_times


    def get_json_field_distribution(model, field, q_obj):
        all_values = model.objects.filter(q_obj).exclude(**{f"{field}__isnull": True}).values_list(
            field, flat=True
        )
        counts = Counter()
        for sublist in all_values:
            # Parse JSON string if necessary
            if isinstance(sublist, str):
                try:
                    sublist = json.loads(sublist)
                except json.JSONDecodeError:
                    continue
            
            if sublist:
                # If it's a list, update with items; if single item (unlikely for JSON list field but possible), update with it
                if isinstance(sublist, list):
                    counts.update(sublist)
                else:
                    counts.update([sublist])
        return {"labels": list(counts.keys()), "data": list(counts.values())}

    statistics["cancellation_reasons"] = get_json_field_distribution(CancelAnnotation, "category", Q_VALID_TASK_USER)
    statistics["reflection_failures"] = get_json_field_distribution(ReflectionAnnotation, "failure_category", Q_VALID_TRIAL_USER)

    # --- Navigation & Behavior Analysis ---
    
    # Average Trajectory Length (Pages per Task)
    # We count webpages per task, then average those counts
    trajectory_stats = Webpage.objects.filter(Q_VALID_USER_REL).values('belong_task').annotate(page_count=Count('id')).aggregate(avg_length=Avg('page_count'))
    statistics["avg_trajectory_length"] = round(trajectory_stats['avg_length'] or 0, 1)

    # Annotation Burden (Time in seconds)
    avg_pre = PreTaskAnnotation.objects.filter(Q_VALID_TASK_USER).aggregate(avg=Avg('duration'))
    avg_post = PostTaskAnnotation.objects.filter(Q_VALID_TASK_USER).aggregate(avg=Avg('duration'))
    statistics["avg_pre_task_duration"] = round(avg_pre['avg'] or 0, 1)
    statistics["avg_post_task_duration"] = round(avg_post['avg'] or 0, 1)

    # Top Visited Domains
    domains = []
    
    if getattr(settings, 'DATABASE_TYPE', 'sqlite') == 'postgres':
        # Optimized for PostgreSQL: Extract domain in DB
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    substring(url from '.*://([^/]*)') as domain,
                    COUNT(*) as count
                FROM task_manager_webpage
                INNER JOIN user_system_user ON task_manager_webpage.user_id = user_system_user.id
                WHERE (user_system_user.is_superuser = false AND user_system_user.is_staff = false)
                GROUP BY domain
                ORDER BY count DESC
                LIMIT 10;
            """)
            top_domains_counts = cursor.fetchall()
            # Clean up www. prefix in Python if needed, or refine regex
            # Simple cleanup for consistency
            cleaned_counts = []
            for domain, count in top_domains_counts:
                if domain:
                    d = domain.lower()
                    if d.startswith('www.'): d = d[4:]
                    cleaned_counts.append((d, count))
            
            # Re-aggregate if stripping www caused duplicates
            final_counts = Counter()
            for d, c in cleaned_counts:
                final_counts[d] += c
            top_domains_counts = final_counts.most_common(10)

    else:
        # Fallback for SQLite: Process in Python with iterator to save memory
        # Use iterator() to fetch rows one by one instead of loading all into memory
        all_urls = Webpage.objects.filter(Q_VALID_USER_REL).values_list('url', flat=True).iterator()
        
        for url in all_urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    domain = parsed.netloc.lower()
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    domains.append(domain)
            except Exception:
                continue
        top_domains_counts = Counter(domains).most_common(10)

    statistics["top_domains"] = {
        "labels": [item[0] for item in top_domains_counts],
        "data": [item[1] for item in top_domains_counts]
    }

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