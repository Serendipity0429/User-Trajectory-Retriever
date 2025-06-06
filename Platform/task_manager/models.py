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
    difficulty = models.IntegerField()  # 0->4, easy -> hard
    effort = models.IntegerField()  # 0->4, low -> high

# Reflection annotation
class ReflectionAnnotation(models.Model):
    id = models.AutoField(primary_key=True)

    failure_reason = models.CharField(max_length=10000) # reason for failure
    future_plan = models.CharField(max_length=10000) # future adjustments and plans

# Post-task annotation
class PostTaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    belong_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
    )

    expertise = models.IntegerField()  # 0->4, unfamiliar -> familiar
    reflection = models.CharField(max_length=10000, null=True)  # reflection on the task

    # If task is cancelled
    cancel_reason = models.CharField(max_length=10000, null=True)  # reason for cancellation
    cancel_reflection = models.CharField(max_length=10000, null=True)  # reflection on cancellation


# Task Trial
class TaskTrial(models.Model):
    id = models.AutoField(primary_key=True)
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()
    num_trial = models.IntegerField()  # number of trials

    answer = models.CharField(max_length=10000)
    is_correct = models.BooleanField(default=False)

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


    title = models.CharField(max_length=100)
    url = models.CharField(max_length=1000)
    referrer = models.CharField(max_length=1000)
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()
    dwell_time = models.IntegerField()
    mouse_moves = models.CharField(max_length=1000000)
    event_list = models.CharField(max_length=1000000)
    rrweb_events = models.CharField(max_length=100000000)


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
