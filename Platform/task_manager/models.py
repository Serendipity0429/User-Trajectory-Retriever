#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models

from user_system.models import User

import json
 

# Task Dataset
class TaskDataset(models.Model):
    name = models.CharField(max_length=1000)
    path = models.CharField(max_length=1000)


class TaskDatasetEntry(models.Model):
    belong_dataset = models.ForeignKey(
        TaskDataset,
        on_delete=models.CASCADE,
    )
    question = models.TextField()
    answer = models.JSONField()

    num_associated_tasks = models.IntegerField(default=0)  # number of tasks associated with this entry


# Task
class Task(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    # basic information
    cancelled = models.BooleanField(default=False)  # whether the task is cancelled
    active = models.BooleanField(default=True)  # whether the task is active
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField(null=True)

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
    belong_task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
    )


    familiarity = models.IntegerField(null=True)  # 0->4, unfamiliar -> familiar
    difficulty = models.IntegerField(null=True)  # 0->4, easy -> hard
    effort = models.IntegerField(null=True)  # 0->5, time effort category
    
    first_search_query = models.TextField(null=True)  # initial strategy to solve the task

    initial_guess = models.TextField(null=True, blank=True)
    initial_guess_unknown = models.BooleanField(default=False)
    expected_source = models.JSONField(null=True, blank=True)
    expected_source_other = models.TextField(null=True, blank=True)
    submission_timestamp = models.DateTimeField(auto_now_add=True, null=True)
    duration = models.IntegerField(null=True)  # time spent on annotation in seconds

# Reflection annotation
class ReflectionAnnotation(models.Model):
    belong_task_trial = models.OneToOneField(
        'TaskTrial',
        on_delete=models.CASCADE,
    )

    failure_category_other = models.TextField() # reason for failure
    failure_category = models.JSONField(null=True)  # category of failure, e.g. "lack of resources", "lack of knowledge", etc.
    future_plan_actions = models.JSONField(null=True)  # actions to take in the future
    future_plan_other = models.TextField(null=True)  # other future plan actions
    estimated_time = models.IntegerField()  # 0->5, time effort category
    adjusted_difficulty = models.IntegerField(null=True) # user's adjusted difficulty of the task

    additional_reflection = models.TextField(null=True)  # additional reflection on the task
    submission_timestamp = models.DateTimeField(auto_now_add=True, null=True)
    duration = models.IntegerField(null=True)  # time spent on annotation in seconds

# Post-task annotation
class PostTaskAnnotation(models.Model):
    belong_task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
    )

    difficulty_actual = models.IntegerField(null=True)  # 0->4, easy -> hard
    
    aha_moment_type = models.CharField(max_length=100, null=True)  # type of aha moment, e.g. "insight", "realization", etc.
    aha_moment_other = models.TextField(null=True)  # other type of aha moment

    unhelpful_paths = models.JSONField(null=True)  # paths that were not helpful, e.g. ["path1", "path2"]
    unhelpful_paths_other = models.TextField(null=True)  # other unhelpful paths

    strategy_shift = models.JSONField(null=True)  # strategy shift during the task
    strategy_shift_other = models.TextField(null=True)  # other strategy shift
    submission_timestamp = models.DateTimeField(auto_now_add=True, null=True)
    duration = models.IntegerField(null=True)  # time spent on annotation in seconds


# Cancel annotation
class CancelAnnotation(models.Model):
    belong_task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
    )

    category = models.JSONField(null=True)  # refer to post_task_annotation.html
    reason = models.TextField(null=True)  # reason for cancellation
    missing_resources = models.JSONField(null=True)  # missing resources that led to cancellation
    missing_resources_other = models.TextField(null=True)  # other missing resources
    submission_timestamp = models.DateTimeField(auto_now_add=True, null=True)
    duration = models.IntegerField(null=True)  # time spent on annotation in seconds


# Task Trial
class TaskTrial(models.Model):
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField(auto_now=True)
    num_trial = models.IntegerField()  # number of trials

    answer = models.CharField(max_length=1000, default='undefined')
    is_correct = models.BooleanField(null=True)
    
    confidence = models.IntegerField(default=-1)  # confidence level, 0->4, low -> high
    answer_formulation_method = models.CharField(max_length=100, default='undefined')  # reasoning method used, e.g. "deductive", "inductive", etc.
    
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )


# Justification
class Justification(models.Model):
    belong_task_trial = models.ForeignKey(TaskTrial, on_delete=models.CASCADE, related_name='justifications')
    url = models.URLField(max_length=2048)
    page_title = models.CharField(max_length=255, blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    dom_position = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, default='active')  # 'active' or 'abandoned'
    evidence_type = models.CharField(max_length=20, default='text_selection')
    element_details = models.JSONField(null=True, blank=True)
    relevance = models.IntegerField(default=0)
    credibility = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    evidence_image = models.ImageField(upload_to='evidence_images/', null=True, blank=True)

    def __str__(self):
        return f"Justification for Trial {self.belong_task_trial.id} - {self.evidence_type}"


# Webpages
class Webpage(models.Model):
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


    title = models.CharField(max_length=512)
    url = models.URLField(max_length=1000)
    referrer = models.URLField(max_length=1000)
    start_timestamp = models.DateTimeField()
    end_timestamp = models.DateTimeField()
    dwell_time = models.IntegerField()
    page_switch_record = models.JSONField() # page switch record in JSON format
    mouse_moves = models.JSONField()  # mouse move data in JSON format
    event_list = models.JSONField()  # list of events in JSON format
    rrweb_record = models.JSONField()  # rrweb record in JSON forma
    
    is_redirected = models.BooleanField(default=False)  # whether the webpage is redirected
    during_annotation = models.BooleanField(default=False)  # whether the webpage is during annotation
    annotation_name = models.CharField(max_length=100, null=True)  # name of the annotation, e.g. "pre_task", "post_task", etc.


# Annotation of certain behaviors
# e.g. click, hover, scroll, etc.
class EventAnnotation(models.Model):
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )

    annotation_status = models.BooleanField(default=False)

    type = models.CharField(max_length=50)
    target = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    detail = models.CharField(max_length=1000)  # description of the event
    is_key_event = models.BooleanField(default=False)  # whether this event is a key event
    remarks = models.CharField(max_length=1000)  # remarks of the event




class ExtensionVersion(models.Model):
    version = models.CharField(max_length=20)  # e.g., "1.2.3"
    update_link = models.URLField()
    description = models.TextField()

    def __str__(self):
        return self.version


