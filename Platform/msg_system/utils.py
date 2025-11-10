from .models import Message
from django.contrib.auth import get_user_model

def send_system_message(recipient, subject, body):
    """
    Sends a message from the system admin to a specific user.
    """
    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    
    if not admin_user:
        # Handle case where no admin user is found
        return

    message = Message.objects.create(
        sender=admin_user,
        subject=subject,
        body=body
    )
    message.recipients.add(recipient)
