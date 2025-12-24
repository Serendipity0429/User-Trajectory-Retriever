from django.core.management.base import BaseCommand
from task_manager.models import Task
from user_system.models import User

class Command(BaseCommand):
    help = 'Delete tasks based on various criteria'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, help='The ID of the task to delete')
        parser.add_argument('--username', type=str, help='Delete all tasks for a specific username')
        parser.add_argument('--cancelled', action='store_true', help='Delete all cancelled tasks')
        parser.add_argument('--force', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        task_id = options['id']
        username = options['username']
        cancelled = options['cancelled']
        force = options['force']

        if not (task_id or username or cancelled):
            self.stdout.write(self.style.ERROR('Please specify at least one of --id, --username, or --cancelled'))
            return

        tasks = Task.objects.all()

        if username:
            try:
                user = User.objects.get(username=username)
                tasks = tasks.filter(user=user)
                self.stdout.write(f'Filtering by user: {username}')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with username "{username}" does not exist'))
                return

        if task_id:
            tasks = tasks.filter(id=task_id)
            self.stdout.write(f'Filtering by task ID: {task_id}')

        if cancelled:
            tasks = tasks.filter(cancelled=True)
            self.stdout.write('Filtering by cancelled tasks')

        count = tasks.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No tasks found matching the criteria.'))
            return

        if not force:
            confirm = input(f'Are you sure you want to delete {count} tasks? (y/N): ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        tasks.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} tasks.'))
