from django.core.management.base import BaseCommand
from user_system.models import User, InformedConsent
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
        user.save()

        profile = user.profile
        profile.name = "Test User"
        profile.gender = random.choice(["M", "F", "O"])
        profile.age = random.randint(18, 80)
        profile.phone = "".join([str(random.randint(0, 9)) for _ in range(10)])
        profile.occupation = random.choice(
            ["student", "engineer", "teacher", "other"]
        )
        profile.education = random.choice(
            ["high_school", "bachelor", "master", "phd", "other"]
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
            ["frequently", "usually", "sometimes", "rarely"]
        )
        profile.llm_history = random.choice(
            ["very short", "short", "long", "very long"]
        )
        profile.english_proficiency = random.choice(
            ["native", "fluent", "advanced", "intermediate", "beginner"]
        )
        profile.web_search_proficiency = random.choice(
            ["expert", "advanced", "intermediate", "beginner"]
        )
        profile.web_agent_familiarity = random.choice(
            [
                "not_familiar",
                "slightly_familiar",
                "moderately_familiar",
                "very_familiar",
                "expert",
            ]
        )
        profile.web_agent_frequency = random.choice(
            ["frequently", "usually", "sometimes", "rarely", "never"]
        )
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} created successfully with password '{password}'."
            )
        )
