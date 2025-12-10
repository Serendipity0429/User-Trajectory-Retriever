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
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import markdown
import json
from collections import Counter, defaultdict
import numpy as np

from user_system.models import User, InformedConsent, Profile
from task_manager.models import (
    Task, ExtensionVersion, TaskTrial, PreTaskAnnotation, PostTaskAnnotation,
    CancelAnnotation, ReflectionAnnotation, Justification, Webpage
)
from discussion.models import Bulletin, Post, Comment

from user_system.forms import InformedConsentForm
from task_manager.forms import ExtensionVersionForm

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def view_current_consent(request):
    latest_consent = InformedConsent.get_latest()
    total_users_count = User.objects.count()

    if latest_consent and latest_consent.pk:
        signed_users_count = User.objects.filter(
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
        User.objects.filter(date_joined__gte=thirty_days_ago)
        .extra(select={"date": "date(date_joined)"})
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    statistics["user_signups"] = {
        "labels": [x["date"] for x in user_signups], "data": [x["count"] for x in user_signups]
    }

    def get_profile_distribution(field, choices):
        counts = Profile.objects.values(field).annotate(count=Count(field))
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
        Task.objects.filter(start_timestamp__gte=thirty_days_ago)
        .extra(select={"date": "date(start_timestamp)"})
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    statistics["task_creations"] = {
        "labels": [x["date"] for x in task_creations], "data": [x["count"] for x in task_creations]
    }

    completed_tasks = Task.objects.filter(cancelled=False, active=False, end_timestamp__isnull=False)
    task_time_distribution = [
        (task.end_timestamp - task.start_timestamp).total_seconds()
        for task in completed_tasks
    ]
    statistics["task_time_distribution"] = task_time_distribution

    all_trials = TaskTrial.objects.filter(end_timestamp__isnull=False)
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
    for trial in all_trials:
        duration = (trial.end_timestamp - trial.start_timestamp).total_seconds()
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

    def get_annotation_distribution(model, field, mapping):
        counts = model.objects.values(field).annotate(count=Count(field))
        return {
            "labels": [mapping.get(str(c[field])) for c in counts if c[field] is not None],
            "data": [c["count"] for c in counts if c[field] is not None],
        }

    familiarity_mapping = {
        "0": "Not familiar at all", "1": "Slightly familiar", "2": "Moderately familiar",
        "3": "Very familiar", "4": "Expert",
    }
    difficulty_mapping = {
        "0": "Very easy", "1": "Easy", "2": "Moderate", "3": "Hard", "4": "Very hard",
    }
    effort_mapping = {
        "0": "Less than 5 minutes", "1": "5-15 minutes", "2": "15-30 minutes",
        "3": "30-60 minutes", "4": "1-2 hours", "5": "More than 2 hours"
    }
    confidence_mapping = {
        "0": "Not confident at all", "1": "Slightly confident", "2": "Moderately confident",
        "3": "Very confident", "4": "Completely confident",
    }


    statistics["familiarity_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "familiarity", familiarity_mapping
    )
    statistics["pre_task_difficulty_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "difficulty", difficulty_mapping
    )
    statistics["post_task_difficulty_distribution"] = get_annotation_distribution(
        PostTaskAnnotation, "difficulty_actual", difficulty_mapping
    )
    statistics["effort_distribution"] = get_annotation_distribution(
        PreTaskAnnotation, "effort", effort_mapping
    )

    # Aha Moment
    aha_moment_counts = PostTaskAnnotation.objects.values('aha_moment_type').annotate(count=Count('aha_moment_type')).exclude(aha_moment_type__isnull=True)
    statistics["aha_moment_distribution"] = {
        "labels": [item['aha_moment_type'] for item in aha_moment_counts],
        "data": [item['count'] for item in aha_moment_counts]
    }

    # Trial Correctness
    is_correct_counts = TaskTrial.objects.values('is_correct').annotate(count=Count('is_correct'))
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
        TaskTrial, "confidence", confidence_mapping
    )
    
    # Answer Formulation Method
    answer_formulation_counts = TaskTrial.objects.values('answer_formulation_method').annotate(count=Count('answer_formulation_method')).exclude(answer_formulation_method='undefined').exclude(answer_formulation_method__isnull=True)
    statistics["answer_formulation_method_distribution"] = {
        "labels": [item['answer_formulation_method'] for item in answer_formulation_counts],
        "data": [item['count'] for item in answer_formulation_counts]
    }
    
    # Evidence Type
    evidence_type_counts = Justification.objects.values('evidence_type').annotate(count=Count('evidence_type'))
    statistics["evidence_type_distribution"] = {
        "labels": [item['evidence_type'] for item in evidence_type_counts],
        "data": [item['count'] for item in evidence_type_counts]
    }

    # Dwell Time
    dwell_times = Webpage.objects.exclude(dwell_time__isnull=True).values_list('dwell_time', flat=True)
    statistics["dwell_time_distribution"] = list(dwell_times)


    def get_json_field_distribution(model, field):
        all_values = model.objects.exclude(**{f"{field}__isnull": True}).values_list(
            field, flat=True
        )
        counts = Counter()
        for sublist in all_values:
            if sublist:
                counts.update(sublist)
        return {"labels": list(counts.keys()), "data": list(counts.values())}

    statistics["cancellation_reasons"] = get_json_field_distribution(CancelAnnotation, "category")
    statistics["reflection_failures"] = get_json_field_distribution(ReflectionAnnotation, "failure_category")

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
            "total_users": User.objects.count(),
            "superusers": User.objects.filter(is_superuser=True).count(),
            "active_users": User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=30)
            ).count(),
            "total_tasks": Task.objects.count(),
            "completed_tasks": Task.objects.filter(
                cancelled=False, active=False
            ).count(),
            "cancelled_tasks": Task.objects.filter(cancelled=True).count(),
            "active_tasks": Task.objects.filter(active=True).count(),
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
        "dashboard/view_user_info.html",
        {
            "user_info": user_info,
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