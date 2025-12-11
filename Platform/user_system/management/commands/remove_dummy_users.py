from django.core.management.base import BaseCommand
from user_system.models import User

class Command(BaseCommand):
    help = "Removes dummy users created by the generate_dummy_users command."

    def handle(self, *args, **options):
        # Filter for users with BOTH the username prefix AND the profile signature
        # Also ensure we NEVER delete superusers or staff, just in case
        dummy_users = User.objects.filter(
            username__startswith="dummy_user_",
            profile__field_of_expertise__startswith="[SYSTEM_GENERATED]",
            is_superuser=False,
            is_staff=False
        )
        count = dummy_users.count()
        
        if count == 0:
            self.stdout.write("No dummy users found to delete.")
            return

        dummy_users.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {count} dummy users.")
        )
