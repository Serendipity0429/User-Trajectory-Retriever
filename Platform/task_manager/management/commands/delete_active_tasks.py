from django.core.management.base import BaseCommand
from task_manager.models import Task
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all active tasks to allow users to perform them again."

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            active_tasks = Task.objects.filter(active=True)
            num_deleted = active_tasks.count()

            if num_deleted == 0:
                self.stdout.write(self.style.SUCCESS("No active tasks to delete."))
                return

            self.stdout.write(f"Found {num_deleted} active tasks to delete.")

            for task in active_tasks:
                self.stdout.write(
                    f"Deleting task {task.id} for user {task.user.username}..."
                )
                task.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {num_deleted} active tasks.")
        )
