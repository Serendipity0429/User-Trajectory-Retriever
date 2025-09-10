import json
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from user_system.models import User

class Command(BaseCommand):
    help = 'Create a test user with specified username and password'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('password', type=str)
    def handle(self, *args, **kwargs):
        from user_system.models import User
        username = kwargs['username']
        password = kwargs['password']
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User {username} already exists, skipping creation.")
            return
        user = User()
        user.username = username
        user.password = password
        user.name = "Test User"
        user.sex = "Test"
        user.age = 0
        user.phone = "0000000000"
        user.email = "test@test.com"
        user.occupation = "Tester"
        user.llm_frequency = ''
        user.llm_history = ''
        user.signup_time = now()
        user.last_login = now()
        user.login_num = 0
        user.save()
        self.stdout.write(self.style.SUCCESS(f"User {username} created successfully."))
