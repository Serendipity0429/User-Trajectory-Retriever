#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'steven'

from rest_framework.response import Response
from django.http import HttpResponse
from django.conf import settings
import logging
from datetime import datetime
from django.utils import timezone

from .models import Task, Webpage, TaskDataset

try:
    import simplejson as json
except ImportError:
    import json
import time
import base64
import zlib

class AnnotationState:
    def __init__(self):
        self.is_annotating = False
        self.is_storing_data = False
        self.annotation_name = 'none'
        self.annotation_start_time = float('inf')

    def start_annotating(self, name):
        self.annotation_start_time = time.time()
        self.annotation_name = name
        self.is_annotating = True
        print_debug(f"Started annotating for {name}.")

    def stop_annotating(self):
        self.annotation_start_time = float('inf')
        self.annotation_name = 'none'
        self.is_annotating = False
        print_debug("Stopped annotating.")

annotation_state = AnnotationState()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Refined
def print_debug(*args, **kwargs):
    if settings.DEBUG:
        message = " ".join(map(str, args)) + " ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(message)


def print_json_debug(message):
    truncator = 50
    # only print the first 50 characters for each key
    message = {k: v[:truncator] + "..." if hasattr(v, '__getitem__') and len(v) > truncator else v for k, v in
               message.items()}
    print_debug(json.dumps(message, indent=4))

def decompress_json_data(compressed_data):
    compressed_bytes = base64.b64decode(compressed_data)
    decompressed_bytes = zlib.decompress(compressed_bytes).decode('utf-8')
    decompressed_json = json.loads(decompressed_bytes)
    return decompressed_json

def start_annotating(name):
    annotation_state.start_annotating(name)
    
def stop_annotating():
    annotation_state.stop_annotating()
    
def start_storing_data():
    annotation_state.is_storing_data = True
    
def stop_storing_data():
    annotation_state.is_storing_data = False
    
    
def store_data(message, user):
    annotation_state.is_storing_data = True
    
    print_json_debug(message)
    if message['url'].startswith(settings.IP_TO_LAUNCH):
        print_debug("Skipping storing data for local URL:", message['url'])
        annotation_state.is_storing_data = False
        return
    task = Task.objects.filter(user=user, active=True).first()
    if not task:
        print_debug("No active task found for user", user.username)
        annotation_state.is_storing_data = False
        return
    
    webpage = Webpage()
    # A page is considered a redirect if the dwell time is very short (< 200ms) or if there's no user interaction.
    if check_is_redirected_page(message):
        print_debug("Redirect detected, setting is_redirected to True")
        webpage.is_redirected = True
    
    sent_when_active = message.get('sent_when_active', False)
    
    print_debug("Annotating:", annotation_state.is_annotating and not sent_when_active)  
    webpage.during_annotation = annotation_state.is_annotating and not sent_when_active
    webpage.annotation_name = annotation_state.annotation_name
    webpage.user = user
    
    webpage.belong_task = task
    webpage.title = message['title']
    webpage.url = message['url']
    webpage.referrer = message['referrer']
    webpage.start_timestamp = timezone.make_aware(datetime.fromtimestamp(message['start_timestamp'] / 1000))
    webpage.end_timestamp = timezone.make_aware(datetime.fromtimestamp(message['end_timestamp'] / 1000))
    webpage.dwell_time = message['dwell_time']
    webpage.mouse_moves = message['mouse_moves']
    webpage.event_list = message['event_list']
    # Replace the problematic string to prevent premature script tag closure in the template.
    # The sequence '<\/script>' is safe for HTML parsers but correctly interpreted by JavaScript.
    webpage.rrweb_record = message['rrweb_record'].replace(
                "</script>", "<\\/script>"
        )
    task.end_timestamp = timezone.make_aware(datetime.fromtimestamp(message['end_timestamp'] / 1000))
    
    webpage.save()
    task.save()
    stop_storing_data()
    
def check_is_redirected_page(message):
    # A page is considered a redirect if the dwell time is very short (< 1000ms) or if there's no user interaction.
    return message['dwell_time'] < 1000 or (message['mouse_moves'] == '[]' and message['rrweb_record'] == '[]' and message['event_list'] == '[]') or message['title'] == '' or 'redirect' in message['title'].lower()

def wait_until_data_stored(func):
    def wrapper(*args, **kwargs):
        # Sleep for a short duration to ensure the backend receives the data
        time.sleep(0.3)
        while annotation_state.is_storing_data:
            print_debug("Waiting for data to be stored...")
            time.sleep(0.5)
        return func(*args, **kwargs)
    return wrapper
    

def check_answer(entry, user_answer):
    try:
        entry_answers = json.loads(entry.answer)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON: {entry.answer}")
        return False
    
    print_debug("Question:", entry.question)
    print_debug("User Answer:", user_answer)
    print_debug("Correct Answer:", entry_answers)

    if isinstance(entry_answers, list):
        entry_answers = [str(ans) for ans in entry_answers]
    if isinstance(entry_answers, str):
        entry_answers = [entry_answers]

    user_answers = [ans.strip().lower() for ans in user_answer.split(';')]
    entry_answers = [ans.strip().lower() for ans in entry_answers]

    is_correct = all(any(user_ans == entry_ans for entry_ans in entry_answers) for user_ans in user_answers)

    return is_correct


def close_window():
    return HttpResponse('<html><body><script>window.close()</script></body></html>')

def get_active_task_dataset():
    active_dataset = "nq_hard_questions"
    try:
        active_dataset = TaskDataset.objects.filter(name=active_dataset).first()
    except Exception as e:
        print(f"Error getting active dataset {active_dataset}, error: {e}")
    return active_dataset


def get_pending_annotation(user):
    """
    Checks for pending annotations for a user and returns the URL to the annotation page if found.
    """
    from django.urls import reverse
    from .models import Task, TaskTrial
    from django.core.exceptions import ObjectDoesNotExist

    try:
        # Check for pending post-task annotations
        pending_post_task = Task.objects.filter(
            user=user, active=False, cancelled=False, posttaskannotation__isnull=True
        ).first()
        if pending_post_task:
            return reverse("task_manager:post_task_annotation", args=[pending_post_task.id])

        # Check for pending reflection annotations
        pending_reflection_trials = TaskTrial.objects.filter(
            belong_task__user=user, is_correct=False, reflectionannotation__isnull=True
        ).order_by('end_timestamp')

        if pending_reflection_trials.exists():
            trial_to_annotate = pending_reflection_trials.first()
            return reverse("task_manager:reflection_annotation", args=[trial_to_annotate.id])
    except ObjectDoesNotExist:
        return None

    return None
