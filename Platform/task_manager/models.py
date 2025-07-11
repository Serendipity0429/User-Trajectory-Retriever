#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from user_system.models import User

try:
    import simplejson as json
except ImportError:
    import json
 

# Task Dataset
class TaskDataset(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=1000)
    path = models.CharField(max_length=1000)


class TaskDatasetEntry(models.Model):
    id = models.AutoField(primary_key=True)
    belong_dataset = models.ForeignKey(
        TaskDataset,
        on_delete=models.CASCADE,
    )
    question = models.CharField(max_length=10000)
    answer = models.JSONField()

    num_associated_tasks = models.IntegerField(default=0)  # number of tasks associated with this entry


# Task
class Task(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    # basic information
    cancelled = models.BooleanField(default=False)  # whether the task is cancelled
    active = models.BooleanField(default=True)  # whether the task is active
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField(null=True)

    # task content
    content = models.ForeignKey(
        TaskDatasetEntry,
        on_delete=models.CASCADE,
        null=True,
    )

    # trial-and-error
    num_trial = models.IntegerField(default=0)  # number of trials


# Pre-task annotation
class PreTaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )

    description = models.CharField(max_length=1000, null=True)
    completion_criteria = models.CharField(max_length=1000, null=True)
    familiarity = models.IntegerField(null=True)  # 0->4, unfamiliar -> familiar
    difficulty = models.IntegerField(null=True)  # 0->4, easy -> hard
    effort = models.IntegerField(null=True)  # time effort to complete the task, 3 to 60
    
    initial_strategy = models.TextField(null=True)  # initial strategy to solve the task

# Reflection annotation
class ReflectionAnnotation(models.Model):
    id = models.AutoField(primary_key=True)

    failure_reason = models.CharField(max_length=10000) # reason for failure
    failure_category = models.CharField(max_length=100)  # category of failure, e.g. "lack of resources", "lack of knowledge", etc.
    future_plan_actions = models.CharField(max_length=100)  # actions to take in the future
    future_plan_other = models.TextField(null=True)  # other future plan actions
    remaining_effort = models.IntegerField()  # remaining effort to complete the task, 3 to 60

    additional_reflection = models.TextField(null=True)  # additional reflection on the task

# Post-task annotation
class PostTaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )

    difficulty_actual = models.IntegerField(null=True)  # 0->4, easy -> hard
    
    aha_moment_type = models.CharField(max_length=100, null=True)  # type of aha moment, e.g. "insight", "realization", etc.
    aha_moment_other = models.TextField(null=True)  # other type of aha moment
    aha_moment_source = models.TextField(null=True)  # source of aha moment, e.g. "webpage", "trial-and-error", etc.

    unhelpful_paths = models.JSONField(null=True)  # paths that were not helpful, e.g. ["path1", "path2"]
    unhelpful_paths_other = models.TextField(null=True)  # other unhelpful paths

    strategy_shift = models.CharField(max_length=100, null=True)  # strategy shift during the task
    strategy_shift_other = models.TextField(null=True)  # other strategy shift
        
    additional_reflection = models.TextField(null=True)  # reflection on the task

    # If task is cancelled
    cancel_category = models.CharField(max_length=100, null=True)  # refer to post_task_annotation.html
    cancel_reason = models.CharField(max_length=10000, null=True)  # reason for cancellation
    cancel_reflection = models.TextField(null=True)  # reflection on cancellation
    cancel_missing_resources = models.CharField(max_length=10000, null=True)  # missing resources that led to cancellation
    cancel_missing_resources_other = models.TextField(null=True)  # other missing resources
    cancel_additional_reflection = models.TextField(null=True)  # additional reflection on cancellation


# Task Trial
class TaskTrial(models.Model):
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()
    num_trial = models.IntegerField()  # number of trials

    answer = models.CharField(max_length=1000)
    is_correct = models.BooleanField(default=False)
    
    confidence = models.IntegerField()  # confidence level, 0->4, low -> high
    source_url_and_text = models.JSONField()
    reasoning_method = models.CharField(max_length=100)  # reasoning method used, e.g. "deductive", "inductive", etc.
    
    additional_explanation = models.TextField(null=True)  # explanation of the answer

    reflection_annotation = models.ForeignKey(
        ReflectionAnnotation,
        on_delete=models.CASCADE,
        null=True,
    )

    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )


# Webpages
class Webpage(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )
    belong_task_trial = models.ForeignKey(
        TaskTrial,
        on_delete=models.CASCADE,
        null=True,
    )


    title = models.CharField(max_length=100)
    url = models.CharField(max_length=1000)
    html = models.TextField()  # HTML content of the webpage
    referrer = models.CharField(max_length=1000)
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()
    dwell_time = models.IntegerField()
    mouse_moves = models.TextField()  # mouse move data in JSON format
    event_list = models.TextField()  # list of events in JSON format
    rrweb_events = models.TextField()  # rrweb events in JSON format
    
    is_redirected = models.BooleanField(default=False)  # whether the webpage is redirected


# Annotation of certain behaviors
# e.g. click, hover, scroll, etc.
class EventAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )

    annotation_status = models.BooleanField(default=False)

    type = models.CharField(max_length=50)
    target = models.CharField(max_length=50)
    timestamp = models.IntegerField()
    detail = models.CharField(max_length=1000)  # description of the event
    is_key_event = models.BooleanField(default=False)  # whether this event is a key event
    remarks = models.CharField(max_length=1000)  # remarks of the event
