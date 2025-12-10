from django.core.management.base import BaseCommand
from user_system.models import User, InformedConsent


class Command(BaseCommand):
    help = (
        "Create a test user with a complete profile and specified username and password"
    )

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="The username for the test user")
        parser.add_argument("password", type=str, help="The password for the test user")

    def handle(self, *args, **kwargs):
        username = kwargs["username"]
        password = kwargs["password"]
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User {username} already exists, skipping creation.")
            return

        user = User.objects.create_user(
            username=username, password=password, email="test@nowhere.com"
        )
        user.consent_agreed = True
        user.agreed_consent_version = InformedConsent.get_latest()
        user.save()

        profile = user.profile
        profile.name = "Test User"
        profile.gender = "O"
        profile.age = 25
        profile.phone = "1234567890"
        profile.occupation = "engineer"
        profile.education = "master"
        profile.field_of_expertise = "Computer Science"
        profile.llm_frequency = "frequently"
        profile.llm_history = "long"
        profile.english_proficiency = "advanced"
        profile.web_search_proficiency = "advanced"
        profile.web_agent_familiarity = "moderately_familiar"
        profile.web_agent_frequency = "sometimes"
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} created successfully with password '{password}'."
            )
        )
