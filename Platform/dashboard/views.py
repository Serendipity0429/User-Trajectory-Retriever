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
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import markdown

from user_system.models import User, InformedConsent
from task_manager.models import Task, ExtensionVersion, CancelAnnotation, ReflectionAnnotation
from discussion.models import Bulletin, Post, Comment

from user_system.forms import InformedConsentForm
from task_manager.forms import ExtensionVersionForm
from core.filters import Q_VALID_TASK_USER, Q_VALID_TRIAL_USER
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