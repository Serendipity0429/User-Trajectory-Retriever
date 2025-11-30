from django.core.management.base import BaseCommand
from user_system.models import User, Profile
from django.db.utils import IntegrityError


class Command(BaseCommand):
    help = "Ensures every user has a profile."

    def handle(self, *args, **options):
        users_without_profile = User.objects.filter(profile__isnull=True)
        count = 0
        for user in users_without_profile:
            try:
                Profile.objects.create(user=user)
                count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created profile for {user.username}"
                    )
                )
            except IntegrityError:
                self.stdout.write(
                    self.style.WARNING(
                        f"Profile already existed for {user.username} (race condition)."
                    )
                )

        if count == 0:
            self.stdout.write(self.style.SUCCESS("All users already have profiles."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Finished creating {count} missing profiles.")
            )
