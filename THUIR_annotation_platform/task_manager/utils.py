#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'defaultstr'

from user_system.models import *
from .models import *

try:
    import simplejson as json
except ImportError:
    import json
import time

ip_to_launch = "http://127.0.0.1:8000/"

__DEBUG__ = True

def store_page_annotation(message, page_id):
    try:
        usefulness_list = message.split('#')[0].split('\t')
        if message.split('#')[1] == '':
            serendipity_list = []
        else:
            serendipity_list = message.split('#')[1].split(',')
        all_results = usefulness_list[0].split(',') + usefulness_list[1].split(',') + usefulness_list[2].split(',')
        non_serendipity = set(all_results).difference(set(serendipity_list))
        non_serendipity.discard("")
        non_serendipity = list(non_serendipity)
        page_log = PageLog.objects.get(id=page_id)
        serp_annotations = SERPAnnotation.objects.filter(serp_log=page_log)
        if serp_annotations:
            serp_annotation = serp_annotations.first()
            serp_annotation.usefulness_0 = usefulness_list[0]
            serp_annotation.usefulness_1 = usefulness_list[1]
            serp_annotation.usefulness_2 = usefulness_list[2]
            serp_annotation.serendipity_0 = ','.join(non_serendipity)
            serp_annotation.serendipity_1 = ','.join(serendipity_list)
        else:
            serp_annotation = SERPAnnotation()
            serp_annotation.serp_log = page_log
            serp_annotation.usefulness_0 = usefulness_list[0]
            serp_annotation.usefulness_1 = usefulness_list[1]
            serp_annotation.usefulness_2 = usefulness_list[2]
            serp_annotation.serendipity_0 = ','.join(non_serendipity)
            serp_annotation.serendipity_1 = ','.join(serendipity_list)
        serp_annotation.save()
    except Exception as e:
        print('exception', e)


def partition(user, query_ids):
    task = TaskAnnotation()
    task.user = user
    task.annotation_status = False
    task.save()
    for query_id in query_ids:
        query_id = int(query_id)
        query = Query.objects.get(id=query_id)
        query.partition_status = True
        query.task_annotation = task
        query.save()
        query__annotation = QueryAnnotation()
        query__annotation.belong_query = query

        query__annotation.relation = -1
        query__annotation.inspiration = -1
        query__annotation.satisfaction = -1
        query__annotation.ending_type = -1
        query__annotation.other_reason = ""
        query__annotation.other_relation = ""
        query__annotation.save()


def delete(user, query_ids):
    for query_id in query_ids:
        query_id = int(query_id)
        query = Query.objects.get(user=user, id=query_id)
        pagelogs = PageLog.objects.filter(user=user, belong_query=query)
        for pagelog in pagelogs:
            pagelog.delete()
        query.delete()


def unpartition(user, task_ids):
    for task_id in task_ids:
        task = TaskAnnotation.objects.get(user=user, id=task_id)
        queries = Query.objects.filter(user=user, partition_status=True, task_annotation=task)
        for query in queries:
            query.partition_status = False
            query.task_annotation = TaskAnnotation.objects.filter(annotation_status=True).first()
            query.save()
            query_annotations = QueryAnnotation.objects.filter(belong_query=query)
            for query_annotation in query_annotations:
                query_annotation.delete()
            pagelogs = PageLog.objects.filter(user=user, belong_query=query)
            for pagelog in pagelogs:
                for serp_annotation in SERPAnnotation.objects.filter(serp_log=pagelog):
                    serp_annotation.delete()
        task.delete()


def clear_expired_query(user):
    unpartition_queries = Query.objects.filter(user=user, partition_status=False)
    for query in unpartition_queries:
        if int(time.time()) - query.life_start > 172800:  # 172800 = 2 days
            pagelogs = PageLog.objects.filter(user=user, belong_query=query)
            for pagelog in pagelogs:
                pagelog.delete()
            query.delete()

    unannotated_tasks = TaskAnnotation.objects.filter(user=user, annotation_status=False)
    for task in unannotated_tasks:
        queries = Query.objects.filter(user=user, partition_status=True, task_annotation=task)
        expired = False
        for query in queries:
            if int(time.time()) - query.life_start > 172800:
                expired = True
                break
        if expired:
            for query in queries:
                for pagelog in PageLog.objects.filter(user=user, belong_query=query):
                    for serp_annotation in SERPAnnotation.objects.filter(serp_log=pagelog):
                        serp_annotation.delete()
                    pagelog.delete()
                query_annotations = QueryAnnotation.objects.filter(belong_query=query)
                for query_annotation in query_annotations:
                    query_annotation.delete()
                query.delete()
            task.delete()


def get_items_list(user, queries):
    items_list = []
    for i in range(len(queries)):
        query = queries[i]
        query__annotation = QueryAnnotation.objects.filter(belong_query=query).first()
        pages = sorted(PageLog.objects.filter(user=user, belong_query=query, page_type='SERP'),
                       key=lambda item: item.start_timestamp)
        pages_and_status = []
        for page in pages:
            if SERPAnnotation.objects.filter(serp_log=page):
                pages_and_status.append((page, True))
            else:
                pages_and_status.append((page, False))
        if i == 0:
            prequery = Query.objects.filter(life_start=0).first()
        else:
            prequery = queries[i - 1]
        items_list.append((query, prequery, query__annotation, pages_and_status))
    return items_list


def check_serp_annotations(user, queries):
    flag = True
    for query in queries:
        pages = sorted(PageLog.objects.filter(user=user, belong_query=query, page_type='SERP'),
                       key=lambda item: item.start_timestamp)
        for page in pages:
            if not SERPAnnotation.objects.filter(serp_log=page):
                flag = False
                break
    return flag


# Refined
def print_debug(*args, **kwargs):
    if __DEBUG__:
        print(*args, **kwargs)

def store_data(message):
    print_debug(json.dumps(message, indent=4))
    webpage = Webpage()
    user = User.objects.get(username=message['username'])
    webpage.user = user
    webpage.title = message['title']
    webpage.url = message['url']
    webpage.referrer = message['referrer']
    webpage.start_timestamp = message['start_timestamp']
    webpage.end_timestamp = message['end_timestamp']
    webpage.dwell_time = message['dwell_time']
    webpage.mouse_moves = message['mouse_moves']
    webpage.event_list = message['event_list']
    task = TaskAnnotation.objects.filter(user=user, active=True).first()
    webpage.belong_task = task
    if not message['url'].startswith(f'{ip_to_launch}'):  # ip_to_launch should be set manually
        webpage.save()

