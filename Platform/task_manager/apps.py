import json

from django.apps import AppConfig


class TaskManagerConfig(AppConfig):
    name = 'task_manager'
    default_auto_field = 'django.db.models.BigAutoField'

    # Load dataset

    def ready(self):
        pass
