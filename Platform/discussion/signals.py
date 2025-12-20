from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Bulletin, Comment
from msg_system.models import Message, MessageRecipient
from user_system.models import User
from django.db import connection
from msg_system.utils import send_system_message
from django.urls import reverse
from django.db.models import Q
from django.utils import timezone
from django.conf import settings


@receiver(post_save, sender=Comment)
def notify_post_author_on_new_comment(sender, instance, created, **kwargs):
    if created:
        post = instance.post
        author = post.author
        commenter = instance.author

        if author != commenter:
            post_url = reverse("post_detail", args=[post.pk])
            full_post_url = f"{settings.IP_TO_LAUNCH.rstrip('/')}{post_url}"
            subject = f"New comment on your post '{post.title}'"
            body = f"{commenter.username} has commented on your post '{post.title}'.<br><br><a href='{full_post_url}'>View Post</a>"
            send_system_message(author, subject, body)


@receiver(post_save, sender=Bulletin)
def notify_users_on_new_bulletin(sender, instance, created, **kwargs):
    if created and instance.send_notification:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            return

        bulletin_url = reverse("bulletin_detail", args=[instance.pk])
        full_bulletin_url = f"{settings.IP_TO_LAUNCH.rstrip('/')}{bulletin_url}"
        subject = f"New Bulletin: {instance.title}"
        body = f"A new bulletin has been posted in the '{instance.category}' category. You can view it in the discussion forum.<br><br><a href='{full_bulletin_url}' style='color: rgba(var(--bs-link-color-rgb), var(--bs-link-opacity, 1));text-decoration: underline;'>[View Bulletin]{full_bulletin_url}</a>"

        message = Message.objects.create(sender=admin_user, subject=subject, body=body)

        recipients = User.objects.filter(is_superuser=False)
        message_recipients = [
            MessageRecipient(message=message, user=user, is_read=False, is_pinned=False)
            for user in recipients
        ]
        MessageRecipient.objects.bulk_create(message_recipients)


@receiver(post_save, sender=User)
def notify_new_user_of_active_bulletins(sender, instance, created, **kwargs):
    """
    When a new user is created, send them notifications for all currently active bulletins
    that were marked for notification.
    """
    if created and not instance.is_superuser:
        now = timezone.now()
        active_bulletins = Bulletin.objects.filter(send_notification=True).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        )

        for bulletin in active_bulletins:
            bulletin_url = reverse("bulletin_detail", args=[bulletin.pk])
            full_bulletin_url = f"{settings.IP_TO_LAUNCH.rstrip('/')}{bulletin_url}"
            subject = f"New Bulletin: {bulletin.title}"
            body = f"A new bulletin has been posted in the '{bulletin.category}' category. You can view it in the discussion forum.<br><br><a href='{full_bulletin_url}' style='color: rgba(var(--bs-link-color-rgb), var(--bs-link-opacity, 1));text-decoration: underline;'>[View Bulletin]{full_bulletin_url}</a>"
            send_system_message(instance, subject, body)