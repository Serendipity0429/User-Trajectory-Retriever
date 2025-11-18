from django.core.management.base import BaseCommand
from user_system.models import User

class Command(BaseCommand):
    help = 'Create a test superuser with a complete profile and specified username and password'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username for the test superuser')
        parser.add_argument('password', type=str, help='The password for the test superuser')
        parser.add_argument('--email', type=str, help='The email for the test superuser', default='admin@example.com')
        parser.add_argument('--primary', action='store_true', help='Set the new superuser as the primary superuser')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        password = kwargs['password']
        email = kwargs['email']
        is_primary = kwargs['primary']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists."))
            return

        if is_primary:
            User.objects.filter(is_primary_superuser=True).update(is_primary_superuser=False)

        user = User.objects.create_superuser(username=username, email=email, password=password)
        
        profile = user.profile
        profile.name = "Admin User"
        profile.gender = "O"
        profile.age = 30
        profile.phone = "0987654321"
        profile.occupation = "other"
        profile.education = "phd"
        profile.field_of_expertise = "System Administration"
        profile.llm_frequency = "frequently"
        profile.llm_history = "very long"
        profile.english_proficiency = "fluent"
        profile.web_search_proficiency = "expert"
        profile.web_agent_familiarity = "very_familiar"
        profile.web_agent_frequency = "frequently"
        profile.save()
        
        if is_primary:
            user.is_primary_superuser = True
            user.save()

        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created successfully."))
        if is_primary:
            self.stdout.write(self.style.SUCCESS(f"User '{username}' has been set as the primary superuser."))
