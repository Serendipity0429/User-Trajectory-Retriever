#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from django.utils import timezone

from django.shortcuts import render

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
)
from .models import (
    Task,
    TaskDatasetEntry,
    PreTaskAnnotation,
    PostTaskAnnotation,
    Webpage,
    TaskTrial,
    ReflectionAnnotation,
)
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


@csrf_exempt
def stop_annotation_api(request):
    """
    A special API endpoint to stop the current annotation process.
    """
    user = request.user
    print_debug("stop_annotation_api called")
    print_debug(f"Received stop annotation signal for user {user.username}.")
    stop_annotating()
    return HttpResponse("Annotation stopped.", status=200)


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
    print_debug("function data")
    message = request.POST["message"]
    # decompress the message if it is compressed
    message = decompress_json_data(message)
    user = request.user
    store_data(message, user)
    return JsonResponse({"status": "success"})


# Pre-Task Annotation Fetcher
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pre_task_annotation(request, timestamp):
    print_debug("function pre_task_annotation")
    user = request.user
    if request.method == "POST":
        # Start a new task
        print_debug("start_task")
        task = Task()
        task.user = user
        task.active = True
        task.start_timestamp = timezone.make_aware(datetime.fromtimestamp(timestamp / 1000))
        entry_id = int(request.POST.get("entry_id"))
        entry = TaskDatasetEntry.objects.filter(id=entry_id).first()
        if entry is None:
            return HttpResponse("No entry found with entry_id={}".format(entry_id))
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

        stop_annotating()

        return close_window()

    else:
        # Randomly choose a task from the dataset
        dataset = get_active_task_dataset()
        if dataset is None:
            return HttpResponse("No dataset found")
        entry = (
            TaskDatasetEntry.objects.filter(belong_dataset=dataset)
            .order_by("num_associated_tasks")
            .first()
        )
        if entry is None:
            return HttpResponse("No entry found in dataset id={}".format(dataset.id))
        print_debug(f"[Question] {entry.question}")
        print_debug(f"[Answer] {entry.answer}")

        start_annotating("pre_task_annotation")
        return render(
            request,
            "pre_task_annotation.html",
            {
                "cur_user": user,
                "task_timestamp": timestamp,
                "question": entry.question,
                "entry_id": entry.id,
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
        if task is not None and task.active:
            task.active = False

            post_annotation = PostTaskAnnotation()
            post_annotation.difficulty_actual = request.POST.get("difficulty_actual")
            post_annotation.aha_moment_type = request.POST.get("aha_moment_type")
            post_annotation.aha_moment_other = request.POST.get("aha_moment_other")
            post_annotation.aha_moment_source = request.POST.get("aha_moment_source")
            post_annotation.unhelpful_paths = request.POST.getlist("unhelpful_paths")
            post_annotation.unhelpful_paths_other = request.POST.get("unhelpful_paths_other")
            post_annotation.strategy_shift = request.POST.get("strategy_shift")
            post_annotation.strategy_shift_other = request.POST.get("strategy_shift_other")
            post_annotation.additional_reflection = request.POST.get(
                "additional_reflection"
            )
            post_annotation.belong_task = task
            post_annotation.save()

            task.save()
            stop_annotating()
            return close_window()
        else:
            stop_annotating()
            return HttpResponse("Task not found or already inactive", status=404)

    else:
        # Fetch task and relevant webpages
        task = Task.objects.filter(id=task_id, user=user).first()
        if task is None:
            return HttpResponse(f"No task found with task_id={task_id}")

        # filter relevant webpages
        webpages = Webpage.objects.filter(
            belong_task=task, is_redirected=False, during_annotation=False
        )
        # sort by start_timestamp
        webpages = sorted(webpages, key=lambda item: item.start_timestamp)
        # print_debug(webpages[0].event_list)

        question = task.content.question
        answer = json.loads(task.content.answer)
        print_debug(answer)

        start_annotating("post_task_annotation")
        return render(
            request,
            "post_task_annotation.html",
            {
                "cur_user": user,
                "task_id": task.id,
                "webpages": webpages,
                "question": question,
                "answer": answer,
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
        return HttpResponse(-1)

    task_id = task.id
    print_debug("Current Task ID: ", task_id)
    # Query Mode
    if "task_id" in request.POST:
        if request.POST["task_id"] == task_id:
            return HttpResponse(1)
        else:
            return HttpResponse(-1)
    return HttpResponse(task_id)


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


from django.contrib.auth.decorators import login_required

@login_required
@permission_classes([IsAuthenticated])
@wait_until_data_stored
def task_home(request):
    print_debug("function task_home")
    user = request.user
    completed_num = len(Task.objects.filter(user=user, active=False))
    pending_num = len(Task.objects.filter(user=user, active=True))
    return render(
        request,
        "task_home.html",
        {
            "cur_user": user,
            "completed_num": completed_num,
            "pending_num": pending_num,
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

    return render(
        request,
        "annotation_home.html",
        {
            "cur_user": user,
            "unannotated_tasks_to_webpages": unannotated_tasks_to_webpages,
            "annotated_tasks_to_webpages": annotated_tasks_to_webpages,
        },
    )


EXPECTED_SOURCES_MAP = {
    "personal": "Personal Knowledge / Experience",
    "wikipedia": "Wikipedia / Encyclopedia",
    "news": "News / Media Outlet",
    "forum": "Forum / Social Media / Q&A Site",
    "academic": "Academic Paper / Book",
    "video": "Video / Documentary",
    "other": "Other",
}

EFFORT_MAP = {
    0: "0-3 minutes",
    1: "3-5 minutes",
    2: "5-10 minutes",
    3: "10-15 minutes",
    4: "15-30 minutes",
    5: "30+ minutes",
}

EFFORT_EXPLANATION_MAP = {
    0: "The task is very simple and I expect to find the answer almost immediately.",
    1: "The task is simple and I expect to find the answer with a simple search.",
    2: "The task is of average difficulty and may require browsing a few pages.",
    3: "The task is difficult and may require some in-depth research.",
    4: "The task is very difficult and may require significant effort and synthesis.",
    5: "The task is extremely difficult and I expect it to take a long time.",
}

FAMILIARITY_MAP = {
    0: "0 - Not familiar at all",
    1: "1 - Slightly familiar",
    2: "2 - Moderately familiar",
    3: "3 - Familiar",
    4: "4 - Very familiar",
}

DIFFICULTY_MAP = {
    0: "0 - Very easy",
    1: "1 - Easy",
    2: "2 - Moderately difficult",
    3: "3 - Difficult",
    4: "4 - Very difficult",
}

FAMILIARITY_EXPLANATION_MAP = {
    0: "You have no prior knowledge or experience with this topic.",
    1: "You have heard of the topic, but know very little about it.",
    2: "You have some basic knowledge of the topic.",
    3: "You are comfortable with the topic and have a good understanding of it.",
    4: "You have a deep understanding of the topic and could explain it to others.",
}

DIFFICULTY_EXPLANATION_MAP = {
    0: "You expect to find the answer almost immediately.",
    1: "You expect to find the answer with a simple search.",
    2: "You expect to need to browse a few pages or perform a few searches.",
    3: "You expect to need to do some in-depth research and synthesis.",
    4: "You expect this to be a very challenging task that may require significant effort.",
}

CONFIDENCE_MAP = {
    1: "1 - Just a guess",
    2: "2 - Not very confident",
    3: "3 - Fairly confident",
    4: "4 - Very confident",
    5: "5 - Certain",
}

REASONING_METHOD_MAP = {
    "direct_fact": "The answer was a direct fact or number stated clearly on the page.",
    "synthesis_single_page": "I had to combine multiple pieces of information from the same page.",
    "synthesis_multi_page": "I had to combine information from different webpages.",
    "calculation": "I had to perform a calculation based on data I found.",
    "inference": "I had to make an inference or deduction that was not explicitly stated.",
    "other": "Other",
}

FAILURE_CATEGORY_MAP = {
    "bad_query": "My search query was ineffective or misleading.",
    "misinterpreted_info": "I found the right page, but misinterpreted the information.",
    "info_not_found": "I could not find the necessary information on the websites I visited.",
    "logic_error": "I made a logical or calculation error based on the information I found.",
    "ambiguous_info": "The information I found was ambiguous.",
    "outdated_info": "The information I found was outdated or no longer accurate.",
    "trusting_source": "I trusted a source that was not reliable or authoritative.",
    "time_pressure": "I was under time pressure and could not verify the information thoroughly.",
    "lack_expertise": "I lacked the necessary expertise to understand or evaluate the information.",
    "format_error": "I made a formatting error in my answer (e.g., missing units, incorrect decimal places).",
    "other": "Other:",
}

CORRECTIVE_PLAN_MAP = {
    "refine_query": "Use different or more specific search keywords.",
    "broaden_query": "Use more general search keywords.",
    "find_new_source_type": "Look for a different type of source (e.g., official report, news, academic paper).",
    "re-evaluate_info": "Re-examine the information I've already found more carefully.",
    "check_recency": "Specifically look for more recent information.",
    "check_reliability": "Check the reliability and authority of the sources I use.",
    "improve_logic": "Improve my logical reasoning or calculation methods.",
    "validate_source": "Try to find the same information on a second, independent source to validate it.",
    "reformulate_answer": "Reformulate my answer to meet the format requirements (e.g., adding units, correcting decimal places).",
    "other": "Other:",
}

AHA_MOMENT_MAP = {
    "data_table": "A data table or chart with the exact answer.",
    "direct_statement": "A direct statement in a paragraph.",
    "official_document": "Finding an official document or report (e.g., PDF, government site).",
    "key_definition": "Understanding a key definition or concept.",
    "synthesis": "Connecting two pieces of information that finally made sense together.",
    "other": "Other:",
}

UNHELPFUL_PATHS_MAP = {
    "no_major_roadblocks": "I did not encounter any major roadblocks.",
    "irrelevant_results": "Search results were mostly irrelevant.",
    "outdated_info": "Found sites with outdated information.",
    "low_quality": "Visited low-quality, spam, or untrustworthy sites.",
    "paywall": "Hit a paywall or login requirement.",
    "contradictory_info": "Found contradictory information on different sites.",
    "other": "Other:",
}

STRATEGY_SHIFT_MAP = {
    "no_change": "It didn't change much; my first approach worked.",
    "narrowed_search": "I had to significantly narrow my search to be more specific.",
    "broadened_search": "I had to broaden my search to find related concepts first.",
    "changed_source_type": "I realized I was looking at the wrong type of sources and switched.",
    "re-evaluated_assumption": "I realized my initial assumption was wrong and changed my approach.",
    "other": "Other:",
}

AHA_MOMENT_EXPLANATION_MAP = {
    "data_table": "You found a table or chart that contained the answer.",
    "direct_statement": "You found a sentence or paragraph that directly stated the answer.",
    "official_document": "You found an official document, such as a PDF from a government agency or a scientific paper, that contained the answer.",
    "key_definition": "Understanding a specific term or concept was the key to finding the answer.",
    "synthesis": "You had to combine information from multiple sources or sections to arrive at the answer.",
    "other": "None of the above.",
}

UNHELPFUL_PATHS_EXPLANATION_MAP = {
    "no_major_roadblocks": "The search process was straightforward.",
    "irrelevant_results": "Your search queries returned results that were not relevant to the task.",
    "outdated_info": "You found information that was no longer accurate.",
    "low_quality": "You encountered websites that were untrustworthy or difficult to use.",
    "paywall": "You were blocked by a paywall or a login requirement.",
    "contradictory_info": "You found conflicting information on different websites.",
    "other": "None of the above.",
}

STRATEGY_SHIFT_EXPLANATION_MAP = {
    "no_change": "Your initial plan was effective and you did not need to change it.",
    "narrowed_search": "You made your search queries more specific to narrow down the results.",
    "broadened_search": "You made your search queries more general to get a broader overview of the topic.",
    "changed_source_type": "You switched from looking at one type of source (e.g., news articles) to another (e.g., academic papers).",
    "re-evaluated_assumption": "You realized that one of your initial assumptions was wrong, which led you to change your search strategy.",
    "other": "None of the above.",
}

CANCEL_CATEGORY_EXPLANATION_MAP = {
    "info_unavailable": "You have searched, but cannot find the required information on the public web.",
    "too_difficult": "The task requires a level of analysis, synthesis, or understanding that is beyond your current capabilities.",
    "no_idea": "You have exhausted your initial ideas and are unsure how to approach the problem differently.",
    "too_long": "The task is consuming an excessive amount of time relative to its expected difficulty or importance.",
    "technical_issue": "You are blocked by a non-information-related problem, such as a website that is down, a required login, or a paywall.",
    "other": "None of the above categories accurately describe the reason for cancellation.",
}

MISSING_RESOURCES_EXPLANATION_MAP = {
    "expert_knowledge": "The task requires understanding of a specialized field that you do not possess.",
    "paid_access": "The information is likely behind a paywall or in a subscription-only database.",
    "better_tools": "A standard search engine is insufficient; a specialized tool (e.g., a scientific database, code interpreter) is needed.",
    "different_question": "The question is poorly phrased, ambiguous, or contains incorrect assumptions.",
    "info_not_online": "The information is likely to exist only in offline sources (e.g., books, private archives).",
    "time_limit": "You could likely solve it, but not within a reasonable timeframe.",
    "team_help": "The task requires collaboration or brainstorming with others.",
    "guidance": "You need a hint or direction from someone who knows the answer or the path to it.",
    "better_question": "The instructions for the task are unclear or incomplete.",
    "other": "A resource not listed here was needed.",
}

FAILURE_CATEGORY_EXPLANATION_MAP = {
    "bad_query": "Your search terms were too broad, too narrow, or did not capture the intent of the question.",
    "misinterpreted_info": "You found the correct data but misunderstood its meaning or context.",
    "info_not_found": "The information does not appear to be available on the pages you visited.",
    "logic_error": "You made a mistake in reasoning, calculation, or synthesis of the information.",
    "ambiguous_info": "The information you found was unclear, contradictory, or could be interpreted in multiple ways.",
    "outdated_info": "The information was once correct but is no longer valid.",
    "trusting_source": "You relied on a source that was biased, incorrect, or not authoritative.",
    "time_pressure": "You rushed and did not have enough time to find or verify the best answer.",
    "lack_expertise": "You could not understand the subject matter well enough to answer correctly.",
    "format_error": "Your answer was factually correct but did not follow the required format.",
    "other": "A reason for failure not listed here.",
}

CORRECTIVE_ACTION_EXPLANATION_MAP = {
    "refine_query": "Make your search terms more specific to narrow down the results.",
    "broaden_query": "Use more general terms to get a broader understanding of the topic first.",
    "find_new_source_type": "Switch from looking at blogs or forums to official reports, news, or academic papers.",
    "re-evaluate_info": "Read the pages you have already visited again, more slowly and carefully.",
    "check_recency": "Filter your search results by date to find the most current information.",
    "check_reliability": "Prioritize well-known, authoritative sources over anonymous or biased ones.",
    "improve_logic": "Double-check your calculations or the steps in your reasoning process.",
    "validate_source": "Confirm the information by finding at least one other independent source that says the same thing.",
    "reformulate_answer": "Check the instructions again to ensure your answer is in the correct format.",
    "other": "A corrective action not listed here.",
}


CANCEL_CATEGORY_MAP = {
    "info_unavailable": "I believe the information is not publicly available online.",
    "too_difficult": "The task is too complex or difficult for me to solve.",
    "no_idea": "I am completely stuck and have no idea how to proceed.",
    "too_long": "The task is taking too much time to complete.",
    "technical_issue": "I encountered a technical barrier (e.g., paywall, login, broken site).",
    "other": "Other:",
}

MISSING_RESOURCES_MAP = {
    "expert_knowledge": "Deep, specialized domain knowledge.",
    "paid_access": "Access to a paid subscription, database, or service.",
    "better_tools": "A more powerful or specialized search tool.",
    "different_question": "The question itself was too ambiguous or unanswerable.",
    "info_not_online": "The information is unlikely to exist publicly online.",
    "time_limit": "More time to research and explore.",
    "team_help": "Help from a team or community.",
    "guidance": "Guidance or mentorship from an expert.",
    "better_question": "A better-formulated question or clearer instructions.",
    "other": "Other:",
}


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
        return HttpResponse(f"No task found with task_id={task_id} or permission denied.")

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
        try:
            trial.submitted_sources = []
            sources_dict = json.loads(trial.source_url_and_text)
            for url, texts in sources_dict.items():
                for text in texts:
                    trial.submitted_sources.append({"url": url, "text": text})
        except (json.JSONDecodeError, TypeError):
            pass

    # 4. Fetch Post-Task or Cancellation Annotation
    final_annotation = PostTaskAnnotation.objects.filter(belong_task=task).first()
    post_task_annotation = None
    cancel_annotation = None
    if final_annotation:
        if task.cancelled:
            cancel_annotation = final_annotation
        else:
            post_task_annotation = final_annotation

    cancel_missing_resources = []
    if cancel_annotation:
        cancel_missing_resources = map_json_list(
            cancel_annotation.cancel_missing_resources, MISSING_RESOURCES_MAP
        )

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
        "cancel_missing_resources": cancel_missing_resources,
        "task": task,
        "FAMILIARITY_MAP": FAMILIARITY_MAP,
        "DIFFICULTY_MAP": DIFFICULTY_MAP,
        "EFFORT_MAP": EFFORT_MAP,
        "CONFIDENCE_MAP": CONFIDENCE_MAP,
        "REASONING_METHOD_MAP": REASONING_METHOD_MAP,
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
def cancel_annotation(request, task_id, end_timestamp):
    print_debug("function cancel_annotation")
    user = request.user
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f"No task found with task_id={task_id}")

    if request.method == "POST":
        task.cancelled = True
        task.save()
        cancel_annotation = PostTaskAnnotation()
        cancel_annotation.belong_task = task
        cancel_annotation.cancel_category = request.POST.get("cancel_category")
        cancel_annotation.cancel_reason = request.POST.get("cancel_reason")
        cancel_annotation.cancel_missing_resources = request.POST.get(
            "cancel_missing_resources_list"
        )
        cancel_annotation.cancel_missing_resources_other = request.POST.get(
            "cancel_missing_resources_other"
        )
        cancel_annotation.cancel_additional_reflection = request.POST.get(
            "cancel_additional_reflection"
        )
        cancel_annotation.save()
        stop_annotating()
        return close_window()

    else:
        task.active = False
        task.end_timestamp = timezone.make_aware(datetime.fromtimestamp(end_timestamp / 1000))
        task.save()

        entry = task.content
        question = entry.question
        answer = json.loads(entry.answer)

        start_annotating("cancel_annotation")
        return render(
            request,
            "cancel_annotation.html",
            {
                "cur_user": user,
                "task_id": task_id,
                "question": question,
                "answer": answer,
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
        return HttpResponse(f"No trial found with id={task_trial_id}")

    task = task_trial.belong_task
    if task.user != user and not user.is_superuser:
        return HttpResponse("Permission denied.")

    entry = task.content
    question = entry.question

    if request.method == "POST":
        ref_annotation = ReflectionAnnotation(
            belong_task_trial=task_trial,
            failure_category=request.POST.get("failure_category_list"),
            failure_reason=request.POST.get("failure_reason"),
            future_plan_actions=request.POST.get("future_plan_actions_list"),
            future_plan_other=request.POST.get("future_plan_other"),
            estimated_time=request.POST.get("estimated_time"),
            adjusted_difficulty=request.POST.get("adjusted_difficulty"),
            additional_reflection=request.POST.get("additional_reflection"),
        )
        ref_annotation.save()

        stop_annotating()

        return close_window()

    else:
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

        start_annotating("reflection_annotation")
        return render(
            request,
            "reflection_annotation.html",
            {
                "cur_user": user,
                "task_id": task.id,
                "question": question,
                "webpages": webpages,
                "user_answer": user_answer,
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
def submit_answer(request, task_id, timestamp):
    print_debug("function submit_answer")
    user = request.user
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f"No task found with task_id={task_id}")
    question = task.content.question
    start_timestamp = task.start_timestamp
    num_trial = task.num_trial
    if num_trial > 0:
        last_task_trial = TaskTrial.objects.filter(
            belong_task=task, num_trial=num_trial
        ).first()
        assert (
            last_task_trial is not None
        )  # Ensure that the last task trial exists, which should always be the case
        start_timestamp = last_task_trial.end_timestamp

    # Filter the webpage whose timestamp is within the range of start_timestamp and timestamp
    end_datetime = timezone.make_aware(datetime.fromtimestamp(timestamp / 1000))
    all_webpages = Webpage.objects.filter(
        belong_task=task, start_timestamp__gte=start_timestamp
    )
    webpages = all_webpages.filter(
        start_timestamp__lte=end_datetime, is_redirected=False, during_annotation=False
    )
    # Sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)

    if request.method == "POST":
        answer = request.POST.get("answer")
        additional_explanation = request.POST.get("additional_explanation")
        confidence = request.POST.get("confidence")
        reasoning_method = request.POST.get("reasoning_method")

        task_trial = TaskTrial()
        task_trial.belong_task = task
        task_trial.num_trial = num_trial + 1
        task.num_trial += 1
        task_trial.answer = answer
        task_trial.start_timestamp = start_timestamp
        task_trial.end_timestamp = timezone.make_aware(datetime.fromtimestamp(timestamp / 1000))
        task_trial.additional_explanation = additional_explanation
        task_trial.confidence = confidence
        task_trial.reasoning_method = reasoning_method

        # Deal with source_url_and_text
        source_id = 0
        source_url_and_text = {}
        while f"source_url_{source_id}" in request.POST:
            source_url = request.POST[f"source_url_{source_id}"]
            source_text = request.POST[f"source_text_{source_id}"]
            if source_url and source_text:
                if source_url not in source_url_and_text:
                    source_url_and_text[source_url] = []
                source_url_and_text[source_url].append(source_text)
            source_id += 1
        source_url_and_text = json.dumps(source_url_and_text)
        task_trial.source_url_and_text = source_url_and_text

        is_correct = check_answer(task.content, answer)
        task_trial.is_correct = is_correct
        if is_correct:
            task.end_timestamp = timezone.make_aware(
                datetime.fromtimestamp(timestamp / 1000)
            )

        task_trial.save()
        task.save()

        if is_correct:
            redirect_url = reverse("task_manager:post_task_annotation", args=[task_id])
        else:
            redirect_url = reverse(
                "task_manager:reflection_annotation", args=[task_trial.id]
            )

        for webpage in all_webpages:
            webpage.belong_task_trial = task_trial
            webpage.save()
        stop_annotating()

        return HttpResponseRedirect(redirect_url)

    else:
        # Handle GET request
        start_annotating("submit_answer")
        return render(
            request,
            "submit_answer.html",
            {
                "cur_user": user,
                "task_id": task_id,
                "question": question,
                "webpages": webpages,
                "num_trial": num_trial + 1,
                "confidence_choices": CONFIDENCE_MAP.items(),
                "reasoning_choices": REASONING_METHOD_MAP.items(),
            },
        )


@permission_classes([IsAuthenticated])
def view_task_info(request, task_id):
    print_debug("function view_task_info")
    user = request.user
    task = Task.objects.filter(id=task_id, user=user, active=True).first()
    if task is None:
        return HttpResponse(f"No task found with task_id={task_id}")

    question = task.content.question

    return render(
        request,
        "view_task_info.html",
        {
            "cur_user": user,
            "task_id": task.id,
            "question": question,
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

