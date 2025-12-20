from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Task, TaskTrial
from django.db.models import F


@receiver(post_delete, sender=Task)
def update_num_associated_tasks(sender, instance, **kwargs):
    entry = instance.content
    if entry:
        # Decrement the num_associated_tasks field of the TaskDatasetEntry model
        entry.num_associated_tasks = F("num_associated_tasks") - 1
        entry.save()


@receiver(post_save, sender=TaskTrial)
def update_num_associated_tasks_submission(sender, instance, **kwargs):
    task = instance.belong_task
    task.num_trial = F("num_trial") + 1  # Increment the number of trials
    task.save()
