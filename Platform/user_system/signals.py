from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import User

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    user.login_num += 1
    user.save()
