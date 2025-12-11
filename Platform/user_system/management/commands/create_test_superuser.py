from django.core.management.base import BaseCommand
from user_system.models import User, InformedConsent
import random


class Command(BaseCommand):
    help = "Create a test superuser with a complete profile and specified username and password"

    def add_arguments(self, parser):
        parser.add_argument(
            "username", type=str, help="The username for the test superuser"
        )
        parser.add_argument(
            "password", type=str, help="The password for the test superuser"
        )
        parser.add_argument(
            "--email",
            type=str,
            help="The email for the test superuser",
            default="admin@example.com",
        )
        parser.add_argument(
            "--primary",
            action="store_true",
            help="Set the new superuser as the primary superuser",
        )

    def handle(self, *args, **kwargs):
        username = kwargs["username"]
        password = kwargs["password"]
        email = kwargs["email"]
        is_primary = kwargs["primary"]

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists."))
            return

        if is_primary:
            User.objects.filter(is_primary_superuser=True).update(
                is_primary_superuser=False
            )

        user = User.objects.create_superuser(
            username=username, email=email, password=password
        )
        user.consent_agreed = True
        user.agreed_consent_version = InformedConsent.get_latest()
        user.save()

        profile = user.profile
        profile.name = "Admin User"
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

        if is_primary:
            user.is_primary_superuser = True
            user.save()

        self.stdout.write(
            self.style.SUCCESS(f"Superuser '{username}' created successfully.")
        )
        if is_primary:
            self.stdout.write(
                self.style.SUCCESS(
                    f"User '{username}' has been set as the primary superuser."
                )
            )
