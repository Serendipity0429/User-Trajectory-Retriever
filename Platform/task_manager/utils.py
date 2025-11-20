#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from openai import OpenAI
from rest_framework.response import Response
from django.http import HttpResponse
from django.conf import settings
import logging
from datetime import datetime
from django.utils import timezone
import re
import httpx
from dateutil.parser import parse as parse_date, ParserError
import redis

from .models import Task, Webpage, TaskDataset, TaskDatasetEntry

try:
    import simplejson as json
except ImportError:
    import json
import time
import base64
import zlib
import uuid
from urllib.parse import urlparse
from django.urls import reverse
from .models import Task, TaskTrial
from django.core.exceptions import ObjectDoesNotExist

# Redis client instance
redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

def get_annotation_state(user_id):
    """Helper to get annotation state from Redis, initializing if not present."""
    state_key = f"annotation_state:{user_id}"
    state = redis_client.get(state_key)
    if state:
        state = json.loads(state)
    else:
        state = {}

    if not isinstance(state, dict):  # Ensure it's a dictionary
        state = {}
    
    # Set defaults for any missing keys
    state.setdefault('is_annotating', False)
    state.setdefault('is_storing_data', False)
    state.setdefault('annotation_name', 'none')
    state.setdefault('annotation_start_time', None)
    state.setdefault('annotation_id', None)
    state.setdefault('last_webpage_id', None)
    state.setdefault('last_webpage_url', None)
    
    return state

def set_annotation_state(user_id, state):
    """Helper to save annotation state back to Redis."""
    state_key = f"annotation_state:{user_id}"
    redis_client.set(state_key, json.dumps(state))

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
    user_id = request.user.id
    state = get_annotation_state(user_id)
    state['annotation_start_time'] = time.time()
    state['annotation_name'] = name
    state['is_annotating'] = True
    state['annotation_id'] = str(uuid.uuid4())
    set_annotation_state(user_id, state)
    print_debug(f"Started annotating for {name} with ID {state['annotation_id']}.")
    return state['annotation_id']

def stop_annotating(request, annotation_id=None):
    user_id = request.user.id
    state = get_annotation_state(user_id)
    if annotation_id and annotation_id != state.get('annotation_id'):
        print_debug(f"Annotation ID mismatch. Expected {state.get('annotation_id')}, got {annotation_id}. Not stopping.")
        return False
    
    state['annotation_start_time'] = None
    state['annotation_name'] = 'none'
    state['is_annotating'] = False
    state['annotation_id'] = None
    state['last_webpage_id'] = None
    state['last_webpage_url'] = None
    set_annotation_state(user_id, state)
    print_debug("Stopped annotating.")
    return True
    
def store_data(request, message, user):
    user_id = user.id
    state = get_annotation_state(user_id)
    state['is_storing_data'] = True
    set_annotation_state(user_id, state)
    
    print_json_debug(message)
    if message['url'].startswith(settings.IP_TO_LAUNCH):
        print_debug("Skipping storing data for local URL:", message['url'])
        state['is_storing_data'] = False
        set_annotation_state(user_id, state)
        return
    task = Task.objects.filter(user=user, active=True).first()
    if not task:
        print_debug("No active task found for user", user.username)
        state['is_storing_data'] = False
        set_annotation_state(user_id, state)
        return

    # Check for the most recent webpage for this task from Redis
    last_webpage_id = state.get('last_webpage_id')
    last_webpage_url = state.get('last_webpage_url')
    
    sent_when_active = message.get('sent_when_active', False)
    print_debug("Annotating:", state['is_annotating'] and not sent_when_active)  
            
    should_merge = False
    if last_webpage_id and last_webpage_url == message['url']:
        should_merge = True

    if should_merge:
        try:
            last_webpage = Webpage.objects.get(id=last_webpage_id, belong_task=task)
            last_webpage_is_annotating = last_webpage.during_annotation
            if last_webpage_is_annotating == state['is_annotating']:
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
                should_merge = False
        except Webpage.DoesNotExist:
            should_merge = False # Fallback to create a new one
    
    if not should_merge:
        print_debug(f"Creating new webpage entry for URL: {message['url']}")
        webpage = Webpage()
        if check_is_redirected_page(message):
            print_debug("Redirect detected, setting is_redirected to True")
            webpage.is_redirected = True
        
        webpage.during_annotation = state['is_annotating'] and not sent_when_active
        webpage.annotation_name = state['annotation_name'] if webpage.during_annotation else 'none'
        webpage.user = user
        
        webpage.belong_task = task
        webpage.title = message['title']
        webpage.url = message['url']
        webpage.referrer = message['referrer']
        webpage.start_timestamp = timezone.make_aware(datetime.fromtimestamp(message['start_timestamp'] / 1000))
        webpage.end_timestamp = timezone.make_aware(datetime.fromtimestamp(message['end_timestamp'] / 1000))
        webpage.dwell_time = message['dwell_time']
        webpage.page_switch_record = message['page_switch_record']
        webpage.mouse_moves = message['mouse_moves']
        webpage.event_list = message['event_list']
        webpage.rrweb_record = message['rrweb_record'].replace(
                    "</script>", "<\\/script>"
            )
        webpage.save()
        state['last_webpage_id'] = webpage.id
        state['last_webpage_url'] = webpage.url

    state['is_storing_data'] = False
    set_annotation_state(user_id, state)
    
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
            user_id = request.user.id
            # Sleep for a short duration to ensure the backend receives the data
            time.sleep(0.3)
            state = get_annotation_state(user_id)
            while state.get('is_storing_data', False):
                print_debug("Waiting for data to be stored...")
                time.sleep(0.5)
                state = get_annotation_state(user_id)  # Re-fetch state
        
        return func(*args, **kwargs)
    return wrapper


def _normalize(text):
    try:
        if not text.isdigit() and len(text) > 3:
            dt = parse_date(text, fuzzy=False) # Strict Parsing
            # Standardize the date format. Using day is important for specific dates.
            return dt.strftime('%Y %m %d')
    except (ParserError, ValueError):
        # If it's not a date, or if there's an error, fall back to original normalization.
        pass

    text = text.lower()
    # Eliminate punctuation except periods (since periods in numbers is important e.g. 397 and 3.97)
    text = re.sub(r'[^\w\s.]', '', text) 
    # Remove the ending period
    text = re.sub(r'\.$', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text

def check_answer_rule(question, authentic_answers, user_answer):
    print_debug("Question:", question)
    print_debug("User Answer:", user_answer)
    print_debug("Correct Answer List:", authentic_answers)

    # Fallback to original normalization logic
    normalized_user_answer = _normalize(user_answer)
    print_debug(f"Normalized User Answer: '{normalized_user_answer}'")

    for answer in authentic_answers:
        normalized_correct_answer = _normalize(answer)
        print_debug(f"Comparing with normalized correct answer: '{normalized_correct_answer}'")
        if normalized_user_answer == normalized_correct_answer:
            return True
        
    return False


def check_answer_llm(question, authentic_answers, user_answer):
    """
    Checks if the user's answer is correct using an LLM-as-a-judge.
    """
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")

    if not base_url or not api_key:
        raise ValueError("LLM_BASE_URL and LLM_API_KEY environment variables must be set.")

    client = OpenAI(base_url=base_url, api_key=api_key)

    prompt = f"""You are a meticulous and strict evaluator. Your sole task is to compare a `User's Answer` to an `Authentic Answer` for a given `Question` and determine if the user's answer is correct.

**Instructions:**
1.  **Strictly Adhere to Provided Information:** Base your judgment *only* on the text provided in the `Authentic Answer`. Do not use any external knowledge or make assumptions.
2.  **Semantic Equivalence:** The `User's Answer` is considered correct if it is semantically equivalent to the `Authentic Answer`. This means it conveys the same meaning, even if the wording is different.
3.  **Completeness:** The `User's Answer` must be complete. A partially correct answer is considered incorrect.
4.  **Output Format:** Your response must be a single word: either `yes` or `no`. Do not provide any explanation or other text.

**Evaluation Task:**

**Question:** "{question}"

**Authentic Answer:** "{"; ".join(authentic_answers)}"

**User's Answer:** "{user_answer}"

Is the user's answer correct?
"""

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    judgment = completion.choices[0].message.content.strip().lower()
    print_debug(f"LLM response: {judgment}")

    return judgment == "yes"


def check_answer(entry, user_answer, llm = True):
    try:
        authentic_answers = json.loads(entry.answer)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON: {entry.answer}")
        return False
    question = entry.question

    if llm:
        return check_answer_llm(question, authentic_answers, user_answer)
    else:
        return check_answer_rule(question, authentic_answers, user_answer)

from django.shortcuts import render

def close_window():
    return HttpResponse('<html><body><script>window.close()</script></body></html>')

def render_status_page(request, title, message, alert_type='info'):
    context = {
        'title': title,
        'message': message,
        'alert_type': alert_type,
    }
    return render(request, "status_page.html", context)

def get_active_task_dataset(user=None):
    if user and not user.is_superuser:
        tutorial_dataset_name = "tutorial"
        tutorial_dataset = TaskDataset.objects.filter(name=tutorial_dataset_name).first()
        if tutorial_dataset:
            # Check if user has finished tutorial
            # Get all entries in tutorial
            tutorial_entries = TaskDatasetEntry.objects.filter(belong_dataset=tutorial_dataset).values_list('id', flat=True)
            # Get all entries user has interacted with
            user_interacted_entries = Task.objects.filter(user=user, content__belong_dataset=tutorial_dataset).values_list('content_id', flat=True)
            
            # If there are any tutorial entries not in user_interacted_entries, then tutorial is not finished
            if set(tutorial_entries) - set(user_interacted_entries):
                return tutorial_dataset

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
    # Check for pending post-task annotations
    try:
        pending_post_task = Task.objects.filter(
            user=user, active=False, cancelled=False, posttaskannotation__isnull=True, cancelannotation__isnull=True
        ).first()
        if pending_post_task:
            return reverse("task_manager:post_task_annotation", args=[pending_post_task.id])

        # Check for pending reflection annotations
        pending_reflection_trials = TaskTrial.objects.filter(
            belong_task__user=user, belong_task__cancelled=False, is_correct=False, reflectionannotation__isnull=True
        ).order_by('end_timestamp')

        if pending_reflection_trials.exists():
            trial_to_annotate = pending_reflection_trials.first()
            return reverse("task_manager:reflection_annotation", args=[trial_to_annotate.id])
    except ObjectDoesNotExist:
        return None

    return None
