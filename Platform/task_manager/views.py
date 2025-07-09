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
        message = request.POST['message']
        # decompress the message if it is compressed
        message = decompress_json_data(message)
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
    print_debug(answer)

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
    """
    获取与特定任务相关的所有数据，并在详细视图中呈现。
    此函数收集任务前问卷、所有尝试及其各自的网页、
    提交的答案、反思以及任务后或取消问卷。
    """
    print_debug(f"function show_task for task_id: {task_id}")
    task = Task.objects.filter(id=task_id, user=user).first()
    if task is None:
        return HttpResponse(f'No task found with task_id={task_id}')

    # 1. 获取常规任务信息
    task_question = task.content.question

    # 2. 获取任务前问卷
    pre_task_annotation = PreTaskAnnotation.objects.filter(belong_task=task).first()

    # 3. 获取所有尝试及相关数据
    task_trials = TaskTrial.objects.filter(belong_task=task).order_by('num_trial')
    trials_context = []
    for trial in task_trials:
        # 获取此特定尝试的所有网页
        trial_webpages = Webpage.objects.filter(belong_task_trial=trial).order_by('start_timestamp')

        # 格式化提交的答案来源
        submitted_sources = []
        try:
            # 该字段存储一个JSON字符串，格式如：{"url1": ["text1", "text2"], "url2": ["text3"]}
            sources_dict = json.loads(trial.source_url_and_text)
            for url, texts in sources_dict.items():
                for text in texts:
                    submitted_sources.append({'url': url, 'text': text})
        except (json.JSONDecodeError, TypeError):
            # 处理数据不是有效JSON或不存在的情况
            submitted_sources = []
            
        submitted_answer_context = {
            'answer': trial.answer,
            'confidence': trial.confidence,
            'sources': submitted_sources,
            'reasoning_method': trial.reasoning_method,
            'additional_explanation': trial.additional_explanation,
        }

        # 如果尝试不正确，则格式化反思问卷
        reflection_context = None
        if not trial.is_correct and trial.reflection_annotation:
            reflection = trial.reflection_annotation
            try:
                failure_reasons = json.loads(reflection.failure_category) if reflection.failure_category else []
            except (json.JSONDecodeError, TypeError):
                failure_reasons = []
            
            try:
                corrective_plan = json.loads(reflection.future_plan_actions) if reflection.future_plan_actions else []
            except (json.JSONDecodeError, TypeError):
                corrective_plan = []

            reflection_context = {
                'failure_reasons': failure_reasons,
                'failure_analysis': reflection.failure_reason,
                'corrective_plan': corrective_plan,
                'remaining_effort': reflection.remaining_effort,
                'additional_reflection': reflection.additional_reflection,
            }

        trials_context.append({
            'num_trial': trial.num_trial,
            'is_correct': trial.is_correct,
            'webpages': trial_webpages,
            'submitted_answer': submitted_answer_context,
            'reflection_annotation': reflection_context,
        })

    # 4. 获取任务后或取消问卷
    final_annotation = PostTaskAnnotation.objects.filter(belong_task=task).first()
    post_task_annotation_context = None
    cancel_annotation_context = None

    if final_annotation:
        if task.cancelled:
            # 这是取消问卷
            try:
                missing_resources = json.loads(final_annotation.cancel_missing_resources) if final_annotation.cancel_missing_resources else []
            except (json.JSONDecodeError, TypeError):
                missing_resources = []

            cancel_annotation_context = {
                'cancel_category': final_annotation.cancel_category,
                'cancel_reason': final_annotation.cancel_reason,
                'missing_resources': missing_resources,
                'additional_reflection': final_annotation.cancel_additional_reflection,
            }
        else:
            # 这是成功完成的问卷
            try:
                unhelpful_paths = json.loads(final_annotation.unhelpful_paths) if final_annotation.unhelpful_paths else []
            except (json.JSONDecodeError, TypeError):
                unhelpful_paths = []

            post_task_annotation_context = {
                'difficulty_actual': final_annotation.difficulty_actual,
                'aha_moment_type': final_annotation.aha_moment_type,
                'aha_moment_source': final_annotation.aha_moment_source,
                'unhelpful_paths': unhelpful_paths,
                'strategy_shift': final_annotation.strategy_shift,
                'additional_reflection': final_annotation.additional_reflection,
            }

    # 5. 组装最终上下文并渲染模板
    context = {
        'cur_user': user,
        'task_id': task.id,
        'task_question': task_question,
        'pre_task_annotation': pre_task_annotation,
        'trials': trials_context,
        'post_task_annotation': post_task_annotation_context,
        'cancel_annotation': cancel_annotation_context,
        'task': task, # 如果需要，传递整个任务对象
    }
    return render(request, 'show_task.html', context)


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
        cancel_annotation = PostTaskAnnotation()
        cancel_annotation.belong_task = task
        cancel_annotation.cancel_category = request.POST.get('cancel_category')
        cancel_annotation.cancel_reason = request.POST.get('cancel_reason')
        cancel_annotation.cancel_missing_resources = request.POST.get('cancel_missing_resources')
        cancel_annotation.cancel_missing_resources_other = request.POST.get('cancel_missing_resources_other')
        cancel_annotation.cancel_additional_reflection = request.POST.get('cancel_additional_reflection')
        cancel_annotation.save()
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
        ref_annotation.failure_category = request.POST.get('failure_category_list')
        ref_annotation.failure_reason = request.POST.get('failure_reason')
        ref_annotation.future_plan_actions = request.POST.get('future_plan_actions_list')
        ref_annotation.future_plan_other  = request.POST.get('future_plan_other')
        ref_annotation.remaining_effort = request.POST.get('remaining_effort')
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
    num_trial = task.num_trial
    if num_trial > 1:
        last_task_trial = TaskTrial.objects.filter(belong_task=task, num_trial=num_trial - 1).first()
        assert last_task_trial is not None  # Ensure that the last task trial exists, which should always be the case
        start_timestamp = last_task_trial.end_timestamp
        
    # Filter the webpage whose timestamp is within the range of start_timestamp and timestamp
    webpages = Webpage.objects.filter(belong_task=task, start_timestamp__gte=start_timestamp,
                                      start_timestamp__lt=timestamp)
    # Sort by start_timestamp
    webpages = sorted(webpages, key=lambda item: item.start_timestamp)

    if request.method == 'POST':
        answer = request.POST.get('answer')
        additional_explanation = request.POST.get('additional_explanation')
        confidence = request.POST.get('confidence')
        reasoning_method = request.POST.get('reasoning_method')
        
        task_trial = TaskTrial()
        task_trial.belong_task = task
        task_trial.num_trial = num_trial + 1
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
        
        redirect_url = f'/task/post_task_annotation/{task_id}'
        if check_answer(task.content, answer):
            task_trial.is_correct = True
            task.end_timestamp = timestamp
        else:
            task_trial.is_correct = False
            redirect_url = f'/task/reflection_annotation/{task_id}/{timestamp}'

        task_trial.save()
        task.save()
        
        for webpage in webpages:
            webpage.belong_task_trial = task_trial
            webpage.save()
        
        return HttpResponseRedirect(redirect_url)

    return render(
        request,
        'submit_answer.html',
        {
            'cur_user': user,
            'task_id': task_id,
            'question': question,
            'webpages': webpages,
            'num_trial': num_trial + 1,
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
