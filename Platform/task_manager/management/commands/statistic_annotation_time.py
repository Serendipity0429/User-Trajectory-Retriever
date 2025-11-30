import csv
from django.core.management.base import BaseCommand
from django.db.models import Sum
from user_system.models import User
from task_manager.models import Task, PreTaskAnnotation, PostTaskAnnotation, CancelAnnotation, ReflectionAnnotation, TaskTrial

class Command(BaseCommand):
    help = "Calculates and prints the total annotation time for each user. Can also save to CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            type=str,
            help='Save the output to a CSV file at the specified path.',
            nargs='?',
            const='annotation_time_stats.csv',
            default=None,
        )

    def handle(self, *args, **options):
        users = User.objects.all()
        results = []

        for user in users:
            total_duration = 0

            # Get all tasks for the user
            tasks = Task.objects.filter(user=user)

            # Pre-task, Post-task, and Cancel annotations
            pre_task_duration = PreTaskAnnotation.objects.filter(belong_task__in=tasks).aggregate(Sum('duration'))['duration__sum'] or 0
            post_task_duration = PostTaskAnnotation.objects.filter(belong_task__in=tasks).aggregate(Sum('duration'))['duration__sum'] or 0
            cancel_task_duration = CancelAnnotation.objects.filter(belong_task__in=tasks).aggregate(Sum('duration'))['duration__sum'] or 0
            
            total_duration += pre_task_duration
            total_duration += post_task_duration
            total_duration += cancel_task_duration

            # Reflection annotations
            task_trials = TaskTrial.objects.filter(belong_task__in=tasks)
            reflection_duration = ReflectionAnnotation.objects.filter(belong_task_trial__in=task_trials).aggregate(Sum('duration'))['duration__sum'] or 0
            total_duration += reflection_duration

            # Always print to console
            self.stdout.write(f"User: {user.username}, Total annotation time: {total_duration} seconds")
            results.append([user.username, total_duration])

        if options['save']:
            file_path = options['save']
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Username', 'Total Annotation Time (seconds)'])
                writer.writerows(results)
            self.stdout.write(self.style.SUCCESS(f"Successfully saved statistics to {file_path}"))
