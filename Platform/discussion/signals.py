from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Bulletin, Comment
from msg_system.models import Message, MessageRecipient
from user_system.models import User
from django.db import connection
from msg_system.utils import send_system_message


@receiver(post_save, sender=Comment)
def notify_post_author_on_new_comment(sender, instance, created, **kwargs):
    if created:
        post = instance.post
        author = post.author
        commenter = instance.author

        if author != commenter:
            subject = f"New comment on your post '{post.title}'"
            body = f"{commenter.username} has commented on your post '{post.title}'."
            send_system_message(author, subject, body)


@receiver(post_save, sender=Bulletin)
def notify_users_on_new_bulletin(sender, instance, created, **kwargs):
    if created and instance.send_notification:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            return

        subject = f"New Bulletin: {instance.title}"
        body = f"A new bulletin has been posted in the '{instance.category}' category. You can view it in the discussion forum."

        message = Message.objects.create(sender=admin_user, subject=subject, body=body)

        recipient_table = MessageRecipient._meta.db_table
        user_table = User._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {recipient_table} (message_id, user_id, is_read, is_pinned)
                SELECT %s, id, false, false
                FROM {user_table}
                WHERE is_superuser = false
            """,
                [message.id],
            )
