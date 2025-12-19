#!/usr/bin/env python
# -*- coding: utf-8 -*-
from decouple import config
from openai import OpenAI
from django.http import HttpResponse
from django.conf import settings
import logging
from datetime import datetime
from django.utils import timezone
import re
from dateutil.parser import parse as parse_date, ParserError
from django.shortcuts import render
import random

from .models import Task, Webpage, TaskDataset, TaskDatasetEntry

import time
import uuid
import json
import zlib
import base64
from django.urls import reverse
from .models import TaskTrial
from django.core.exceptions import ObjectDoesNotExist
from core.utils import redis_client, print_debug, print_json_debug, decompress_json_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    state.setdefault("is_annotating", False)
    state.setdefault("annotation_name", "none")
    state.setdefault("annotation_start_time", None)
    state.setdefault("annotation_id", None)
    state.setdefault("last_webpage_id", None)
    state.setdefault("last_webpage_url", None)
    state.setdefault("last_start_timestamp", None)

    return state


def set_annotation_state(user_id, state):
    """Helper to save annotation state back to Redis."""
    state_key = f"annotation_state:{user_id}"
    redis_client.set(state_key, json.dumps(state))

def start_annotating(request, name):
    user_id = request.user.id
    state = get_annotation_state(user_id)
    state["annotation_start_time"] = time.time()
    state["annotation_name"] = name
    state["is_annotating"] = True
    state["annotation_id"] = str(uuid.uuid4())
    set_annotation_state(user_id, state)
    print_debug(f"Started annotating for {name} with ID {state['annotation_id']}.")
    return state["annotation_id"]


def stop_annotating(request, annotation_id=None):
    user_id = request.user.id
    state = get_annotation_state(user_id)
    if annotation_id and annotation_id != state.get("annotation_id"):
        print_debug(
            f"Annotation ID mismatch. Expected {state.get('annotation_id')}, got {annotation_id}. Not stopping."
        )
        return False

    state["annotation_start_time"] = None
    state["annotation_name"] = "none"
    state["is_annotating"] = False
    state["annotation_id"] = None
    state["last_webpage_id"] = None
    state["last_webpage_url"] = None
    state["last_start_timestamp"] = None
    set_annotation_state(user_id, state)
    print_debug("Stopped annotating.")
    return True


def append_json_data(existing_json_str, new_json_str):
    if not existing_json_str or existing_json_str in ("[]", "{}"):
        return new_json_str
    if not new_json_str or new_json_str in ("[]", "{}"):
        return existing_json_str

    try:
        existing_data = json.loads(existing_json_str)
        new_data = json.loads(new_json_str)

        if isinstance(existing_data, list) and isinstance(new_data, list):
            existing_data.extend(new_data)
            return json.dumps(existing_data)
    except json.JSONDecodeError:
        # Handle cases where one of the strings is not valid JSON
        return existing_json_str  # Or some other fallback

    # Fallback for non-list JSON or other structures, though lists are expected
    return existing_json_str


def safe_int(val):
    """
    Safely convert a value to an integer within the standard 32-bit signed integer range.
    Returns None if conversion fails. Clamps values that exceed limits.
    """
    try:
        val = int(val)
        # Standard 32-bit signed integer range
        MAX_INT = 2147483647
        MIN_INT = -2147483648
        if val > MAX_INT:
            return MAX_INT
        if val < MIN_INT:
            return MIN_INT
        return val
    except (ValueError, TypeError):
        return None


def acquire_lock(lock_key, timeout=30, wait_time=0.1):
    """
    Attempts to acquire a Redis lock.
    Returns True if acquired, False if timed out.
    """
    expires = time.time() + timeout
    while time.time() < expires:
        if redis_client.set(lock_key, 1, nx=True, ex=timeout):
            return True
        time.sleep(wait_time)
    return False


def store_data(request, message, user):
    user_id = user.id
    lock_key = f"data_store_lock:{user_id}"

    # Attempt to acquire lock
    if not acquire_lock(lock_key):
        logger.warning(f"Could not acquire data store lock for user {user.username}. Dropping packet.")
        return

    try:
        state = get_annotation_state(user_id)

        print_json_debug(message)
        if message["url"].startswith(settings.IP_TO_LAUNCH):
            print_debug("Skipping storing data for local URL:", message["url"])
            return

        task = Task.objects.filter(user=user, active=True).first()
        if not task:
            print_debug("No active task found for user", user.username)
            return

        last_webpage_id = state.get("last_webpage_id")
        last_webpage_url = state.get("last_webpage_url")
        last_start_timestamp = state.get("last_start_timestamp")
        start_ts = message.get("start_timestamp")

        webpage = None
        if (
            last_webpage_id
            and last_webpage_url == message["url"]
            and last_start_timestamp == start_ts
        ):
            try:
                webpage = Webpage.objects.get(id=last_webpage_id, belong_task=task)
            except Webpage.DoesNotExist:
                pass  # Will create a new one

        is_new_webpage = not webpage

        if is_new_webpage:
            print_debug(f"Creating new webpage entry for URL: {message['url']}")
            webpage = Webpage()
            webpage.user = user
            webpage.belong_task = task
            # Truncate fields to fit database constraints
            webpage.url = message["url"][:4096]
            webpage.title = (
                message.get("title")[:1024] if message.get("title") else None
            )
            webpage.referrer = (
                message.get("referrer")[:4096] if message.get("referrer") else None
            )

            webpage.width = safe_int(message.get("width"))
            webpage.height = safe_int(message.get("height"))

            webpage.start_timestamp = (
                timezone.make_aware(datetime.fromtimestamp(start_ts / 1000))
                if start_ts
                else timezone.now()
            )
            webpage.end_timestamp = webpage.start_timestamp

            webpage.dwell_time = 0
            webpage.page_switch_record = "[]"
            webpage.mouse_moves = "[]"
            webpage.event_list = "[]"
            webpage.rrweb_record = "[]"

            sent_when_active = message.get("sent_when_active", False)
            webpage.during_annotation = (
                state.get("is_annotating", False) and not sent_when_active
            )
            webpage.annotation_name = (
                state.get("annotation_name", "none")
                if webpage.during_annotation
                else "none"
            )
        else:
            print_debug(f"Merging data for URL: {message['url']}")

        # Common logic for both CREATE and MERGE
        raw_rrweb = message.get("rrweb_record", "[]")
        new_rrweb_record = raw_rrweb.replace("</script>", "<\\/script>")

        # Optimize rrweb_record storage with compression
        existing_rrweb = []
        try:
            if isinstance(webpage.rrweb_record, str):
                if webpage.rrweb_record and webpage.rrweb_record not in ("[]", "{}"):
                    existing_rrweb = json.loads(webpage.rrweb_record)
            elif isinstance(webpage.rrweb_record, dict) and webpage.rrweb_record.get(
                "compressed"
            ):
                compressed_data = webpage.rrweb_record["data"]
                decompressed_str = zlib.decompress(
                    base64.b64decode(compressed_data)
                ).decode("utf-8")
                existing_rrweb = json.loads(decompressed_str)
            elif isinstance(webpage.rrweb_record, list):
                existing_rrweb = webpage.rrweb_record
        except Exception as e:
            logger.error(f"Error parsing existing rrweb_record: {e}")
            existing_rrweb = []

        new_rrweb_list = []
        try:
            if new_rrweb_record and new_rrweb_record not in ("[]", "{}"):
                new_rrweb_list = json.loads(new_rrweb_record)
        except Exception as e:
            logger.error(f"Error parsing new rrweb_record: {e}")

        if new_rrweb_list:
            existing_rrweb.extend(new_rrweb_list)

        # Compress and save based on setting
        should_compress = getattr(settings, "ENABLE_RRWEB_COMPRESSION", True)
        
        try:
            if should_compress:
                final_json_str = json.dumps(existing_rrweb)
                compressed_str = base64.b64encode(
                    zlib.compress(final_json_str.encode("utf-8"))
                ).decode("utf-8")
                webpage.rrweb_record = {"compressed": True, "data": compressed_str}
            else:
                webpage.rrweb_record = json.dumps(existing_rrweb)
        except Exception as e:
            logger.error(f"Error saving rrweb_record (compress={should_compress}): {e}")
            # Fallback to uncompressed if compression fails
            webpage.rrweb_record = json.dumps(existing_rrweb)

        webpage.event_list = append_json_data(
            webpage.event_list, message.get("event_list", "[]")
        )
        webpage.mouse_moves = append_json_data(
            webpage.mouse_moves, message.get("mouse_moves", "[]")
        )

        is_routine_update = message.get("is_routine_update", False)
        if not is_routine_update:
            if message.get("end_timestamp"):
                webpage.end_timestamp = timezone.make_aware(
                    datetime.fromtimestamp(message["end_timestamp"] / 1000)
                )

            webpage.dwell_time = safe_int(
                message.get("dwell_time", webpage.dwell_time)
            )
            webpage.page_switch_record = message.get(
                "page_switch_record", webpage.page_switch_record
            )

            if check_is_redirected_page(webpage):
                webpage.is_redirected = True

        webpage.save()

        if is_new_webpage:
            state["last_webpage_id"] = webpage.id
            state["last_webpage_url"] = webpage.url
            state["last_start_timestamp"] = start_ts
            set_annotation_state(user_id, state)

    finally:
        redis_client.delete(lock_key)  # Always release the lock


def check_is_redirected_page(webpage):
    # A page is considered a redirect if the dwell time is very short (< 500ms) or if there's no user interaction.
    return (
        webpage.dwell_time < 500
        or (webpage.mouse_moves == "[]" and webpage.event_list == "[]")
        or webpage.rrweb_record == "[]"
    )


def wait_until_data_stored(func):
    def wrapper(*args, **kwargs):
        # Find the request object in the arguments
        request = None
        for arg in args:
            if hasattr(arg, "session"):
                request = arg
                break

        if request:
            user_id = request.user.id
            lock_key = f"data_store_lock:{user_id}"

            # Sleep for a short duration to ensure the backend receives the data
            time.sleep(0.3)

            wait_time = 0
            max_wait_time = 30  # Max wait 30 seconds to prevent infinite loops

            while redis_client.exists(lock_key):
                if wait_time >= max_wait_time:
                    logger.error(f"Data store lock wait timeout for user {user_id}")
                    break

                print_debug("Waiting for data to be stored...")
                time.sleep(0.5)
                wait_time += 0.5

        return func(*args, **kwargs)

    return wrapper


def _normalize(text):
    try:
        if not text.isdigit() and len(text) > 3:
            dt = parse_date(text, fuzzy=False)  # Strict Parsing
            # Standardize the date format. Using day is important for specific dates.
            return dt.strftime("%Y %m %d")
    except (ParserError, ValueError):
        # If it's not a date, or if there's an error, fall back to original normalization.
        pass

    text = text.lower()
    # Eliminate punctuation except periods (since periods in numbers is important e.g. 397 and 3.97)
    text = re.sub(r"[^\w\s.]", "", text)
    # Remove the ending period
    text = re.sub(r"\.$", "", text)
    # Normalize whitespace
    text = " ".join(text.split())
    return text


def check_answer_rule(question, authentic_answers, user_answer):
    print_debug("Question:", question)
    print_debug("User Answer:", user_answer)
    print_debug("Correct Answer List:", authentic_answers)

    # Fallback to original normalization logic
    normalized_user_answer = _normalize(user_answer)
    # print_debug(f"Normalized User Answer: '{normalized_user_answer}'")

    for answer in authentic_answers:
        normalized_correct_answer = _normalize(answer)
        # print_debug(
        #     f"Comparing with normalized correct answer: '{normalized_correct_answer}'"
        # )
        if normalized_user_answer == normalized_correct_answer:
            return True

    return False


def check_answer_llm(question, authentic_answers, user_answer, client = None, model=None, max_retries=3):
    """
    Checks if the user's answer is correct using an LLM-as-a-judge.
    """
    if not client:
        base_url = config("LLM_BASE_URL", default=None)
        api_key = config("LLM_API_KEY", default=None)
        model = config("LLM_MODEL", default="gpt-3.5-turbo")

        if not base_url or not api_key:
            raise ValueError(
                "LLM_BASE_URL and LLM_API_KEY environment variables must be set."
            )

        client = OpenAI(base_url=base_url, api_key=api_key)

    authentic_answers_formatted = "\n- ".join(authentic_answers)
    prompt = f"""You are a meticulous and fair evaluator. Your task is to compare a `User's Answer` to a list of `Authentic Answers` for a given `Question` and determine if it is correct.

**Instructions:**
1.  **Correctness Criteria:** The `User's Answer` is correct if it is semantically equivalent to **any one** of the answers in the `Authentic Answers` list.
2.  **Tolerances:** Your comparison must be case-insensitive. You should ignore minor differences in punctuation (e.g., commas, periods) and whitespace. For example, "New York NY" should be considered a match for "New York, NY".
3.  **Completeness:** The user's answer must not be missing essential information. For example, if an authentic answer is "Michael Jordan", "Jordan" would be considered incorrect because it is incomplete.
4.  **Conciseness & Precision:** The `User's Answer` must be the direct, precise answer. It should NOT be a long explanation, a paragraph of deduction, or contain excessive extraneous information. If the answer is buried in a long text, judge it as **incorrect**, even if the correct information is technically present.
5.  **Strict Adherence:** Base your judgment *only* on the provided text. Do not use external knowledge.
6.  **Output Format:** Your response must be a single word: `yes` or `no`. Do not provide any explanation or markdown formatting.

**Evaluation Task:**

**Question:** "{question}"

**Authentic Answers (any of the following are correct):**
- {authentic_answers_formatted}

**User's Answer:** "{user_answer}"

Is the user's answer correct?"""

    try_count = 0
    while try_count < max_retries:
        try_count += 1
        completion = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=0
        )

        judgment = completion.choices[0].message.content.strip().lower()
        print_debug(f"LLM response: {judgment}")

        # Remove markdown and punctuation for a cleaner check
        cleaned_judgment = re.sub(r"[^a-z]", "", judgment)

        if cleaned_judgment == "yes":
            return True
        if cleaned_judgment == "no":
            return False
    
    raise ValueError("LLM did not return a valid judgment after multiple attempts.")


def check_answer(entry, user_answer, llm=True):
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


def reset_states(new_page=True):
    # This script sends a message to our `close_helper.js` content script,
    # which then securely communicates with the background script to close the tab.
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Closing...</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(2px);
                cursor: wait;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                color: #2c3e50;
            }}
            .utrt-spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid #e0e0e0;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                animation: utrt-spin 1s cubic-bezier(0.68, -0.55, 0.27, 1.55) infinite;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            @keyframes utrt-spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .utrt-message {{
                font-size: 18px;
                font-weight: 600;
                letter-spacing: 0.5px;
                text-align: center;
                padding: 0 20px;
                animation: utrt-pulse 2s infinite ease-in-out;
            }}
            @keyframes utrt-pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.7; }}
            }}
        </style>
    </head>
    <body>
        <div class="utrt-spinner"></div>
        <div class="utrt-message">Please wait, this page will close automatically.</div>
        <script>
            function requestClose() {{
                window.postMessage({{ type: "UTR_RESET_STATES_REQUEST", new_page: "{'true' if new_page else 'false'}"}}, "*");
            }}
            requestClose();
            setInterval(requestClose, 500);
        </script>
    </body>
    </html>
    """
    return HttpResponse(html_content)


def render_status_page(request, title, message, alert_type="info"):
    context = {
        "title": title,
        "message": message,
        "alert_type": alert_type,
    }
    return render(request, "status_page.html", context)


def get_active_task_dataset(user=None):
    if user and not user.is_superuser:
        tutorial_dataset_name = "tutorial"
        tutorial_dataset = TaskDataset.objects.filter(
            name=tutorial_dataset_name
        ).first()
        if tutorial_dataset:
            # Check if user has finished tutorial
            # Get all entries in tutorial
            tutorial_entries = TaskDatasetEntry.objects.filter(
                belong_dataset=tutorial_dataset
            ).values_list("id", flat=True)
            # Get all entries user has interacted with
            user_interacted_entries = Task.objects.filter(
                user=user, content__belong_dataset=tutorial_dataset
            ).values_list("content_id", flat=True)

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
            user=user,
            active=False,
            cancelled=False,
            posttaskannotation__isnull=True,
            cancelannotation__isnull=True,
        ).first()
        if pending_post_task:
            return reverse(
                "task_manager:post_task_annotation", args=[pending_post_task.id]
            )

        # Check for pending reflection annotations
        pending_reflection_trials = TaskTrial.objects.filter(
            belong_task__user=user,
            belong_task__cancelled=False,
            is_correct=False,
            reflectionannotation__isnull=True,
        ).order_by("end_timestamp")

        if pending_reflection_trials.exists():
            trial_to_annotate = pending_reflection_trials.first()
            return reverse(
                "task_manager:reflection_annotation", args=[trial_to_annotate.id]
            )
    except ObjectDoesNotExist:
        return None

    return None


def shuffle_choices(choices_map):
    """
    Shuffles the choices for a given map, keeping special keys at the end.
    """
    special_keys = ["other", "no_change", "no_major_roadblocks"]

    # Convert dict items to a list
    items = list(choices_map.items())

    # Separate special items
    special_items = []
    regular_items = []

    for key, value in items:
        if key in special_keys:
            special_items.append((key, value))
        else:
            regular_items.append((key, value))

    # Shuffle regular items
    random.shuffle(regular_items)

    # Combine shuffled regular items with special items at the end
    # Sort special items to have a consistent order (e.g., 'no_change', 'no_major_roadblocks', 'other')
    special_items.sort(key=lambda x: special_keys.index(x[0]))

    shuffled_items = regular_items + special_items

    return shuffled_items
