import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from dotenv import load_dotenv

load_dotenv()


class Command(BaseCommand):
    help = "Creates a superuser from environment variables (ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD)."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("ADMIN_USERNAME")
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")

        if not all([username, email, password]):
            self.stdout.write(
                self.style.ERROR(
                    "Please set ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD in your .env file."
                )
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{username}" already exists.')
            )
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully.')
        )
