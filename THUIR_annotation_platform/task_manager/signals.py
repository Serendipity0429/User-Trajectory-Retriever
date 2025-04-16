from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Task
from django.db.models import F

@receiver(post_delete, sender=Task)
def update_num_associated_tasks(sender, instance, **kwargs):
    entry = instance.task_content
    if entry:
        # Decrement the num_associated_tasks field of the TaskDatasetEntry model
        entry.num_associated_tasks = F('num_associated_tasks') - 1
        entry.save()
