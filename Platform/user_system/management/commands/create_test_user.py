from django.core.management.base import BaseCommand
from user_system.models import User, InformedConsent, Profile
import random


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
        user.is_test_account = True
        user.save()

        profile = user.profile
        profile.name = "Test User"
        profile.gender = random.choice([c[0] for c in Profile.GENDER_CHOICES if c[0]])
        profile.age = random.randint(18, 80)
        profile.phone = "".join([str(random.randint(0, 9)) for _ in range(10)])
        profile.occupation = random.choice(
            [c[0] for c in Profile.OCCUPATION_CHOICES if c[0]]
        )
        profile.education = random.choice(
            [c[0] for c in Profile.EDUCATION_CHOICES if c[0]]
        )
        profile.field_of_expertise = random.choice(
            [
                "Computer Science",
                "Physics",
                "Literature",
                "Mathematics",
                "Biology",
                "History",
            ]
        )
        profile.llm_frequency = random.choice(
            [c[0] for c in Profile.LLM_FREQUENCY_CHOICES if c[0]]
        )
        profile.llm_history = random.choice(
            [c[0] for c in Profile.LLM_HISTORY_CHOICES if c[0]]
        )
        profile.english_proficiency = random.choice(
            [c[0] for c in Profile.ENGLISH_PROFICIENCY_CHOICES if c[0]]
        )
        profile.web_search_proficiency = random.choice(
            [c[0] for c in Profile.WEB_SEARCH_PROFICIENCY_CHOICES if c[0]]
        )
        profile.web_agent_familiarity = random.choice(
            [c[0] for c in Profile.WEB_AGENT_FAMILIARITY_CHOICES if c[0]]
        )
        profile.web_agent_frequency = random.choice(
            [c[0] for c in Profile.WEB_AGENT_FREQUENCY_CHOICES if c[0]]
        )
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} created successfully with password '{password}'."
            )
        )
