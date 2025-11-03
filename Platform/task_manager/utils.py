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
import uuid

def get_annotation_state(request):
    """Helper to get annotation state from session, initializing if not present."""
    state = request.session.get('annotation_state', {})
    if not isinstance(state, dict):  # Ensure it's a dictionary
        state = {}
    
    # Set defaults for any missing keys
    state.setdefault('is_annotating', False)
    state.setdefault('is_storing_data', False)
    state.setdefault('annotation_name', 'none')
    state.setdefault('annotation_start_time', float('inf'))
    state.setdefault('annotation_id', None)
    
    return state

def set_annotation_state(request, state):
    """Helper to save annotation state back to session."""
    request.session['annotation_state'] = state
    request.session.modified = True

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

def start_annotating(request, name):
    state = get_annotation_state(request)
    state['annotation_start_time'] = time.time()
    state['annotation_name'] = name
    state['is_annotating'] = True
    state['annotation_id'] = str(uuid.uuid4())
    set_annotation_state(request, state)
    print_debug(f"Started annotating for {name} with ID {state['annotation_id']}.")
    return state['annotation_id']

def stop_annotating(request, annotation_id=None):
    state = get_annotation_state(request)
    if annotation_id and annotation_id != state.get('annotation_id'):
        print_debug(f"Annotation ID mismatch. Expected {state.get('annotation_id')}, got {annotation_id}. Not stopping.")
        return False
    
    state['annotation_start_time'] = float('inf')
    state['annotation_name'] = 'none'
    state['is_annotating'] = False
    state['annotation_id'] = None
    set_annotation_state(request, state)
    print_debug("Stopped annotating.")
    return True
    
def start_storing_data(request):
    state = get_annotation_state(request)
    state['is_storing_data'] = True
    set_annotation_state(request, state)
    
def stop_storing_data(request):
    state = get_annotation_state(request)
    state['is_storing_data'] = False
    set_annotation_state(request, state)
    
    
def store_data(request, message, user):
    state = get_annotation_state(request)
    state['is_storing_data'] = True
    set_annotation_state(request, state)
    
    print_json_debug(message)
    if message['url'].startswith(settings.IP_TO_LAUNCH):
        print_debug("Skipping storing data for local URL:", message['url'])
        state['is_storing_data'] = False
        set_annotation_state(request, state)
        return
    task = Task.objects.filter(user=user, active=True).first()
    if not task:
        print_debug("No active task found for user", user.username)
        state['is_storing_data'] = False
        set_annotation_state(request, state)
        return

    from urllib.parse import urlparse

    # Check for the most recent webpage for this task
    last_webpage = Webpage.objects.filter(belong_task=task).order_by('-end_timestamp').first()

    should_merge = False
    if last_webpage:
        try:
            last_url = last_webpage.url
            current_origin = message['url']
            if last_url == current_origin:
                should_merge = True
        except Exception as e:
            print_debug(f"Could not parse URL to determine origin: {e}")

    if should_merge:
        print_debug(f"Merging data for URL: {message['url']}")
        last_webpage.end_timestamp = timezone.make_aware(datetime.fromtimestamp(message['end_timestamp'] / 1000))
        last_webpage.dwell_time += message['dwell_time']
        
        # Append events, handling potential empty or invalid JSON
        try:
            existing_events = json.loads(last_webpage.event_list) if last_webpage.event_list else []
            new_events = json.loads(message['event_list']) if message['event_list'] else []
            last_webpage.event_list = json.dumps(existing_events + new_events)
        except json.JSONDecodeError:
            print_debug("Could not decode existing event_list, overwriting.")
            last_webpage.event_list = message['event_list']

        try:
            existing_rrweb = json.loads(last_webpage.rrweb_record) if last_webpage.rrweb_record else []
            new_rrweb = json.loads(message['rrweb_record']) if message['rrweb_record'] else []
            last_webpage.rrweb_record = json.dumps(existing_rrweb + new_rrweb)
        except json.JSONDecodeError:
            print_debug("Could not decode existing rrweb_record, overwriting.")
            last_webpage.rrweb_record = message['rrweb_record']
            
        last_webpage.save()
    else:
        print_debug(f"Creating new webpage entry for URL: {message['url']}")
        webpage = Webpage()
        if check_is_redirected_page(message):
            print_debug("Redirect detected, setting is_redirected to True")
            webpage.is_redirected = True
        
        sent_when_active = message.get('sent_when_active', False)
        
        print_debug("Annotating:", state['is_annotating'] and not sent_when_active)  
        webpage.during_annotation = state['is_annotating'] and not sent_when_active
        webpage.annotation_name = state['annotation_name']
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
        webpage.rrweb_record = message['rrweb_record'].replace(
                    "</script>", "<\\/script>"
            )
        webpage.save()

    task.end_timestamp = timezone.make_aware(datetime.fromtimestamp(message['end_timestamp'] / 1000))
    task.save()
    stop_storing_data(request)
    
def check_is_redirected_page(message):
    # A page is considered a redirect if the dwell time is very short (< 1000ms) or if there's no user interaction.
    return message['dwell_time'] < 1000 or (message['mouse_moves'] == '[]' and message['rrweb_record'] == '[]' and message['event_list'] == '[]') or message['title'] == '' or 'redirect' in message['title'].lower()

def wait_until_data_stored(func):
    def wrapper(*args, **kwargs):
        # Find the request object in the arguments
        request = None
        for arg in args:
            if hasattr(arg, 'session'):
                request = arg
                break
        
        if request:
            # Sleep for a short duration to ensure the backend receives the data
            time.sleep(0.3)
            state = get_annotation_state(request)
            while state.get('is_storing_data', False):
                print_debug("Waiting for data to be stored...")
                time.sleep(0.5)
                state = get_annotation_state(request)  # Re-fetch state
        
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
            user=user, active=False, cancelled=False, posttaskannotation__isnull=True, cancelannotation__isnull=True
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
