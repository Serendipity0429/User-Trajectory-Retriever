from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from user_system.utils import check_password_strength

class Command(BaseCommand):
    help = "Reset all users' passwords to [email_user]Thu1234!"

    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()
        count = 0
        
        self.stdout.write("Starting password reset process...")

        for user in users:
            # Skip admin and test users
            if user.is_superuser or user.is_primary_superuser or user.is_test_account or user.is_staff:
                self.stdout.write(self.style.WARNING(f"Skipping admin/test user {user.username}"))
                continue

            if not user.email:
                self.stdout.write(self.style.WARNING(f"Skipping user {user.username}: No email address"))
                continue
                
            try:
                email_user = user.email.split('@')[0]
                if not email_user:
                     self.stdout.write(self.style.WARNING(f"Skipping user {user.username}: Invalid email format '{user.email}'"))
                     continue

                new_password = f"{email_user}Thu1234!"
                
                # Verify password strength
                is_valid, msg = check_password_strength(new_password)
                if not is_valid:
                    self.stdout.write(self.style.ERROR(f"Skipping user {user.username}: Generated password '{new_password}' is invalid: {msg}"))
                    continue

                user.set_password(new_password)
                user.save()
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error resetting password for {user.username}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully reset passwords for {count} users."))
