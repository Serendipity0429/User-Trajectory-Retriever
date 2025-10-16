from django.core.management.base import BaseCommand
from user_system.models import User

class Command(BaseCommand):
    help = 'Create a test user with a complete profile and specified username and password'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username for the test user')
        parser.add_argument('password', type=str, help='The password for the test user')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        password = kwargs['password']
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User {username} already exists, skipping creation.")
            return
        
        user = User()
        user.username = username
        user.set_password(password)
        user.name = "Test User"
        user.gender = "O"
        user.email = "test@nowhere.com"
        user.age = 25
        user.phone = "1234567890"
        user.occupation = "engineer"
        user.education = "master"
        user.field_of_expertise = "Computer Science"
        user.llm_frequency = "frequently"
        user.llm_history = "long"
        user.is_staff = False
        user.is_superuser = False
        user.save()
        self.stdout.write(self.style.SUCCESS(f"User {username} created successfully with password '{password}'."))

