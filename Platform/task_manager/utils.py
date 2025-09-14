#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'defaultstr'

from django.http import HttpResponse

from .models import *

try:
    import simplejson as json
except ImportError:
    import json
import time
import base64
import zlib

ip_to_launch = "http://127.0.0.1:8000/"

__DEBUG__ = True
is_annotating = False
is_storing_data = False
annotation_name = 'none'
annotation_start_time = float('inf')

# Refined
def print_debug(*args, **kwargs):
    if __DEBUG__:
        print(*args, **kwargs)


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
    global is_annotating
    global annotation_name
    global annotation_start_time
    annotation_start_time = time.time()
    annotation_name = name
    is_annotating = True
    print_debug(f"Started annotating for {name}.")
    
def stop_annotating():
    global is_annotating
    global annotation_name
    global annotation_start_time
    annotation_start_time = float('inf')
    annotation_name = 'none'
    is_annotating = False
    
    print_debug("Stopped annotating.")

def store_data(message, user):
    global is_storing_data
    is_storing_data = True
    
    print_json_debug(message)
    if message['url'].startswith(f'{ip_to_launch}'):  # ip_to_launch should be set manually
        print_debug("Skipping storing data for local URL:", message['url'])
        return
    task = Task.objects.filter(user=user, active=True).first()
    if not task:
        print_debug("No active task found for user", user.username)
        return
    
    webpage = Webpage()
    if message['mouse_moves'] == '[]' or message['rrweb_record'] == '[]':
        print_debug("Redirect detected, setting is_redirected to True")
        webpage.is_redirected = True
    
    sent_when_active = message.get('sent_when_active', False)
    
    print_debug("Annotating:", is_annotating and not sent_when_active)  
    webpage.during_annotation = is_annotating and not sent_when_active
    webpage.annotation_name = annotation_name
    
    webpage.belong_task = task
    webpage.user = user
    webpage.title = message['title']
    webpage.url = message['url']
    webpage.referrer = message['referrer']
    webpage.start_timestamp = message['start_timestamp']
    webpage.end_timestamp = message['end_timestamp']
    webpage.dwell_time = message['dwell_time']
    webpage.mouse_moves = message['mouse_moves']
    webpage.event_list = message['event_list']
    # Replace the problematic string to prevent premature script tag closure in the template.
    # The sequence '<\/script>' is safe for HTML parsers but correctly interpreted by JavaScript.
    webpage.rrweb_record = message['rrweb_record'].replace(
                "</script>", "<\\/script>"
        )
    task.end_timestamp = message['end_timestamp']
    
    webpage.save()
    is_storing_data = False
    
def wait_until_data_stored(func):
    def wrapper(*args, **kwargs):
        while is_storing_data:
            print_debug("Waiting for data to be stored...")
            time.sleep(0.1)
        return func(*args, **kwargs)
    return wrapper


def check_answer(entry, user_answer):
    try:
        entry_answers = json.loads(entry.answer)
    except json.JSONDecodeError:
        print("Error decoding JSON:", entry.answer)
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
