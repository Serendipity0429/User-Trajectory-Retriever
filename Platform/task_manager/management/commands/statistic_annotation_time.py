import csv
import datetime
from django.core.management.base import BaseCommand
from user_system.models import User
from task_manager.models import Task

class Command(BaseCommand):
    help = "Calculates and prints the total effort time for each user by summing up the duration of all their tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            type=str,
            help='Save the output to a CSV file at the specified path.',
            nargs='?',
            const='total_effort_time.csv',
            default=None,
        )

    def handle(self, *args, **options):
        users = User.objects.all()
        results = []

        for user in users:
            total_effort_duration = datetime.timedelta(0)
            
            # Get all tasks for the user that are completed or cancelled
            tasks = Task.objects.filter(user=user, active=False)

            for task in tasks:
                if task.start_timestamp and task.end_timestamp:
                    duration = task.end_timestamp - task.start_timestamp
                    total_effort_duration += duration
            
            total_seconds = total_effort_duration.total_seconds()
            self.stdout.write(f"User: {user.username}, Total Effort Time: {total_seconds/60:.2f} minutes")
            results.append([user.username, total_seconds])

        if options['save']:
            file_path = options['save']
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Username', 'Total Effort Time (seconds)'])
                # Format to 2 decimal places for consistency
                formatted_results = [[res[0], f"{res[1]:.2f}"] for res in results]
                writer.writerows(formatted_results)
            self.stdout.write(self.style.SUCCESS(f"Successfully saved statistics to {file_path}"))
