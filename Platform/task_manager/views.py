#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from user_system.utils import *
from .utils import *

try:
    import simplejson as json
except ImportError:
    import json

# =============================================
# =         Below is newly added code         =
# =============================================

# Store data
@csrf_exempt
def data(request):
    print_debug("function data")
    if request.method == 'POST':
        message = json.loads(request.POST['message'])
        store_data(message)
        return HttpResponse('data storage succeeded')
    else:
        print_debug(request.method)
        return HttpResponse('data storage failed')


# Pre-Task Annotation Fetcher
@require_login
def pre_task_annotation(user, request, timestamp):
    if request.method == 'POST':
        # Start a new task
        print_debug("start_task")
        task = Task()
        task.user = user
        task.active = True
        task.start_timestamp = timestamp
        entry_id = int(request.POST.get('entry_id'))
        entry = TaskDatasetEntry.objects.filter(id=entry_id).first()
        if entry is None:
            return HttpResponse('No entry found with entry_id={}'.format(entry_id))
        entry.num_associated_tasks += 1
        task.content = entry
        entry.save()
        task.save()

        pre_annotation = PreTaskAnnotation()
        pre_annotation.belong_task = task
        pre_annotation.description = request.POST.get('description')
        pre_annotation.completion_criteria = request.POST.get('completion_criteria')
        pre_annotation.familiarity = request.POST.get('familiarity')
        pre_annotation.difficulty = request.POST.get('difficulty')
        pre_annotation.effort = request.POST.get('effort')
        pre_annotation.initial_strategy = request.POST.get('initial_strategy')
        pre_annotation.save()

        return close_window()

    # Randomly choose a task from the dataset
    dataset = get_active_task_dataset()
    if dataset is None:
        return HttpResponse('No dataset found')
    entries = TaskDatasetEntry.objects.filter(belong_dataset=dataset)
    if not entries.exists():
        return HttpResponse('No entries found in the dataset')
    # sort by the number of associated tasks
    entries = sorted(entries, key=lambda item: item.num_associated_tasks) # TODO: Don't sort on the fly
    print_debug(f"[Question] {entries[0].question}")
    print_debug(f"[Answer] {entries[0].answer}")
    question = entries[0].question

    return render(
        request,
        'pre_task_annotation.html',
        {
            'cur_user': user,
            'task_timestamp': timestamp,
            'question': question,
            'entry_id': entries[0].id,
        }
    )


# Post-Task Annotation Fetcher
@require_login
def post_task_annotation(user, request, task_id):
    if request.method == 'POST':
        # End a task
        print_debug("end_task")
        task = Task.objects.filter(id=task_id, user=user).first()
        if task is not None and task.active:
            task.active = False

            post_annotation = PostTaskAnnotation()
            post_annotation.difficulty_actual = request.POST.get('difficulty_actual')
            post_annotation.aha_moment_type = request.POST.get('aha_moment_type')
            post_annotation.aha_moment_other = request.POST.get('aha_moment_other')
            post_annotation.aha_moment_source = request.POST.get('aha_moment_source')
            post_annotation.unhelpful_paths = request.POST.get('unhelpful_paths')
            post_annotation.additional_reflection = request.POST.get('additional_reflection')
            post_annotation.belong_task = task
            post_annotation.save()

            task.save()
            return close_window()
        # error
        print_debug("error in post_task_annotation")
        return close_window()

    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')

    # filter relevant webpages
    webpages = Webpage.objects.filter(belong_task=task)
    # sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)
    # print_debug(webpages[0].event_list)

    question = task.content.question
    answer = json.loads(task.content.answer)
    print(answer)

    return render(
        request,
        'post_task_annotation.html',
        {
            'cur_user': user,
            'task_id': task.id,
            'webpages': webpages,
            'question': question,
            'answer': answer,
        }
    )


# Return active tasks
@require_login
def active_task(user, request):
    # Return active tasks
    print_debug("active_task")
    task = Task.objects.filter(user=user, active=True).first()
    if task is None:
        return HttpResponse(-1)

    task_id = task.id
    print_debug("Current Task ID: ", task_id)
    # Query Mode
    if 'task_id' in request.POST:
        if request.POST['task_id'] == task_id:
            return HttpResponse(1)
        else:
            return HttpResponse(-1)
    return HttpResponse(task_id)


# Initialize the task
@require_login
def initialize(user, request):
    if request.method == 'POST':
        print_debug("initialize")

        # Delete all active tasks and relevant queries and pages
        tasks = Task.objects.filter(user=user, active=True)
        # for task in tasks:
        #     task.delete()

        # TODO: Let users choose to continue the previous task or start a new task
        if tasks.first() is not None:
            return HttpResponse(tasks.first().id)
    return HttpResponse(-1)


@require_login
def task_home(user, request):
    print_debug("function task_home")
    # clear_expired_query(user)
    completed_num = len(Task.objects.filter(user=user, active=False))
    pending_num = len(Task.objects.filter(user=user, active=True))
    return render(
        request,
        'task_home.html',
        {
            'cur_user': user,
            'completed_num': completed_num,
            'pending_num': pending_num,
        }
    )


@require_login
def annotation_home(user, request):
    print_debug("function annotation_home")
    clear_expired_query(user)
    annotated_tasks = sorted(Task.objects.filter(user=user, active=False), key=lambda task: -task.id)
    unannotated_tasks = sorted(Task.objects.filter(user=user, active=True), key=lambda task: -task.id)
    annotated_tasks_to_webpages = []
    unannotated_tasks_to_webpages = []
    for task in unannotated_tasks:
        # end_timestamp = task.end_timestamp
        # Convert to human-readable time
        # end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
        unannotated_tasks_to_webpages.append((task.id, sorted(
            Webpage.objects.filter(user=user, belong_task=task), key=lambda item: item.start_timestamp))
                                             )
    for task in annotated_tasks:
        # end_timestamp = task.end_timestamp
        # Convert to human-readable time
        # end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
        annotated_tasks_to_webpages.append((task.id, sorted(
            Webpage.objects.filter(user=user, belong_task=task), key=lambda item: item.start_timestamp))
                                           )

    return render(
        request,
        'annotation_home.html',
        {
            'cur_user': user,
            'unannotated_tasks_to_webpages': unannotated_tasks_to_webpages,
            'annotated_tasks_to_webpages': annotated_tasks_to_webpages,
        }
    )


@require_login
def show_task(user, request, task_id):
    print_debug("function show_task")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')

    # filter relevant webpages
    webpages = Webpage.objects.filter(belong_task=task)
    # sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)

    return render(
        request,
        'show_task.html',
        {
            'cur_user': user,
            'task_id': task.id,
            'webpages': webpages,
            'task': task,
        }
    )


@require_login
def show_tool_use_page(user, request):
    print_debug("function show_tool_use_page")

    return render(
        request,
        'show_tool_use_page.html',
        {
            'cur_user': user,
        }
    )


@require_login
def tool_use(user, request):
    if request.method == 'POST':
        print_debug("tool_use")

        tool = request.POST['tool']

        for_url = ""

        if tool == "math":
            for_url = "https://www.wolframalpha.com/"

        elif tool == "graph":
            for_url = "https://www.geogebra.org/classic"

        elif tool == "code":
            for_url = "https://www.jdoodle.com/start-coding"

        return HttpResponse(f'<html><head><meta http-equiv="refresh" content="0;url={for_url}"></head><body></body></html>')


@require_login
def cancel_task(user, request, task_id, end_timestamp):
    print_debug("function cancel_task")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')
    
    if request.method == 'POST':
        task.cancelled = True
        task.cancel_category = request.POST.get('cancel_category')
        task.cancel_reason = request.POST.get('cancel_reason')
        task.cancel_missing_resources = request.POST.get('cancel_missing_resources')
        task.cancel_missing_resources_other = request.POST.get('cancel_missing_resources_other')
        return close_window()
    
    task.active = False
    task.end_timestamp = end_timestamp
    task.save()

    entry = task.content
    question = entry.question
    answer = json.loads(entry.answer)

    return render(
        request,
        'cancel_task.html',
        {
            'cur_user': user,
            'task_id': task_id,
            'question': question,
            'answer': answer,
        }
    )



@require_login
def reflection_annotation(user, request, task_id, end_timestamp):
    print_debug("function reflection_annotation")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')
    entry = task.content
    question = entry.question
    task_trial = TaskTrial.objects.filter(belong_task=task, end_timestamp=end_timestamp).first()
    if task_trial is None:
        return HttpResponse(f'No trial found with task_id={task_id} and end_timestamp={end_timestamp}')

    if request.method == 'POST':
        ref_annotation = ReflectionAnnotation()
        ref_annotation.failure_category = request.POST.get('failure_category')
        ref_annotation.failure_reason = request.POST.get('failure_reason')
        ref_annotation.future_plan_actions = request.POST.get('future_plan_actions')
        ref_annotation.future_plan_other  = request.POST.get('future_plan_other')
        ref_annotation.save()
        task_trial.reflection_annotation = ref_annotation
        task_trial.save()

        return close_window()

    # Filter the webpage whose timestamp is within the range of start_timestamp and timestamp
    webpages = Webpage.objects.filter(belong_task=task, start_timestamp__gte=task_trial.start_timestamp,
                                      start_timestamp__lt=end_timestamp)
    # Sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)

    return render(
        request,
        'reflection_annotation.html',
        {
            'cur_user': user,
            'task_id': task_id,
            'question': question,
            'webpages': webpages,
        }
    )


@require_login
def submit_answer(user, request, task_id, timestamp):
    print_debug("function submit_answer")
    
    # Wait until the storage is ready
    # wait_until_storing_data_done()

    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')
    question = task.content.question
    start_timestamp = task.start_timestamp
    if task.num_trial > 1:
        last_task_trial = TaskTrial.objects.filter(belong_task=task, num_trial=task.num_trial - 1).first()
        assert last_task_trial is not None  # Ensure that the last task trial exists, which should always be the case
        start_timestamp.start_timestamp = last_task_trial.end_timestamp

    if request.method == 'POST':
        answer = request.POST.get('answer')
        additional_explanation = request.POST.get('additional_explanation')
        confidence = request.POST.get('confidence')
        reasoning_method = request.POST.get('reasoning_method')
        
        
        redirect_url = f'/task/post_task_annotation/{task_id}'
        task_trial = TaskTrial()
        task_trial.belong_task = task
        task_trial.num_trial = task.num_trial + 1
        task.num_trial += 1
        task_trial.answer = answer
        task_trial.start_timestamp = start_timestamp
        task_trial.end_timestamp = timestamp
        task_trial.additional_explanation = additional_explanation
        task_trial.confidence = confidence
        task_trial.reasoning_method = reasoning_method
        
        # Deal with source_url_and_text
        source_id = 0
        source_url_and_text = {}
        while f'source_url_{source_id}' in request.POST:
            source_url = request.POST[f'source_url_{source_id}']
            source_text = request.POST[f'source_text_{source_id}']
            if source_url and source_text:
                if source_url not in source_url_and_text:
                    source_url_and_text[source_url] = []
                source_url_and_text[source_url].append(source_text)
            source_id += 1
        source_url_and_text = json.dumps(source_url_and_text)
        task_trial.source_url_and_text = source_url_and_text
        
        if check_answer(task.content, answer):
            task_trial.is_correct = True
            task.end_timestamp = timestamp
        else:
            task_trial.is_correct = False
            redirect_url = f'/task/reflection_annotation/{task_id}/{timestamp}'

        task_trial.save()
        task.save()
        return HttpResponseRedirect(redirect_url)

    # Filter the webpage whose timestamp is within the range of start_timestamp and timestamp
    webpages = Webpage.objects.filter(belong_task=task, start_timestamp__gte=start_timestamp,
                                      start_timestamp__lt=timestamp)
    # Sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)

    return render(
        request,
        'submit_answer.html',
        {
            'cur_user': user,
            'task_id': task_id,
            'question': question,
            'webpages': webpages,
        }
    )


@require_login
def view_task_info(user, request, task_id):
    print_debug("function view_task_info")
    task = Task.objects.filter(id=task_id, user=user, active=True).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')

    question = task.content.question

    return render(
        request,
        'view_task_info.html',
        {
            'cur_user': user,
            'task_id': task.id,
            'question': question,
        }
    )

@require_login
def remove_task(user, request, task_id):
    print_debug("function remove_task")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')
    task.delete()
    return HttpResponse('Task removed successfully')
