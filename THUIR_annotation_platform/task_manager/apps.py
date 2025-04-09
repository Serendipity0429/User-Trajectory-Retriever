from django.apps import AppConfig

class TaskManagerConfig(AppConfig):
    name = 'task_manager'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from task_manager.models import Task
        # Judge if Task Table already exists
        if not hasattr(Task, 'objects'):
            return
        Task.objects.filter(active=True).update(active=False)
