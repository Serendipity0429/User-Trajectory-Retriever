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

ip_to_launch = "http://127.0.0.1:8000/"

__DEBUG__ = True
is_storing_data = False

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


def store_data(message):
    # is_storing_data = True
    print_json_debug(message)
    if message['url'].startswith(f'{ip_to_launch}'):  # ip_to_launch should be set manually
        print_debug("Skipping storing data for local URL:", message['url'])
        return
    user = User.objects.get(username=message['username'])
    task = Task.objects.filter(user=user, active=True).first()
    if not task:
        print_debug("No active task found for user", user.username)
        return
    # Check whether the webpage already exists
    # existing_webpage = Webpage.objects.filter(
    #     url=message['url'],
    #     belong_task=task,
    #     user=user
    # ).first()
    # webpage = Webpage()
    # if existing_webpage: # if the webpage already exists, update it
    #     webpage = existing_webpage
    
    webpage = Webpage()

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
    webpage.rrweb_events = message['rrweb_events']
    task.end_timestamp = message['end_timestamp']
    
    webpage.save()
    # is_storing_data = False

def check_is_storing_data():
    global is_storing_data
    return is_storing_data

def wait_until_storing_data_done():
    time.sleep(0.3)
    global is_storing_data
    while is_storing_data:
        print_debug("Waiting for storing data to finish...")
        time.sleep(0.3)  # Sleep for a short duration to avoid busy waiting
    print_debug("Storing data finished.")

def check_answer(entry, user_answer):
    try:
        entry_answers = json.loads(entry.answer)
    except json.JSONDecodeError:
        print("Error decoding JSON:", entry.answer)
        return False
    
    print_debug("Question:", entry.question)
    print_debug("User Answer:", user_answer)
    print_debug("Correct Answer:", entry_answers)

    if isinstance(entry_answer, list):
        entry_answers = [str(ans) for ans in entry_answers]
    if isinstance(entry_answer, str):
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
