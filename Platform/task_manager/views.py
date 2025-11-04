#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
import base64
import uuid
import json

from .utils import (
    print_debug,
    stop_annotating,
    decompress_json_data,
    store_data,
    close_window,
    get_active_task_dataset,
    start_annotating,
    wait_until_data_stored,
    check_answer,
    get_pending_annotation,
    start_storing_data,
)
from .models import (
    Task,
    TaskDatasetEntry,
    PreTaskAnnotation,
    PostTaskAnnotation,
    CancelAnnotation,
    Webpage,
    TaskTrial,
    ReflectionAnnotation,
    Justification,
)
from .mappings import *
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import (
    csrf_exempt,
    ensure_csrf_cookie,
)  # Add ensure_csrf_cookie here
from django.urls import reverse

try:
    import simplejson as json
except ImportError:
    import json
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.contrib.auth import login

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stop_annotation_api(request):
    """
    A special API endpoint to stop the current annotation process.
    """
    user = request.user
    annotation_id = request.data.get("annotation_id")
    print_debug(f"Received stop annotation signal for user {user.username} with ID {annotation_id}.")
    if stop_annotating(request, annotation_id):
        return JsonResponse({"status": "success", "message": "Annotation stopped."}, status=200)
    else:
        return JsonResponse({"status": "error", "message": "Annotation ID mismatch or not found."}, status=400)


# Redirect after authentication
@ensure_csrf_cookie
def auth_redirect(request):
    """
    Authenticates a user via a JWT token from a query parameter,
    logs them into a standard Django session, and redirects them to a specified page.

    Expected query parameters:
    - token: The JWT access token.
    - next: The URL path to redirect to after successful authentication.
    """
    token_str = request.GET.get("token")
    redirect_path = request.GET.get(
        "next", "/"
    )  # Default to home if 'next' is not provided

    if not token_str:
        return HttpResponse("Authentication token not provided.", status=400)

    try:
        # 1. Decode the token to validate it and get the user
        access_token = AccessToken(token_str)
        user_id = access_token["user_id"]
        User = get_user_model()
        user = User.objects.get(id=user_id)

        # 2. Log the user into a Django session
        # This will set the session cookie in the user's browser
        if user.is_active:
            user.backend = 'django.contrib.auth.backends.ModelBackend'  # Explicitly set backend
            login(request, user)
            # 3. Redirect to the intended page
            response = HttpResponseRedirect(redirect_path)
            return response
        else:
            return HttpResponse("User account is disabled.", status=403)

    except (InvalidToken, TokenError, User.DoesNotExist):
        # Handle cases where the token is invalid, expired, or the user doesn't exist
        return HttpResponse("Invalid or expired authentication token.", status=401)


# Store data
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def data(request):
    start_storing_data(request)
    print_debug("function data")
    message = request.POST["message"]
    # decompress the message if it is compressed
    message = decompress_json_data(message)
    user = request.user
    store_data(request, message, user)
    return JsonResponse({"status": "success"})


# Pre-Task Annotation Fetcher
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pre_task_annotation(request):
    print_debug("function pre_task_annotation")
    user = request.user

    pending_annotation_url = get_pending_annotation(user)
    if pending_annotation_url:
        return HttpResponseRedirect(pending_annotation_url)

    if request.method == "POST":
        # Start a new task
        print_debug("start_task")
        task = Task()
        task.user = user
        task.active = True
        entry_id = int(request.POST.get("entry_id"))
        entry = TaskDatasetEntry.objects.filter(id=entry_id).first()
        if entry is None:
            context = {
                'title': 'Not Found',
                'message': f"No entry found with entry_id={entry_id}",
                'alert_type': 'danger',
            }
            return render(request, "status_page.html", context)
        entry.num_associated_tasks += 1
        task.content = entry
        entry.save()
        task.save()

        pre_annotation = PreTaskAnnotation()
        pre_annotation.belong_task = task
        pre_annotation.familiarity = request.POST.get("familiarity")
        pre_annotation.difficulty = request.POST.get("difficulty")
        pre_annotation.effort = request.POST.get("effort")
        pre_annotation.first_search_query = request.POST.get("first_search_query")
        pre_annotation.initial_guess = request.POST.get("initial_guess")
        pre_annotation.initial_guess_unknown = request.POST.get("initial_guess_unknown") == "on"
        pre_annotation.expected_source = request.POST.getlist("expected_source")
        pre_annotation.expected_source_other = request.POST.get("expected_source_other")
        pre_annotation.save()

        stop_annotating(request)

        return close_window()

    else:
        if Task.objects.filter(user=user, active=True).exists():
            context = {
                'title': 'Ongoing Task!',
                'message': 'You already have an active task. Please complete or cancel it before starting a new one.',
                'alert_type': 'warning',
            }
            return render(request, "status_page.html", context)

        # Randomly choose a task from the dataset
        dataset = get_active_task_dataset()
        if dataset is None:
            context = {
                'title': 'Not Found',
                'message': 'No active dataset found.',
                'alert_type': 'danger',
            }
            return render(request, "status_page.html", context)
        entry = (
            TaskDatasetEntry.objects.filter(belong_dataset=dataset)
            .order_by("num_associated_tasks")
            .first()
        )
        if entry is None:
            context = {
                'title': 'Not Found',
                'message': f"No entry found in dataset id={dataset.id}",
                'alert_type': 'danger',
            }
            return render(request, "status_page.html", context)
        print_debug(f"[Question] {entry.question}")
        print_debug(f"[Answer] {entry.answer}")

        annotation_id = start_annotating(request, "pre_task_annotation")
        return render(
            request,
            "pre_task_annotation.html",
            {
                "cur_user": user,
                "question": entry.question,
                "entry_id": entry.id,
                "annotation_id": annotation_id,
                "FAMILIARITY_MAP": FAMILIARITY_MAP,
                "DIFFICULTY_MAP": DIFFICULTY_MAP,
                "EFFORT_MAP": EFFORT_MAP,
                "FAMILIARITY_EXPLANATION_MAP": FAMILIARITY_EXPLANATION_MAP,
                "DIFFICULTY_EXPLANATION_MAP": DIFFICULTY_EXPLANATION_MAP,
                "EFFORT_EXPLANATION_MAP": EFFORT_EXPLANATION_MAP,
                "EXPECTED_SOURCES_MAP": EXPECTED_SOURCES_MAP,
            },
        )


# Post-Task Annotation Fetcher
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@wait_until_data_stored
def post_task_annotation(request, task_id):
    print_debug("function post_task_annotation")
    user = request.user
    if request.method == "POST":
        # End a task
        print_debug("end_task")
        task = Task.objects.filter(id=task_id, user=user).first()
        if task is not None:
            # Check if an annotation already exists to prevent duplicates
            if PostTaskAnnotation.objects.filter(belong_task=task).exists():
                print_debug(f"PostTaskAnnotation for task {task_id} already exists.")
                stop_annotating(request)
                return close_window()

            post_annotation = PostTaskAnnotation()
            post_annotation.difficulty_actual = request.POST.get("difficulty_actual")
            post_annotation.aha_moment_type = request.POST.get("aha_moment_type")
            post_annotation.aha_moment_other = request.POST.get("aha_moment_other")
            post_annotation.unhelpful_paths = request.POST.getlist("unhelpful_paths")
            post_annotation.unhelpful_paths_other = request.POST.get("unhelpful_paths_other")
            post_annotation.strategy_shift = request.POST.getlist("strategy_shift")
            post_annotation.strategy_shift_other = request.POST.get("strategy_shift_other")
            post_annotation.belong_task = task
            post_annotation.save()

            stop_annotating(request)
            return close_window()
        else:
            stop_annotating(request)
            return HttpResponse("Task not found", status=404)

    else:
        # Fetch task and relevant webpages
        task = Task.objects.filter(id=task_id, user=user).first()
        if task is None:
            context = {
                'title': 'Task Not Found',
                'message': f"No task found with task_id={task_id}",
                'alert_type': 'danger',
            }
            return render(request, "status_page.html", context)

        if task.cancelled:
            context = {
                'title': 'Task Cancelled',
                'message': 'This task has been cancelled and can no longer be annotated.',
                'alert_type': 'warning',
            }
            return render(request, "status_page.html", context)

        # Check if annotation already exists
        if PostTaskAnnotation.objects.filter(belong_task=task).exists():
            context = {
                'title': 'Annotation Already Completed!',
                'message': 'You have already submitted the annotation for this task.',
                'alert_type': 'success',
            }
            return render(request, "status_page.html", context)

        latest_trial = TaskTrial.objects.filter(belong_task=task).order_by('-num_trial').first()
        if not latest_trial or latest_trial.is_correct is not True:
            context = {
                'title': 'Annotation Not Ready!',
                'message': 'This annotation cannot be completed yet. Please complete the previous steps of the task first.',
                'alert_type': 'warning',
            }
            return render(request, "status_page.html", context)

        # Deactivate the task as soon as the user lands on the page
        if task.active:
            task.active = False
            task.save()

        # Fetch trials and their relevant webpages
        trials = TaskTrial.objects.filter(belong_task=task).order_by('num_trial')
        for trial in trials:
            trial.webpages = Webpage.objects.filter(
                belong_task_trial=trial, is_redirected=False, during_annotation=False
            ).order_by('start_timestamp')

        question = task.content.question
        answer = json.loads(task.content.answer)
        print_debug(answer)

        # Get the user's answer from the latest trial
        latest_trial = TaskTrial.objects.filter(belong_task=task).order_by('-num_trial').first()
        user_answer = latest_trial.answer if latest_trial else ""

        annotation_id = start_annotating(request, "post_task_annotation")
        return render(
            request,
            "post_task_annotation.html",
            {
                "cur_user": user,
                "task_id": task.id,
                "trials": trials,
                "question": question,
                "answer": answer,
                "user_answer": user_answer,
                "annotation_id": annotation_id,
                "DIFFICULTY_MAP": DIFFICULTY_MAP,
                "AHA_MOMENT_MAP": AHA_MOMENT_MAP,
                "UNHELPFUL_PATHS_MAP": UNHELPFUL_PATHS_MAP,
                "STRATEGY_SHIFT_MAP": STRATEGY_SHIFT_MAP,
                "DIFFICULTY_EXPLANATION_MAP": DIFFICULTY_EXPLANATION_MAP,
                "AHA_MOMENT_EXPLANATION_MAP": AHA_MOMENT_EXPLANATION_MAP,
                "UNHELPFUL_PATHS_EXPLANATION_MAP": UNHELPFUL_PATHS_EXPLANATION_MAP,
                "STRATEGY_SHIFT_EXPLANATION_MAP": STRATEGY_SHIFT_EXPLANATION_MAP,
            },
        )


# Return active tasks
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def active_task(request):
    # Return active tasks
    print_debug("active_task")
    user = request.user
    task = Task.objects.filter(user=user, active=True).first()
    if task is None:
        return JsonResponse({"task_id": -1})

    task_id = task.id
    print_debug("Current Task ID: ", task_id)
    return JsonResponse({"task_id": task_id})


# Initialize the task
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize(request):
    print_debug("initialize")

    user = request.user
    # Delete all active tasks and relevant queries and pages
    tasks = Task.objects.filter(user=user, active=True)
    # for task in tasks:
    #     task.delete()

    # TODO: Let users choose to continue the previous task or start a new task
    if tasks.first() is not None:
        return HttpResponse(tasks.first().id)
    return HttpResponse(-1)

@login_required
@permission_classes([IsAuthenticated])
@wait_until_data_stored
def task_home(request):
    print_debug("function task_home")
    user = request.user
    completed_num = len(Task.objects.filter(user=user, active=False))
    pending_num = len(Task.objects.filter(user=user, active=True))
    pending_annotation_url = get_pending_annotation(user)
    return render(
        request,
        "task_home.html",
        {
            "cur_user": user,
            "completed_num": completed_num,
            "pending_num": pending_num,
            "pending_annotation_url": pending_annotation_url,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def annotation_home(request):
    print_debug("function annotation_home")

    user = request.user
    annotated_tasks = sorted(
        Task.objects.filter(user=user, active=False), key=lambda task: -task.id
    )
    unannotated_tasks = sorted(
        Task.objects.filter(user=user, active=True), key=lambda task: -task.id
    )
    annotated_tasks_to_webpages = []
    unannotated_tasks_to_webpages = []
    for task in unannotated_tasks:
        # end_timestamp = task.end_timestamp
        # Convert to human-readable time
        # end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
        unannotated_tasks_to_webpages.append(
            (
                task.id,
                sorted(
                    Webpage.objects.filter(
                        user=user,
                        belong_task=task,
                        is_redirected=False,
                        during_annotation=False,
                    ),
                    key=lambda item: item.start_timestamp,
                ),
            )
        )
    for task in annotated_tasks:
        # end_timestamp = task.end_timestamp
        # Convert to human-readable time
        # end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
        annotated_tasks_to_webpages.append(
            (
                task.id,
                sorted(
                    Webpage.objects.filter(
                        user=user,
                        belong_task=task,
                        is_redirected=False,
                        during_annotation=False,
                    ),
                    key=lambda item: item.start_timestamp,
                ),
            )
        )

    pending_annotation_url = get_pending_annotation(user)
    return render(
        request,
        "annotation_home.html",
        {
            "cur_user": user,
            "unannotated_tasks_to_webpages": unannotated_tasks_to_webpages,
            "annotated_tasks_to_webpages": annotated_tasks_to_webpages,
            "pending_annotation_url": pending_annotation_url,
        },
    )

# Helper function to map lists of keys to lists of values
def map_json_list(json_string, mapping):
    try:
        keys = json.loads(json_string) if json_string else []
        return [mapping.get(key, key) for key in keys]
    except (json.JSONDecodeError, TypeError):
        return []


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_task_info(request):
    print_debug("function get_task_info")
    user = request.user
    task_id = request.query_params.get("task_id")
    task = Task.objects.filter(id=task_id, user=user, active=True).first()
    if task is None:
        return HttpResponse(f"No task found with task_id={task_id}", status=404)

    question = task.content.question
    trial_num = task.num_trial
    return JsonResponse({"question": question, "trial_num": trial_num})


# =============================================
# =        Updated show_task Function         =
# =============================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@wait_until_data_stored
def show_task(request, task_id):
    """
    Fetches all data related to a specific task and renders it in a detail view.
    This function gathers the pre-task survey, all trials with their respective
    webpages, submitted answers, reflections, and the post-task or cancellation survey.
    Allows access to the task owner or any superuser.
    """
    print_debug(f"function show_task for task_id: {task_id}")
    user = request.user
    
    # Fetch the task by ID.
    task = Task.objects.filter(id=task_id).first()

    # Check if the task exists and if the user has permission to view it.
    if task is None or (task.user != user and not user.is_superuser):
        context = {
            'title': 'Access Denied',
            'message': f"No task found with task_id={task_id} or you do not have permission to view it.",
            'alert_type': 'danger',
        }
        return render(request, "status_page.html", context)

    # 1. Fetch general task information
    task_question = task.content.question
    task_answer = json.loads(task.content.answer) if task.content.answer else {}

    # 2. Fetch Pre-Task Annotation
    pre_task_annotation = PreTaskAnnotation.objects.filter(belong_task=task).first()

    # 3. Fetch all trials and related data
    task_trials = TaskTrial.objects.filter(belong_task=task).order_by("num_trial")
    for trial in task_trials:
        trial.webpages = Webpage.objects.filter(
            belong_task_trial=trial, is_redirected=False, during_annotation=False
        ).order_by("start_timestamp")
        trial.submitted_sources = trial.justifications.all()
        if hasattr(trial, 'reflectionannotation') and trial.reflectionannotation:
            if isinstance(trial.reflectionannotation.failure_category, str):
                try:
                    trial.reflectionannotation.failure_category = json.loads(trial.reflectionannotation.failure_category)
                except json.JSONDecodeError:
                    trial.reflectionannotation.failure_category = []
            if isinstance(trial.reflectionannotation.future_plan_actions, str):
                try:
                    trial.reflectionannotation.future_plan_actions = json.loads(trial.reflectionannotation.future_plan_actions)
                except json.JSONDecodeError:
                    trial.reflectionannotation.future_plan_actions = []

    # 4. Fetch Post-Task or Cancellation Annotation
    post_task_annotation = None
    cancel_annotation = None
    if task.cancelled:
        cancel_annotation = CancelAnnotation.objects.filter(belong_task=task).first()
    else:
        post_task_annotation = PostTaskAnnotation.objects.filter(belong_task=task).first()

    cancel_missing_resources = []
    cancel_categories = []
    if cancel_annotation:
        cancel_missing_resources = map_json_list(
            cancel_annotation.missing_resources, MISSING_RESOURCES_MAP
        )
        if cancel_annotation.category:
            # Ensure category is treated as a JSON string for map_json_list
            category_json = json.dumps(cancel_annotation.category)
            cancel_categories = map_json_list(category_json, CANCEL_CATEGORY_MAP)

    # 5. Assemble the final context and render the template
    context = {
        "cur_user": user,
        "task_id": task.id,
        "task_question": task_question,
        "task_answer": task_answer,
        "pre_task_annotation": pre_task_annotation,
        "trials": task_trials,
        "post_task_annotation": post_task_annotation,
        "cancel_annotation": cancel_annotation,
        "cancel_categories": cancel_categories,
        "cancel_missing_resources": cancel_missing_resources,
        "task": task,
        "FAMILIARITY_MAP": FAMILIARITY_MAP,
        "DIFFICULTY_MAP": DIFFICULTY_MAP,
        "EFFORT_MAP": EFFORT_MAP,
        "CONFIDENCE_MAP": CONFIDENCE_MAP,
        "ANSWER_FORMULATION_MAP": ANSWER_FORMULATION_MAP,
        "FAILURE_CATEGORY_MAP": FAILURE_CATEGORY_MAP,
        "CORRECTIVE_PLAN_MAP": CORRECTIVE_PLAN_MAP,
        "AHA_MOMENT_MAP": AHA_MOMENT_MAP,
        "UNHELPFUL_PATHS_MAP": UNHELPFUL_PATHS_MAP,
        "STRATEGY_SHIFT_MAP": STRATEGY_SHIFT_MAP,
        "CANCEL_CATEGORY_MAP": CANCEL_CATEGORY_MAP,
        "MISSING_RESOURCES_MAP": MISSING_RESOURCES_MAP,
        "EXPECTED_SOURCES_MAP": EXPECTED_SOURCES_MAP,
    }
    return render(request, "show_task.html", context)


@permission_classes([IsAuthenticated])
def show_tool_use_page(request):
    print_debug("function show_tool_use_page")
    user = request.user
    return render(
        request,
        "show_tool_use_page.html",
        {
            "cur_user": user,
        },
    )


@permission_classes([IsAuthenticated])
def tool_use(request):
    print_debug("function tool_use")
    if request.method == "POST":
        print_debug("tool_use")

        tool = request.POST["tool"]

        for_url = ""

        if tool == "math":
            for_url = "https://www.wolframalpha.com/"

        elif tool == "graph":
            for_url = "https://www.geogebra.org/classic"

        elif tool == "code":
            for_url = "https://www.jdoodle.com/start-coding"

        return HttpResponseRedirect(for_url)


@permission_classes([IsAuthenticated])
@wait_until_data_stored
def cancel_annotation(request, task_id):
    print_debug("function cancel_annotation")
    user = request.user
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        context = {
            'title': 'Task Not Found',
            'message': f"No task found with task_id={task_id}",
            'alert_type': 'danger',
        }
        return render(request, "status_page.html", context)

    if request.method == "POST":
        if CancelAnnotation.objects.filter(belong_task=task).exists():
            print_debug(f"CancelAnnotation for task {task_id} already exists.")
            stop_annotating(request)
            return close_window()

        task.cancelled = True
        task.active = False
        task.save()
        cancel_annotation = CancelAnnotation()
        cancel_annotation.belong_task = task
        cancel_annotation.category = request.POST.getlist("cancel_category")
        cancel_annotation.reason = request.POST.get("cancel_reason")
        cancel_annotation.missing_resources = request.POST.get(
            "cancel_missing_resources_list"
        )
        cancel_annotation.missing_resources_other = request.POST.get(
            "cancel_missing_resources_other"
        )
        cancel_annotation.save()
        stop_annotating(request)
        return close_window()

    else:
        if CancelAnnotation.objects.filter(belong_task=task).exists():
            context = {
                'title': 'Annotation Already Completed!',
                'message': 'You have already submitted the annotation for this task.',
                'alert_type': 'success',
            }
            return render(request, "status_page.html", context)

        task.end_timestamp = timezone.now()
        # NOTICE: Give user change to reconsider cancellation
        # So only after the form is submitted, the task is marked as cancelled  

        entry = task.content
        question = entry.question
        answer = json.loads(entry.answer)

        # Fetch completed trials and their webpages
        trials = list(TaskTrial.objects.filter(belong_task=task).order_by('num_trial'))
        for trial in trials:
            trial.webpages = Webpage.objects.filter(
                belong_task_trial=trial, is_redirected=False, during_annotation=False
            ).order_by('start_timestamp')

        # Fetch webpages for the current (uncompleted) trial
        current_webpages = Webpage.objects.filter(
            belong_task=task,
            belong_task_trial__isnull=True,
            is_redirected=False,
            during_annotation=False
        ).order_by('start_timestamp')

        # If there are webpages for the current trial, associate them with the correct trial object
        if current_webpages.exists():
            current_trial_num = task.num_trial + 1
            # Check if a placeholder trial already exists
            current_trial_obj = next((t for t in trials if t.num_trial == current_trial_num), None)

            if current_trial_obj:
                # Add webpages to the existing placeholder trial
                # Ensure webpages are combined and sorted if necessary
                existing_webpages = list(current_trial_obj.webpages)
                new_webpages = list(current_webpages)
                all_webpages = sorted(existing_webpages + new_webpages, key=lambda w: w.start_timestamp)
                current_trial_obj.webpages = all_webpages
            else:
                # Create a new pseudo-trial object if no placeholder exists
                from types import SimpleNamespace
                current_trial = SimpleNamespace(
                    num_trial=current_trial_num,
                    webpages=current_webpages
                )
                trials.append(current_trial)

        annotation_id = start_annotating(request, "cancel_annotation")
        return render(
            request,
            "cancel_annotation.html",
            {
                "cur_user": user,
                "task_id": task_id,
                "question": question,
                "answer": answer,
                "trials": trials,
                "annotation_id": annotation_id,
                "CANCEL_CATEGORY_MAP": CANCEL_CATEGORY_MAP,
                "MISSING_RESOURCES_MAP": MISSING_RESOURCES_MAP,
                "CANCEL_CATEGORY_EXPLANATION_MAP": CANCEL_CATEGORY_EXPLANATION_MAP,
                "MISSING_RESOURCES_EXPLANATION_MAP": MISSING_RESOURCES_EXPLANATION_MAP,
            },
        )


@permission_classes([IsAuthenticated])
@wait_until_data_stored
def reflection_annotation(request, task_trial_id):
    print_debug("function reflection_annotation")
    user = request.user
    task_trial = TaskTrial.objects.filter(id=task_trial_id).first()
    if task_trial is None:
        context = {
            'title': 'Not Found',
            'message': f"No trial found with id={task_trial_id}",
            'alert_type': 'danger',
        }
        return render(request, "status_page.html", context)

    task = task_trial.belong_task
    if task.user != user and not user.is_superuser:
        context = {
            'title': 'Access Denied',
            'message': 'You do not have permission to view this page.',
            'alert_type': 'danger',
        }
        return render(request, "status_page.html", context)

    if task_trial.is_correct is not False:
        context = {
            'title': 'Annotation Not Ready!',
            'message': 'This annotation cannot be completed yet. Please complete the previous steps of the task first.',
            'alert_type': 'warning',
        }
        return render(request, "status_page.html", context)

    entry = task.content
    question = entry.question

    if request.method == "POST":
        if ReflectionAnnotation.objects.filter(belong_task_trial=task_trial).exists():
            print_debug(f"ReflectionAnnotation for trial {task_trial.id} already exists.")
            stop_annotating(request)
            return close_window()

        ref_annotation = ReflectionAnnotation(
            belong_task_trial=task_trial,
            failure_category=request.POST.get("failure_category_list"),
            failure_category_other=request.POST.get("failure_category_other"),
            future_plan_actions=request.POST.get("future_plan_actions_list"),
            future_plan_other=request.POST.get("future_plan_other"),
            estimated_time=request.POST.get("estimated_time"),
            adjusted_difficulty=request.POST.get("adjusted_difficulty"),
        )
        ref_annotation.save()

        stop_annotating(request)

        return close_window()

    else:
        if ReflectionAnnotation.objects.filter(belong_task_trial=task_trial).exists():
            context = {
                'title': 'Annotation Already Completed!',
                'message': 'You have already submitted the annotation for this task.',
                'alert_type': 'success',
            }
            return render(request, "status_page.html", context)

        # Filter the webpage whose timestamp is within the range of start_timestamp and timestamp
        end_datetime = task_trial.end_timestamp
        webpages = Webpage.objects.filter(
            belong_task_trial=task_trial,
            is_redirected=False,
            during_annotation=False,
        )
        # Sort by start_timestamp
        webpages = sorted(webpages, key=lambda item: item.start_timestamp)

        # User answer
        user_answer = task_trial.answer if task_trial.answer else ""

        annotation_id = start_annotating(request, "reflection_annotation")
        return render(
            request,
            "reflection_annotation.html",
            {
                "cur_user": user,
                "task_id": task.id,
                "question": question,
                "webpages": webpages,
                "user_answer": user_answer,
                "annotation_id": annotation_id,
                "FAILURE_CATEGORY_MAP": FAILURE_CATEGORY_MAP,
                "CORRECTIVE_PLAN_MAP": CORRECTIVE_PLAN_MAP,
                "DIFFICULTY_MAP": DIFFICULTY_MAP,
                "EFFORT_MAP": EFFORT_MAP,
                "EFFORT_EXPLANATION_MAP": EFFORT_EXPLANATION_MAP,
                "DIFFICULTY_EXPLANATION_MAP": DIFFICULTY_EXPLANATION_MAP,
                "FAILURE_CATEGORY_EXPLANATION_MAP": FAILURE_CATEGORY_EXPLANATION_MAP,
                "CORRECTIVE_ACTION_EXPLANATION_MAP": CORRECTIVE_ACTION_EXPLANATION_MAP,
            },
        )


@permission_classes([IsAuthenticated])
@wait_until_data_stored
def submit_answer(request, task_id):
    print_debug("function submit_answer")
    user = request.user

    pending_annotation_url = get_pending_annotation(user)
    if pending_annotation_url:
        return HttpResponseRedirect(pending_annotation_url)

    if request.method == "POST":
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(id=task_id, user=user)
                if task.cancelled:
                    context = {
                        'title': 'Task Cancelled',
                        'message': 'This task has been cancelled and no new answers can be submitted.',
                        'alert_type': 'warning',
                    }
                    return render(request, "status_page.html", context)
            except Task.DoesNotExist:
                context = {
                    'title': 'Task Not Found',
                    'message': f"No task found with task_id={task_id}",
                    'alert_type': 'danger',
                }
                return render(request, "status_page.html", context)

            start_timestamp = task.start_timestamp
            num_trial = task.num_trial
            if num_trial > 0:
                last_task_trial = TaskTrial.objects.filter(
                    belong_task=task, num_trial=num_trial
                ).first()
                if last_task_trial:
                    start_timestamp = last_task_trial.end_timestamp

            answer = request.POST.get("answer")
            answer = answer if answer else ""
            
            confidence = request.POST.get("confidence")
            answer_formulation_method = request.POST.get("answer_formulation_method")

            current_trial_num = task.num_trial + 1

            task_trial, created = TaskTrial.objects.get_or_create(
                belong_task=task,
                num_trial=current_trial_num,
            )

            task_trial.answer = answer
            task_trial.start_timestamp = start_timestamp
            task_trial.end_timestamp = timezone.now()
            task_trial.confidence = confidence
            task_trial.answer_formulation_method = answer_formulation_method

            is_correct = check_answer(task.content, task_trial.answer)
            task_trial.is_correct = is_correct

            if is_correct:
                task.end_timestamp = timezone.now()

            task_trial.save()

            task.num_trial = current_trial_num
            task.save()

            end_datetime = timezone.now()
            all_webpages = Webpage.objects.filter(
                belong_task=task, start_timestamp__gte=start_timestamp
            )

            for key, value in request.POST.items():
                if key.startswith('relevance_'):
                    justification_id = key.split('_')[1]
                    try:
                        justification = Justification.objects.get(id=justification_id)
                        if justification.belong_task_trial.belong_task.user == user:
                            justification.relevance = int(value)
                            justification.save()
                    except (Justification.DoesNotExist, ValueError):
                        pass
                elif key.startswith('credibility_'):
                    justification_id = key.split('_')[1]
                    try:
                        justification = Justification.objects.get(id=justification_id)
                        if justification.belong_task_trial.belong_task.user == user:
                            justification.credibility = int(value)
                            justification.save()
                    except (Justification.DoesNotExist, ValueError):
                        pass

            if is_correct:
                if PostTaskAnnotation.objects.filter(belong_task=task).exists():
                    redirect_url = reverse("task_manager:status_page") + "?title=Annotation+Already+Completed%21&message=You+have+already+submitted+the+annotation+for+this+task.&alert_type=success"
                else:
                    redirect_url = reverse("task_manager:post_task_annotation", args=[task_id])
            else:
                if ReflectionAnnotation.objects.filter(belong_task_trial=task_trial).exists():
                    redirect_url = reverse("task_manager:status_page") + "?title=Annotation+Already+Completed%21&message=You+have+already+submitted+the+annotation+for+this+task.&alert_type=success"
                else:
                    redirect_url = reverse(
                        "task_manager:reflection_annotation", args=[task_trial.id]
                    )

            for webpage in all_webpages:
                webpage.belong_task_trial = task_trial
                webpage.save()
            stop_annotating(request)

            return HttpResponseRedirect(redirect_url)
    else:
        task = Task.objects.filter(id=task_id, user=user).first()
        if task is None:
            context = {
                'title': 'Task Not Found',
                'message': f"No task found with task_id={task_id}",
                'alert_type': 'danger',
            }
            return render(request, "status_page.html", context)
        
        if task.cancelled:
            context = {
                'title': 'Task Cancelled',
                'message': 'This task has been cancelled and can no longer be annotated.',
                'alert_type': 'warning',
            }
            return render(request, "status_page.html", context)
        
        question = task.content.question
        start_timestamp = task.start_timestamp
        num_trial = task.num_trial
        if num_trial > 0:
            last_task_trial = TaskTrial.objects.filter(
                belong_task=task, num_trial=num_trial
            ).first()
            if last_task_trial:
                start_timestamp = last_task_trial.end_timestamp

        webpages = Webpage.objects.filter(
            belong_task=task,
            belong_task_trial__isnull=True,
            is_redirected=False,
            during_annotation=False
        ).order_by('start_timestamp')

        annotation_id = start_annotating(request, "submit_answer")
        return render(
            request,
            "submit_answer.html",
            {
                "cur_user": user,
                "task_id": task_id,
                "question": question,
                "webpages": webpages,
                "num_trial": num_trial + 1,
                "annotation_id": annotation_id,
                "confidence_choices": CONFIDENCE_MAP.items(),
                "answer_formulation_choices": ANSWER_FORMULATION_MAP.items(),
            },
        )



@permission_classes([IsAuthenticated])
def remove_task(request, task_id):
    print_debug("function remove_task")
    user = request.user
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f"No task found with task_id={task_id}")
    task.delete()
    return HttpResponse("Task removed successfully")


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_justification(request):
    """
    Adds a justification for a given task.
    """
    user = request.user
    data = request.data
    task_id = data.get("task_id")
    url = data.get("url")
    page_title = data.get("page_title")
    text = data.get("text")
    dom_position = data.get("dom_position")
    evidence_type = data.get("evidence_type", "text_selection")
    element_details = data.get("element_details")

    # Input validation
    if not all([task_id, url]):
        return JsonResponse({"status": "error", "message": "Missing required fields."}, status=400)

    if page_title and len(page_title) > 255:
        return JsonResponse({"status": "error", "message": "Page title is too long."}, status=400)

    if text and len(text) > 10000:
        return JsonResponse({"status": "error", "message": "Text is too long."}, status=400)

    if dom_position and len(dom_position) > 1000:
        return JsonResponse({"status": "error", "message": "DOM position is too long."}, status=400)

    try:
        with transaction.atomic():
            task = Task.objects.select_for_update().get(id=task_id, user=user, active=True)

            # The trial being annotated is always the next one after the last completed trial.
            trial_num_to_get = task.num_trial + 1

            # Get or create a placeholder trial for this attempt.
            trial, created = TaskTrial.objects.get_or_create(
                belong_task=task,
                num_trial=trial_num_to_get,
            )

            justification = Justification.objects.create(
                belong_task_trial=trial,
                url=url,
                page_title=page_title,
                text=text,
                dom_position=dom_position,
                evidence_type=evidence_type,
                element_details=element_details
            )

            if element_details:
                image_data = element_details.get('attributes', {}).get('imageData')
                if image_data:
                    try:
                        format, imgstr = image_data.split(';base64,')
                        ext = format.split('/')[-1]
                        filename = f"{uuid.uuid4()}.{ext}"
                        data = ContentFile(base64.b64decode(imgstr), name=filename)
                        justification.evidence_image.save(filename, data, save=True)
                    except Exception as e:
                        logger.error(f"Could not save image evidence: {e}")

        return JsonResponse({"status": "success"})
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Active task not found."}, status=404)
    except Exception as e:
        logger.error(f"Error adding justification: {e}")
        return JsonResponse({"status": "error", "message": "An internal error occurred."}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_justification_status(request, justification_id):
    """
    Updates the status of a justification.
    """
    user = request.user
    try:
        justification = Justification.objects.get(id=justification_id)
        # Check if the user has permission to update this justification
        if justification.belong_task_trial.belong_task.user != user:
            return JsonResponse({"status": "error", "message": "Permission denied."}, status=403)

        new_status = request.data.get("status")
        if new_status in ['active', 'abandoned']:
            justification.status = new_status
            justification.save()
            return JsonResponse({"status": "success", "new_status": new_status})
        else:
            return JsonResponse({"status": "error", "message": "Invalid status."}, status=400)
    except Justification.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Justification not found."}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_justifications(request, task_id):
    """
    Retrieves all justifications for the current trial of a given task.
    """
    user = request.user
    task = Task.objects.filter(id=task_id, user=user).first()
    if not task:
        return JsonResponse({"status": "error", "message": "Active task not found."}, status=404)

    trial_num_to_get = task.num_trial + 1
    trial = TaskTrial.objects.filter(belong_task=task, num_trial=trial_num_to_get).first()

    if not trial:
        return JsonResponse({"status": "success", "justifications": [], "trial_num": trial_num_to_get})

    justifications = Justification.objects.filter(belong_task_trial=trial)
    justifications_data = []
    for j in justifications:
        justifications_data.append({
            'id': j.id,
            'url': j.url,
            'page_title': j.page_title,
            'text': j.text,
            'status': j.status,
            'evidence_type': j.evidence_type,
            'element_details': j.element_details,
            'relevance': j.relevance,
            'credibility': j.credibility,
            'evidence_image_url': j.evidence_image.url if j.evidence_image else None,
        })
    return JsonResponse({"status": "success", "justifications": justifications_data, "trial_num": trial.num_trial})

def status_page(request):
    title = request.GET.get('title', 'Notice')
    message = request.GET.get('message', 'Something happened.')
    alert_type = request.GET.get('alert_type', 'info')
    context = {
        'title': title,
        'message': message,
        'alert_type': alert_type,
    }
    return render(request, "status_page.html", context)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_rrweb_record(request, webpage_id):
    """
    API endpoint to fetch the rrweb_record for a specific webpage.
    """
    user = request.user
    try:
        # Using select_related for efficiency
        webpage = Webpage.objects.select_related('belong_task__user').get(id=webpage_id)
        task_user = webpage.belong_task.user
        
        # Security check: ensure the user owns the task or is a superuser
        if task_user != user and not user.is_superuser:
            return JsonResponse({"status": "error", "message": "Permission denied."}, status=403)
            
        # The rrweb_record might be stored as a JSON string within the JSONField.
        # We need to parse it to ensure JsonResponse sends a proper JSON array.
        record_data = webpage.rrweb_record
        if isinstance(record_data, str):
            record_data = json.loads(record_data)

        return JsonResponse(record_data, safe=False)
    except Webpage.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Webpage not found."}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Failed to parse recording data."}, status=500)
    except Exception as e:
        logger.error(f"Error fetching rrweb record for webpage {webpage_id}: {e}")
        return JsonResponse({"status": "error", "message": "An internal error occurred."}, status=500)
