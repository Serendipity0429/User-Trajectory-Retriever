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


@csrf_exempt
@require_login
def page_annotation_submit(user, request, page_id):
    print_debug("function page_annotation_submit")
    if request.method == 'POST':
        message = request.POST['message']
        store_page_annotation(message, page_id)
        return HttpResponse('nice')
    else:
        return HttpResponse('oh no')


@require_login
def task_partition(user, request):
    print_debug("function task_partition")
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        if action_type == "partition":
            query_ids = request.POST.getlist('unpartition_checkbox')
            if query_ids:
                partition(user, query_ids)

        if action_type == "delete":
            query_ids = request.POST.getlist('unpartition_checkbox')
            if query_ids:
                delete(user, query_ids)

        if action_type == "unpartition":
            task_ids = request.POST.getlist('partition_checkbox')
            if task_ids:
                unpartition(user, task_ids)
        return HttpResponseRedirect('/task/partition/')

    clear_expired_query(user)
    unpartition_queries = sorted(Query.objects.filter(user=user, partition_status=False),
                                 key=lambda item: item.start_timestamp)
    unpartition_queries_to_pages = []
    for query in unpartition_queries:
        unpartition_queries_to_pages.append((query, sorted(
            PageLog.objects.filter(user=user, belong_query=query, page_type='SERP'),
            key=lambda item: item.start_timestamp)))

    unannotated_tasks = TaskAnnotation.objects.filter(user=user, annotation_status=False)
    unannotated_tasks_to_queries = []
    for task in unannotated_tasks:
        unannotated_tasks_to_queries.append((task.id, sorted(
            Query.objects.filter(user=user, partition_status=True, task_annotation=task),
            key=lambda item: item.start_timestamp)))
    return render(
        request,
        'task_partition.html',
        {
            'cur_user': user,
            'unpartition_queries_to_pages': unpartition_queries_to_pages,
            'partition_tasks_to_queries': unannotated_tasks_to_queries
        }
    )


@require_login
def task_annotation1(user, request, task_id):
    print_debug("function task_annotation1")
    if request.method == 'POST':
        time_condition = request.POST.get('time_condition_' + str(task_id))
        position_condition = request.POST.get('position_condition_' + str(task_id))
        specificity = request.POST.get('specificity_' + str(task_id))
        trigger = request.POST.get('trigger_' + str(task_id))
        expertise = request.POST.get('expertise_' + str(task_id))

        task_annotation = TaskAnnotation.objects.get(id=task_id, user=user, annotation_status=False)
        task_annotation.time_condition = time_condition
        task_annotation.position_condition = position_condition
        task_annotation.specificity = specificity
        task_annotation.trigger = trigger
        task_annotation.expertise = expertise
        task_annotation.save()
        return HttpResponseRedirect('/task/query_annotation/' + str(task_id))

    task_annotation = TaskAnnotation.objects.filter(id=task_id, user=user, annotation_status=False)
    if len(task_annotation) == 0:
        return HttpResponseRedirect('/task/home/')
    # task_annotation = task_annotation[0]
    print_debug("function task_annotation1")
    task_annotation = task_annotation.first()
    queries = sorted(Query.objects.filter(user=user, partition_status=True, task_annotation=task_annotation),
                     key=lambda item: item.start_timestamp)
    queries_to_pages = []
    for query in queries:
        queries_to_pages.append((query, sorted(PageLog.objects.filter(user=user, belong_query=query, page_type='SERP'),
                                               key=lambda item: item.start_timestamp)))

    return render(
        request,
        'task_annotation1.html',
        {
            'cur_user': user,
            'task': task_annotation,
            'queries_to_pages': queries_to_pages
        }
    )


@require_login
def pre_query_annotation(user, request, timestamp):
    print_debug("function pre_query_annotation")
    if request.method == 'POST':
        diversity = request.POST.get('diversity')
        habit = request.POST.get('habit_str')
        redundancy = request.POST.get('redundancy')
        difficulty = request.POST.get('difficulty')
        gain = request.POST.get('gain')
        effort = request.POST.get('effort')

        new_query = Query()
        new_query.task_annotation = TaskAnnotation.objects.filter(annotation_status=True).first()
        new_query.partition_status = False
        new_query.annotation_status = False
        new_query.life_start = int(time.time())
        new_query.user = user
        new_query.diversity = diversity
        new_query.habit = habit
        new_query.redundancy = redundancy
        new_query.difficulty = difficulty
        new_query.gain = gain
        new_query.effort = effort
        new_query.start_timestamp = timestamp
        new_query.save()
        return close_window()

    # GET
    return render(
        request,
        'pre_query_annotation.html',
        {
            'cur_user': user,
        }
    )


@require_login
def query_annotation(user, request, task_id):
    print_debug("function query_annotation")
    task_annotation = TaskAnnotation.objects.filter(id=task_id, user=user, annotation_status=False)
    if len(task_annotation) == 0:
        return HttpResponseRedirect('/task/home/')
    task_annotation = task_annotation.first()
    queries = sorted(Query.objects.filter(user=user, partition_status=True, task_annotation=task_annotation),
                     key=lambda item: item.start_timestamp)
    items_list = get_items_list(user, queries)

    if request.method == 'POST':
        for query in queries:
            relation = request.POST.get('relation_ratio_' + str(query.id))
            inspiration = request.POST.get('inspiration_' + str(query.id))
            satisfaction = request.POST.get('satisfaction_ratio_' + str(query.id))
            ending_type = request.POST.get('ending_ratio_' + str(query.id))
            other_reason = request.POST.get('ending_text_' + str(query.id))
            other_relation = request.POST.get('relation_text_' + str(query.id))
            # query__annotation = QueryAnnotation.objects.filter(belong_query=query)
            print_debug("function query_annotation")
            query__annotation = QueryAnnotation.objects.filter(belong_query=query).first()
            for dup_query_annotation in QueryAnnotation.objects.filter(belong_query=query)[1:]:
                dup_query_annotation.delete()
            query__annotation.relation = relation
            query__annotation.inspiration = inspiration
            query__annotation.satisfaction = satisfaction
            query__annotation.ending_type = ending_type
            query__annotation.other_reason = other_reason
            query__annotation.other_relation = other_relation

            # 触发expectation标注
            if query.diversity != -1:
                # print(request.POST.get('habit_str_' + str(query.id)))
                diversity_confirm = request.POST.get('diversity_confirm_' + str(query.id))
                habit_confirm = request.POST.get('habit_str_' + str(query.id))
                redundancy_confirm = request.POST.get('redundancy_confirm_' + str(query.id))
                difficulty_confirm = request.POST.get('difficulty_confirm_' + str(query.id))
                gain_confirm = request.POST.get('gain_confirm_' + str(query.id))
                effort_confirm = request.POST.get('effort_confirm_' + str(query.id))
                query.diversity_confirm = diversity_confirm
                query.habit_confirm = habit_confirm
                query.redundancy_confirm = redundancy_confirm
                query.difficulty_confirm = difficulty_confirm
                query.gain_confirm = gain_confirm
                query.effort_confirm = effort_confirm
                query.save()
            query__annotation.save()
        return HttpResponseRedirect('/task/task_annotation2/' + str(task_id))

    return render(
        request,
        'query_annotation.html',
        {
            'cur_user': user,
            'items_list': items_list
        }
    )


@require_login
def task_annotation2(user, request, task_id):
    print_debug("function task_annotation2")
    task_annotation = TaskAnnotation.objects.filter(id=task_id, user=user, annotation_status=False)
    if len(task_annotation) == 0:
        return HttpResponseRedirect('/task/home/')
    # task_annotation = task_annotation
    task_annotation = task_annotation.first()
    queries = sorted(Query.objects.filter(user=user, partition_status=True, task_annotation=task_annotation),
                     key=lambda item: item.start_timestamp)
    flag = check_serp_annotations(user, queries)

    queries_to_pages = []
    for query in queries:
        queries_to_pages.append((query, sorted(PageLog.objects.filter(user=user, belong_query=query, page_type='SERP'),
                                               key=lambda item: item.start_timestamp)))

    if request.method == 'POST':
        satisfaction = request.POST.get('satisfaction_ratio')
        information_difficulty = request.POST.get('information_difficulty')
        success = request.POST.get('success')
        task_annotation.satisfaction = int(satisfaction)
        task_annotation.information_difficulty = int(information_difficulty)
        task_annotation.success = int(success)
        task_annotation.other_reason = request.POST.get('ending_text_' + str(task_id))
        task_annotation.annotation_status = True
        task_annotation.save()
        for query in queries:
            query.annotation_status = True
            query.save()
        return HttpResponseRedirect('/task/annotation/')

    return render(
        request,
        'task_annotation2.html',
        {
            'cur_user': user,
            'task': task_annotation,
            'queries_to_pages': queries_to_pages,
            'flag': flag
        }
    )


@require_login
def show_page(user, request, page_id):
    print_debug("function show_page")
    serp = PageLog.objects.filter(id=page_id, user=user)
    if len(serp) == 0:
        return HttpResponseRedirect('/task/home/')
    # serp = serp[0]
    serp = serp.first()
    return render(
        request,
        'show_query.html',
        {
            'query': serp.query_string,
            'html': serp.html,
        }
    )


@require_login
def page_annotation(user, request, page_id):
    page = PageLog.objects.filter(id=page_id, user=user)
    if len(page) == 0:
        return HttpResponseRedirect('/task/home/')
    # page = page[0]
    print_debug("function page_annotation")
    page = page.first()
    # clicked_results = json.loads(page.clicked_results)
    clicked_results = []
    clicked_ids = []
    for result in clicked_results:
        if result['id'] not in clicked_ids:
            clicked_ids.append(result['id'])
    if page.origin == 'baidu':
        return render(
            request,
            'page_annotation_baidu.html',
            {
                'query': page.query_string,
                'html': page.html,
                'page_id': page_id,
                'clicked_ids': clicked_ids
            }
        )
    if page.origin == 'sogou':
        return render(
            request,
            'page_annotation_sogou.html',
            {
                'query': page.query_string,
                'html': page.html,
                'page_id': page_id,
                'clicked_ids': clicked_ids
            }
        )


@csrf_exempt
def show_me_serp(request, query_id):
    print_debug("function show_me_serp")
    query = Query.objects.get(id=query_id)
    serp = PageLog.objects.filter(belong_query=query, page_id='1')
    # serp = serp[0]
    serp = serp.first()
    print(serp.id)
    return render(
        request,
        'show_query.html',
        {
            'html': serp.html,
        }
    )


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
        task.content = entry
        task.save()

        pre_annotation = PreTaskAnnotation()
        pre_annotation.belong_task = task
        pre_annotation.description = request.POST.get('description')
        pre_annotation.completion_criteria = request.POST.get('completion_criteria')
        pre_annotation.difficulty = request.POST.get('difficulty')
        pre_annotation.effort = request.POST.get('effort')
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
    entries = sorted(entries, key=lambda item: item.num_associated_tasks)
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
            post_annotation.expertise = request.POST.get('expertise')
            post_annotation.reflection = request.POST.get('reflection')
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
def cancel_task(user, request, task_id):
    print_debug("function cancel_task")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')

    if request.method == 'POST':
        task.cancelled = True
        task.active = False
        task.save()
        return close_window()

    entry = task.content
    question = entry.question

    return render(
        request,
        'cancel_task.html',
        {
            'cur_user': user,
            'task_id': task_id,
            'question': question,
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
        ref_annotation.failure_reason = request.POST.get('failure_reason')
        ref_annotation.future_plan = request.POST.get('future_plan')
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
        redirect_url = f'/task/post_task_annotation/{task_id}'
        task_trial = TaskTrial()
        task_trial.belong_task = task
        task_trial.num_trial = task.num_trial + 1
        task_trial.answer = answer
        task_trial.start_timestamp = start_timestamp
        task_trial.end_timestamp = timestamp

        if check_answer(task.content, answer):
            task_trial.is_correct = True
        else:
            task_trial.is_correct = False
            redirect_url = f'/task/reflection_annotation/{task_id}/{timestamp}'

        task_trial.save()
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
