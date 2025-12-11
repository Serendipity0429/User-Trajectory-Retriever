import random
import string
from django.core.management.base import BaseCommand
from django.db import transaction
from user_system.models import User, Profile, InformedConsent


class Command(BaseCommand):
    help = "Generates dummy users with random profile data for testing analysis."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            help="Number of dummy users to create.",
            default=10,
        )

    def handle(self, *args, **options):
        count = options["count"]
        created_count = 0

        # Helper function to extract keys from choices, excluding empty ones
        def get_keys(choices):
            return [c[0] for c in choices if c[0]]

        self.stdout.write("Starting generation of dummy users...")

        try:
            with transaction.atomic():
                for i in range(count):
                    # Generate a unique username suffix
                    suffix = "".join(
                        random.choices(string.ascii_lowercase + string.digits, k=8)
                    )
                    username = f"dummy_user_{suffix}"

                    if User.objects.filter(username=username).exists():
                        continue

                    # Create User
                    user = User.objects.create_user(
                        username=username,
                        email=f"{username}@example.com",
                        password="password123",  # Default password for all dummy users
                    )

                    # Handle Consent
                    user.consent_agreed = True
                    user.agreed_consent_version = InformedConsent.get_latest()
                    user.save()

                    # Randomize Profile
                    profile = user.profile

                    profile.name = f"Dummy User {suffix}"
                    profile.gender = random.choice(get_keys(Profile.GENDER_CHOICES))
                    profile.age = random.randint(18, 80)
                    profile.phone = "".join(
                        [str(random.randint(0, 9)) for _ in range(10)]
                    )
                    profile.occupation = random.choice(
                        get_keys(Profile.OCCUPATION_CHOICES)
                    )
                    profile.education = random.choice(
                        get_keys(Profile.EDUCATION_CHOICES)
                    )
                    
                    # Add signature to field_of_expertise for robust identification
                    random_expertise = random.choice(
                        [
                            "Computer Science",
                            "Physics",
                            "Literature",
                            "Mathematics",
                            "Biology",
                            "History",
                            "Psychology",
                            "Economics",
                            "Art",
                        ]
                    )
                    profile.field_of_expertise = f"[SYSTEM_GENERATED] {random_expertise}"
                    
                    profile.llm_frequency = random.choice(
                        get_keys(Profile.LLM_FREQUENCY_CHOICES)
                    )
                    profile.llm_history = random.choice(
                        get_keys(Profile.LLM_HISTORY_CHOICES)
                    )
                    profile.english_proficiency = random.choice(
                        get_keys(Profile.ENGLISH_PROFICIENCY_CHOICES)
                    )
                    profile.web_search_proficiency = random.choice(
                        get_keys(Profile.WEB_SEARCH_PROFICIENCY_CHOICES)
                    )
                    profile.web_agent_familiarity = random.choice(
                        get_keys(Profile.WEB_AGENT_FAMILIARITY_CHOICES)
                    )
                    profile.web_agent_frequency = random.choice(
                        get_keys(Profile.WEB_AGENT_FREQUENCY_CHOICES)
                    )

                    profile.save()
                    created_count += 1

                    if created_count % 10 == 0:
                        self.stdout.write(f"Created {created_count} users...")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating users: {e}"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {created_count} dummy users.")
        )
