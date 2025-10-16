from django.core.management.base import BaseCommand, CommandError
from user_system.models import User, ResetPasswordRequest
from user_system.utils import send_reset_password_email
from django.conf import settings

class Command(BaseCommand):
    help = 'Sends a test password reset email to a specified address.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='The email address to send the test email to.')
        parser.add_argument(
            '--domain',
            type=str,
            default='127.0.0.1:8000',
            help='The domain to use for the password reset link.'
        )

    def handle(self, *args, **options):
        email = options['email']
        domain = options['domain']

        try:
            user, created = User.objects.get_or_create(
                username=email.split('@')[0], 
                defaults={'email': email}
            )
            if not created and not user.email:
                user.name = email.split('@')[0]
                user.email = email
                user.save()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully found or created user with email: {email}'))
            
            reset_request = ResetPasswordRequest.objects.create(user=user)
            self.stdout.write(self.style.SUCCESS(f'Generated reset token: {reset_request.token}'))

            send_reset_password_email(domain, reset_request)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully sent a test password reset email to {email}'))

        except Exception as e:
            raise CommandError(f'Failed to send test email. Error: {e}')
