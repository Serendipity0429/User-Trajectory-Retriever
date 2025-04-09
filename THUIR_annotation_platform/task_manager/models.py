#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from user_system.models import User

try:
    import simplejson as json
except ImportError:
    import json


class TaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )

    active = models.BooleanField(default=True) # whether the task is active

    # user intent
    specificity = models.IntegerField(default=-1)  # 0 ==> 4, broad ==> clear
    trigger = models.IntegerField(default=-1)  # 0 ==> 4, interest-driven ==> task-driven
    expertise = models.IntegerField(default=-1)  # 0 ==> 4, unfamiliar ==> familiar

    # search scenario
    time_condition = models.IntegerField(default=-1)  # 0 ==> 4, relax ==> tense
    position_condition = models.IntegerField(default=-1)  # 0 ==> 4, quiet ==> noisy

    # search task experience
    satisfaction = models.IntegerField(default=-1)
    information_difficulty = models.IntegerField(default=-1)
    success = models.IntegerField(default=-1)

    annotation_status = models.BooleanField(default=False)


class Query(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )
    task_annotation = models.ForeignKey(
        TaskAnnotation,
        on_delete=models.CASCADE,
        null=True,        )

    partition_status = models.BooleanField(default=False)
    annotation_status = models.BooleanField(default=False)

    query_string = models.CharField(max_length=1000)
    start_timestamp = models.IntegerField()
    life_start = models.IntegerField()

    # reformulation interface
    # 1: SERP inputbox, 2: SERP related queries (query suggestion),
    # 3: SERP related entities, 4: top searched queries, 5: others (other pages, sponsored search, ads)
    interface = models.IntegerField(default=1)

    # user expectation, pre-query
    diversity = models.IntegerField(default=-1)  # 0->4
    habit = models.CharField(max_length=50)  #
    redundancy = models.IntegerField(default=-1)  # 0->4
    difficulty = models.IntegerField(default=-1)  # 0->4
    gain = models.IntegerField(default=-1)  # 0->9
    effort = models.IntegerField(default=-1)  # 0->9

    # user expectation confirmation, post-query
    diversity_confirm = models.IntegerField(default=-1)
    habit_confirm = models.CharField(max_length=50)
    redundancy_confirm = models.IntegerField(default=-1)
    difficulty_confirm = models.IntegerField(default=-1)
    gain_confirm = models.IntegerField(default=-1)
    effort_confirm = models.IntegerField(default=-1)


class PageLog(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )
    belong_query = models.ForeignKey(
        Query,
        on_delete=models.CASCADE,
        null=True,
        )
    page_type = models.CharField(max_length=50)
    page_title = models.CharField(max_length=50)
    origin = models.CharField(max_length=50)
    url = models.CharField(max_length=1000)
    referrer = models.CharField(max_length=1000)
    serp_link = models.CharField(max_length=1000)
    html = models.CharField(max_length=1000000)
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField()
    dwell_time = models.IntegerField()
    page_timestamps = models.CharField(max_length=1000000)
    query_string = models.CharField(max_length=1000)
    page_id = models.IntegerField()
    mouse_moves = models.CharField(max_length=1000000)
    event_list = models.CharField(max_length=1000000)


class QueryAnnotation(models.Model):  # !!
    id = models.AutoField(primary_key=True)
    belong_query = models.ForeignKey(
        Query,
        on_delete=models.CASCADE,
        )
    # 1--initial, 2--spec, 3--gen, 4--meronym 5--holonym, 6--synonym, 7--parallel moving, 8--intent shift, 0--others
    relation = models.IntegerField()
    # 1--initial query ,2--SERP search snippets, 3--SERP other components,
    # 4--landing pages, 5--others (not acquired during search)
    inspiration = models.IntegerField()
    satisfaction = models.IntegerField()
    ending_type = models.IntegerField()  # 4--sat, 3--dissat, 2--new, 1-intent shift, 0--others
    other_reason = models.CharField(max_length=1000)
    other_relation = models.CharField(max_length=1000)


class SERPAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    serp_log = models.ForeignKey(
        PageLog,
        on_delete=models.CASCADE,
        )
    usefulness_0 = models.CharField(max_length=1000)
    usefulness_1 = models.CharField(max_length=1000)
    usefulness_2 = models.CharField(max_length=1000)

    serendipity_0 = models.CharField(max_length=1000)
    serendipity_1 = models.CharField(max_length=1000)


# Pre-task annotation
class PreTaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    annotation_status = models.BooleanField(default=False)

    description = models.CharField(max_length=1000)
    completion_criteria = models.CharField(max_length=1000)
    target_type = models.CharField(max_length=100)
    difficulty = models.IntegerField()  # 0->4, easy -> hard
    effort = models.IntegerField()  # 0->4, low -> high

# Post-task annotation
class PostTaskAnnotation(models.Model):
    id = models.AutoField(primary_key=True)
    annotation_status = models.BooleanField(default=False)

    completion_reason = models.CharField(max_length=1000) # why user chooses to end the task
    completion_level = models.IntegerField() # 0->4, not completed -> fully completed
    time_condition = models.IntegerField() # 0->4, urgent -> relaxed
    specificity = models.IntegerField() # 0->4, broad -> clear
    trigger = models.IntegerField() # 0->4, interest-driven -> task-driven
    expertise = models.IntegerField() # 0->4, unfamiliar -> familiar


# Task
class Task(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )

    # basic information
    active = models.BooleanField(default=True) # whether the task is active
    start_timestamp = models.IntegerField()
    end_timestamp = models.IntegerField(null=True)

    # pre-task annotation
    pre_annotation = models.ForeignKey(
        PreTaskAnnotation,
        related_name='pre_annotation',
        on_delete=models.CASCADE,
        null=True,
        )

    # post-task annotation
    post_annotation = models.ForeignKey(
        PostTaskAnnotation,
        on_delete=models.CASCADE,
        null=True,
        )

    need_update_pre_annotation = models.BooleanField(null=True) # whether the pre-task annotation needs to be updated
    updated_pre_annotation = models.ForeignKey(
        PreTaskAnnotation,
        related_name='updated_pre_annotation',
        on_delete=models.CASCADE,
        null=True,
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
    is_key_event = models.BooleanField(default=False) # whether this event is a key event
    remarks = models.CharField(max_length=1000)  # remarks of the event