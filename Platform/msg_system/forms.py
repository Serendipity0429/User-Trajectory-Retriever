from django import forms
from .models import Message
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class MessageForm(forms.ModelForm):
    recipients = forms.CharField(widget=forms.HiddenInput(), required=False)
    send_to_all = forms.BooleanField(required=False, label="Send to all users")
    is_pinned = forms.BooleanField(required=False, label="Pin this message")

    class Meta:
        model = Message
        fields = ["subject", "body", "level"]

    def clean_recipients(self):
        recipient_ids_str = self.cleaned_data.get("recipients", "")
        if not recipient_ids_str:
            return []

        recipient_ids = [
            int(uid) for uid in recipient_ids_str.split(",") if uid.strip()
        ]
        recipients = User.objects.filter(pk__in=recipient_ids)

        if len(recipient_ids) != recipients.count():
            raise ValidationError("Invalid recipient selected.")

        return recipients

    def clean(self):
        cleaned_data = super().clean()
        # The clean_recipients method will be called automatically by Django's form processing.
        recipients = cleaned_data.get("recipients", [])
        send_to_all = cleaned_data.get("send_to_all")

        if not recipients and not send_to_all:
            raise ValidationError(
                "You must select at least one recipient or check 'Send to all users'."
            )

        return cleaned_data


class ReplyMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["subject", "body"]
