from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Bulletin
from msg_system.models import Message
from user_system.models import User

@receiver(post_save, sender=Bulletin)
def notify_users_on_new_bulletin(sender, instance, created, **kwargs):
    if created:
        all_users = User.objects.exclude(is_superuser=True)
        subject = f"New Bulletin: {instance.title}"
        body = f"A new bulletin has been posted in the '{instance.category}' category. You can view it in the discussion forum."
        
        # Assuming there's a superuser to be the sender
        admin_user = User.objects.filter(is_superuser=True).first()
        
        if admin_user:
            messages_to_create = [
                Message(
                    sender=admin_user,
                    recipient=user,
                    subject=subject,
                    body=body
                )
                for user in all_users
            ]
            Message.objects.bulk_create(messages_to_create)
