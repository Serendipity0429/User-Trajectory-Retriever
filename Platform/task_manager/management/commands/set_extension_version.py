from django.core.management.base import BaseCommand
from task_manager.models import ExtensionVersion


class Command(BaseCommand):
    help = "Creates or updates the latest extension version record."

    def add_arguments(self, parser):
        parser.add_argument("version", type=str, help="The version number (e.g., 3.1).")
        parser.add_argument(
            "update_link", type=str, help="The URL for the update page."
        )
        parser.add_argument(
            "description",
            type=str,
            help="A description of the changes in this version.",
        )

    def handle(self, *args, **kwargs):
        version = kwargs["version"]
        update_link = kwargs["update_link"]
        description = kwargs["description"]

        # Delete old versions to ensure only one 'latest' version exists.
        ExtensionVersion.objects.all().delete()

        # Create the new latest version.
        ExtensionVersion.objects.create(
            version=version, update_link=update_link, description=description
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully set extension version to {version}.")
        )
