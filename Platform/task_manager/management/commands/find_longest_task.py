from django.core.management.base import BaseCommand
from task_manager.models import Task
from django.db.models import F, DurationField
from django.db.models.functions import Cast


class Command(BaseCommand):
    help = "Find the task with the longest completion time."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.HTTP_INFO("Searching for the longest task..."))

        # Filter for completed, non-cancelled tasks and calculate duration
        longest_task = (
            Task.objects.filter(active=False, cancelled=False)
            .annotate(
                duration=Cast(
                    F("end_timestamp") - F("start_timestamp"), DurationField()
                )
            )
            .order_by("-duration")
            .first()
        )

        if longest_task:
            duration_seconds = longest_task.duration.total_seconds()
            duration_minutes = duration_seconds / 60

            self.stdout.write(self.style.SUCCESS("\n" + "=" * 30))
            self.stdout.write(self.style.SUCCESS("Longest Task Found"))
            self.stdout.write(self.style.SUCCESS("=" * 30))
            self.stdout.write(f"Task ID: {longest_task.id}")
            self.stdout.write(f"User: {longest_task.user.username}")
            self.stdout.write(f"Question: {longest_task.content.question}")
            self.stdout.write(
                f"Duration: {duration_minutes:.2f} minutes ({duration_seconds:.2f} seconds)"
            )
            self.stdout.write("=" * 30)
        else:
            self.stdout.write(
                self.style.WARNING("No completed tasks found to analyze.")
            )
