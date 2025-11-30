from django.core.management.base import BaseCommand
from user_system.models import User
from msg_system.models import Message
from django.conf import settings


class Command(BaseCommand):
    help = "Sends a test message to specified users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="Send a test message to all users."
        )
        parser.add_argument(
            "--users", nargs="+", type=str, help="Usernames of the recipients."
        )
        parser.add_argument(
            "--group", type=str, help="Send a test message to a group of users."
        )
        parser.add_argument(
            "--level",
            type=str,
            default="INFO",
            help="Set the message level (INFO, WARNING, ERROR, IMPORTANT).",
        )

    def handle(self, *args, **options):
        sender = User.objects.get(username=settings.ADMIN_USERNAME)
        subject = "Test Message"
        body = "This is a test message from the system."
        level = options["level"].upper()

        if level not in ["INFO", "WARNING", "ERROR", "IMPORTANT"]:
            self.stdout.write(
                self.style.ERROR(
                    "Invalid level. Please use INFO, WARNING, ERROR, or IMPORTANT."
                )
            )
            return

        if options["all"]:
            recipients = User.objects.exclude(username=sender.username)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sending message to all {recipients.count()} users."
                )
            )
        elif options["users"]:
            recipients = User.objects.filter(username__in=options["users"])
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sending message to users: {", ".join(options["users"])}'
                )
            )
        elif options["group"]:
            # This is a placeholder for group logic.
            # You would need to have a group model and relationships set up.
            self.stdout.write(
                self.style.WARNING("Group messaging is not yet implemented.")
            )
            return
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify recipients using --all, --users, or --group."
                )
            )
            return

        for recipient in recipients:
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                level=level,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Message sent to {recipient.username}")
            )
