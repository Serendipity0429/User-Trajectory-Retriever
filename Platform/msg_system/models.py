from django.db import models
from django.conf import settings


class Message(models.Model):
    LEVEL_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="MessageRecipient",
        related_name="received_messages",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="INFO")
    timestamp = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )

    def __str__(self):
        return f"From {self.sender}: {self.subject}"


class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        unique_together = ("message", "user")
