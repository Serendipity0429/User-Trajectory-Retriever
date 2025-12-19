from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from task_manager.models import Task, TaskDataset, TaskDatasetEntry
from rest_framework_simplejwt.tokens import RefreshToken
import json
import os
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = "Creates multiple users for benchmarking and exports their access tokens."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of users to create.",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default="bench_user",
            help="Prefix for usernames.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="benchmark_tokens.json",
            help="Output file for the tokens.",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Delete all users created with the specified prefix.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        prefix = options["prefix"]

        if options["cleanup"]:
            self.stdout.write(f"Cleaning up users with prefix '{prefix}'...")
            users_to_del = User.objects.filter(username__startswith=prefix)
            count = users_to_del.count()
            users_to_del.delete()
            
            TaskDataset.objects.filter(name="pressure_test_dataset").delete()
            
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {count} benchmark users."))
            return

        count = options["count"]
        output_file = options["output"]

        self.stdout.write(f"Creating {count} users with prefix '{prefix}'...")

        # Setup dataset and task entry once
        dataset, _ = TaskDataset.objects.get_or_create(name="pressure_test_dataset")
        entry, _ = TaskDatasetEntry.objects.get_or_create(
            belong_dataset=dataset,
            question="Pressure Test",
            answer=json.dumps(["Done"]),
        )

        tokens = []

        for i in range(count):
            username = f"{prefix}_{i}"
            password = "password123"
            
            # Create User
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                user = User.objects.create_user(username=username, password=password)
            
            # Ensure Active Task
            Task.objects.update_or_create(
                user=user, active=True, defaults={"content": entry}
            )

            # Generate Token
            refresh = RefreshToken.for_user(user)
            # Manually set expiration to 24 hours from now
            refresh.access_token.set_exp(lifetime=timedelta(hours=24))
            tokens.append(str(refresh.access_token))

            if (i + 1) % 10 == 0:
                self.stdout.write(f"Processed {i + 1} users...")

        # Export to file
        with open(output_file, "w") as f:
            json.dump(tokens, f)

        self.stdout.write(self.style.SUCCESS(f"Successfully exported {len(tokens)} tokens to {output_file}"))
