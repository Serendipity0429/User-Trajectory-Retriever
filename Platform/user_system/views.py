#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from .forms import (
    InformedConsentForm,
    CustomAuthenticationForm,
    SignupForm,
    EditInfoForm,
    EditPasswordForm,
    ForgetPasswordForm,
    ResetPasswordForm,
)
from .models import User, ResetPasswordRequest, InformedConsent
from .utils import authenticate, print_debug, redirect_to_prev_page
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
import logging
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    get_user_model,
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.templatetags.static import static
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.views import View
from django.core.signing import Signer, BadSignature
from django.views.decorators.http import require_POST
from task_manager.models import Task, ExtensionVersion
from task_manager.forms import ExtensionVersionForm
from .utils import send_reset_password_email
from discussion.models import Bulletin, Post, Comment
from .decorators import consent_exempt
import markdown
import json
from collections import Counter, defaultdict
import numpy as np
from task_manager.models import (
    PreTaskAnnotation,
    PostTaskAnnotation,
    CancelAnnotation,
    ReflectionAnnotation,
    TaskTrial,
    Justification,
    Webpage,
)
from user_system.models import Profile
from django.db.models import Count, Avg


USER_SEARCH_RESULT_LIMIT = 8



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
            return HttpResponseRedirect(reverse("user_system:admin_page"))
    else:
        initial_data = {"content": latest_consent.content}
        form = InformedConsentForm(initial=initial_data)

    preview_html = markdown.markdown(latest_consent.content)

    return render(
        request,
        "manage_informed_consent.html",
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
            return render(request, "partials/_user_table.html", context)
        elif partial_target == "task-table-container":
            # Add all_users to context for the filter dropdown in the partial
            context["all_users"] = User.objects.all()
            return render(request, "partials/_task_table.html", context)

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

    return render(request, "admin_page.html", context)



@csrf_exempt
@consent_exempt
def token_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        username = request.POST.get("username")
        password = request.POST.get("password")
        force_login = request.POST.get("force", "false").lower() == "true"

        error_code, user = authenticate(username, password)

        if error_code == 0 and user:
            if user.extension_session_token and not force_login:
                return JsonResponse(
                    {
                        "status": "already_logged_in",
                        "last_login_from": user.last_login_from,
                    }
                )

            # Generate a new session token
            session_token = uuid.uuid4().hex
            user.extension_session_token = session_token

            # Get user's IP address
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0]
            else:
                ip = request.META.get("REMOTE_ADDR")
            user.last_login_from = ip

            user.login_num += 1
            user.last_login = now()
            user.save()

            refresh = RefreshToken.for_user(user)
            # Add session_token to the token payload
            refresh["extension_session_token"] = session_token

            return JsonResponse(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            )
        else:
            print_debug(
                f"User {username} authentication failed with error code {error_code}"
            )
            error_messages = {
                1: "User does not exist",
                2: "Incorrect password",
                4: "Authentication failed",
            }
            return JsonResponse(
                {
                    "error": error_messages.get(error_code, "Authentication failed"),
                    "error_code": error_code,
                },
                status=401,
            )
    except Exception as e:
        logging.error(f"An unexpected error occurred during token login: {e}")
        return JsonResponse(
            {
                "error": "An unexpected error occurred. Please try again later.",
                "error_code": 3,
            },
            status=500,
        )


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
                return HttpResponseRedirect(reverse("user_system:admin_page"))

        user_to_delete.delete()

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"status": "success", "message": "User deleted successfully."}
            )
        else:
            return HttpResponseRedirect(reverse("user_system:admin_page"))

    return HttpResponseRedirect(reverse("user_system:admin_page"))


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
    return HttpResponseRedirect(reverse("user_system:admin_page"))


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
    return HttpResponseRedirect(reverse("user_system:admin_page"))


def login(request):
    form = CustomAuthenticationForm(request, data=request.POST or None)
    error_message = None

    if request.method == "POST":
        if form.is_valid():
            request.session["login_attempts"] = 0  # Reset attempts on success
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, "Successfully logged in.")
            
            next_url = request.GET.get('next')
            if next_url:
                return HttpResponseRedirect(next_url)
            else:
                if user.is_superuser:
                    return HttpResponseRedirect(reverse("user_system:admin_page"))
                else:
                    return HttpResponseRedirect(reverse("task_manager:home"))
        else:
            # Increment login attempts
            request.session["login_attempts"] = (
                request.session.get("login_attempts", 0) + 1
            )
            error_message = "Invalid username or password."

            # If we just crossed the threshold, the current 'form' instance doesn't have the captcha field.
            # We need to add it so it renders for the user to fill in next time.
            if request.session["login_attempts"] >= 2 and "captcha" not in form.fields:
                from captcha.fields import CaptchaField

                form.fields["captcha"] = CaptchaField()
                form.fields["captcha"].widget.attrs.update(
                    {"class": "form-control", "placeholder": "Enter captcha"}
                )

            # If captcha error exists, update error message
            if "captcha" in form.errors:
                error_message = "Invalid CAPTCHA. Please try again."

    show_captcha = request.session.get("login_attempts", 0) >= 2

    return render(
        request,
        "login.html",
        {
            "form": form,
            "error_message": error_message,
            "show_captcha": show_captcha,
        },
    )


@consent_exempt
def informed_consent(request):
    latest_consent = InformedConsent.get_latest()

    # latest_consent is guaranteed to be an object (saved or unsaved)
    html_content = markdown.markdown(latest_consent.content)

    if request.method == "POST":
        if "agree" in request.POST:
            if not latest_consent.pk:
                # If it's an unsaved default object, save it now as the first version
                latest_consent.save()

            if request.user.is_authenticated:
                request.user.agreed_consent_version = latest_consent
                request.user.consent_agreed = True
                request.user.save()
                next_url = request.GET.get('next')
                if next_url:
                    return HttpResponseRedirect(next_url)
                return HttpResponseRedirect(reverse("task_manager:home"))
            else:
                request.session["consent_agreed"] = True
                return HttpResponseRedirect(reverse("user_system:signup"))
        else:
            if request.user.is_authenticated:
                auth_logout(request)
            return HttpResponseRedirect(reverse("user_system:login"))

    return render(
        request,
        "informed_consent.html",
        {
            "latest_consent": (
                latest_consent if latest_consent.pk else None
            ),  # Pass None if unsaved so template knows it's default
            "html_content": html_content,
        },
    )


def signup(request):
    if not request.session.get("consent_agreed"):
        return HttpResponseRedirect(reverse("user_system:informed_consent"))

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                email=form.cleaned_data["email"],
            )
            user.consent_agreed = True
            user.agreed_consent_version = InformedConsent.get_latest()
            user.save()

            profile = user.profile
            profile.name = form.cleaned_data["name"]
            profile.gender = form.cleaned_data["gender"]
            profile.age = form.cleaned_data["age"]
            profile.phone = form.cleaned_data["phone"]
            profile.occupation = form.cleaned_data["occupation"]
            profile.education = form.cleaned_data["education"]
            profile.field_of_expertise = form.cleaned_data["field_of_expertise"]
            profile.llm_frequency = form.cleaned_data["llm_frequency"]
            profile.llm_history = form.cleaned_data["llm_history"]
            profile.save()

            # Clean up the session
            request.session.pop("consent_agreed", None)

            return HttpResponseRedirect(reverse("user_system:login"))
        else:
            # Store form data and errors in session, then redirect
            request.session["signup_form_data"] = request.POST
            request.session["signup_form_errors"] = form.errors.as_json()
            return HttpResponseRedirect(reverse("user_system:signup"))
    else:
        # On GET, check for session data from a failed POST
        form_data = request.session.pop("signup_form_data", None)
        # Clear any lingering error session data, as it's not needed
        request.session.pop("signup_form_errors", None)

        if form_data:
            # Recreate the form with the user's data.
            # Validation errors will be regenerated when the template accesses them.
            form = SignupForm(form_data)
        else:
            # This is a fresh GET, create an empty form
            form = SignupForm()

    return render(request, "signup.html", {"form": form})


@consent_exempt
def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse("user_system:login"))


def health_check(request):
    return JsonResponse({"status": "ok"})


@login_required
def info(request):
    return render(
        request,
        "info.html",
        {
            "cur_user": request.user,
        },
    )


@login_required
@user_passes_test(is_superuser)
def view_user_info(request, user_id):
    user_info = get_object_or_404(User, id=user_id)
    return render(
        request,
        "view_user_info.html",
        {
            "user_info": user_info,
        },
    )


@login_required
def edit_info(request):
    if request.method == "POST":
        form = EditInfoForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            request.user.email = form.cleaned_data["email"]
            request.user.save()
            form.save()
            return HttpResponseRedirect(reverse("user_system:info"))
    else:
        form = EditInfoForm(
            instance=request.user.profile, initial={"email": request.user.email}
        )

    return render(
        request,
        "edit_info.html",
        {
            "cur_user": request.user,
            "form": form,
        },
    )


@login_required
def edit_password(request):
    form = EditPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        if request.user.check_password(form.cleaned_data["cur_password"]):
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            return HttpResponseRedirect(reverse("user_system:info"))
        else:
            error_message = "Incorrect current password."
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "edit_password.html",
        {
            "cur_user": request.user,
            "form": form,
            "error_message": error_message,
        },
    )


def forget_password(request):
    form = ForgetPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        try:
            user = User.objects.get(email=form.cleaned_data["email"])
            reset_request = ResetPasswordRequest.objects.create(user=user)
            # Assuming send_reset_password_email is a utility function you have defined
            # from .utils import send_reset_password_email
            send_reset_password_email(request.get_host(), reset_request)
            return HttpResponseRedirect(reverse("user_system:login"))
        except User.DoesNotExist:
            error_message = "Email address not found."
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "forget_password.html",
        {
            "form": form,
            "error_message": error_message,
        },
    )


def reset_password(request, token_str):
    token = get_object_or_404(ResetPasswordRequest, token=token_str)

    if token.is_expired:
        return render(
            request,
            "reset_password.html",
            {
                "form": None,
                "error_message": "This token has expired. Please request a new password reset.",
            },
        )

    form = ResetPasswordForm(request.POST or None)
    error_message = None

    if request.method == "POST" and form.is_valid():
        user = token.user
        user.set_password(form.cleaned_data["new_password"])
        user.save()
        token.delete()
        return HttpResponseRedirect(reverse("user_system:login"))
    elif request.method == "POST":
        error_message = form.errors

    return render(
        request,
        "reset_password.html",
        {
            "form": form,
            "error_message": error_message,
            "user": token.user,
        },
    )


@login_required
@user_passes_test(is_superuser)
def manage_extension_versions(request):
    if request.method == "POST":
        form = ExtensionVersionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New extension version added successfully.")
            return HttpResponseRedirect(
                reverse("user_system:manage_extension_versions")
            )
    else:
        form = ExtensionVersionForm()

    versions = ExtensionVersion.objects.all().order_by("-id")
    return render(
        request, "manage_extension_versions.html", {"form": form, "versions": versions}
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
    return HttpResponseRedirect(reverse("user_system:manage_extension_versions"))


class UserSearchView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        term = request.GET.get("term", "")
        User = get_user_model()
        users = (
            User.objects.filter(
                Q(username__icontains=term) | Q(profile__name__icontains=term)
            )
            .exclude(pk=request.user.pk)
            .select_related("profile")[:USER_SEARCH_RESULT_LIMIT]
        )

        results = []
        for user in users:
            # Use default static image if icon is not set
            image_url = (
                user.profile.icon.url
                if user.profile.icon
                else static("img/default.jpg")
            )

            results.append(
                {
                    "id": user.id,
                    "label": user.username,  # Keep for accessibility
                    "value": user.username,
                    "name": user.profile.name or user.username,
                    "username": user.username,
                    "image_url": image_url,
                }
            )
        return JsonResponse(results, safe=False)


def check_web_session(request):
    if request.user.is_authenticated:
        return JsonResponse(
            {"status": "authenticated", "username": request.user.username}
        )
    else:
        return JsonResponse({"status": "anonymous"})
