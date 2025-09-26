#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from datetime import timedelta

user_group_list = (
    ('admin', u'Admin'),
    ('normal_user', u'User'),
)


class User(AbstractUser):
    LLM_FREQUENCY_CHOICES = (
        ('', u''),
        ('frequently', u'Several times a day'),
        ('usually', u'Once per day'),
        ('sometimes', u'Several times a week'),
        ('rarely', u'Less than once a week'),
    )
    LLM_HISTORY_CHOICES = (
        ('', u''),
        ('very long', u'five years or longer'),
        ('long', u'three to five years'),
        ('short', u'one to three years'),
        ('very short', u'less than one year'),
    )

    # Inherits username, password, email, first_name, last_name, is_staff, is_active, date_joined, last_login from AbstractUser.
    # We are adding the following fields to the default User model.

    name = models.CharField(max_length=50, blank=True)
    sex = models.CharField(max_length=50, blank=True)
    age = models.IntegerField(default=0)
    phone = models.CharField(max_length=50, blank=True)
    occupation = models.CharField(max_length=50, blank=True)
    llm_frequency = models.CharField(max_length=50, choices=LLM_FREQUENCY_CHOICES, blank=True)
    llm_history = models.CharField(max_length=50, choices=LLM_HISTORY_CHOICES, blank=True)
    login_num = models.IntegerField(default=0)

    # No need for custom manager, USERNAME_FIELD, or REQUIRED_FIELDS as AbstractUser provides sensible defaults.
    # 'username' is the default USERNAME_FIELD.
    # 'email' is in REQUIRED_FIELDS by default.


def get_password_reset_token_expiry_date():
    return timezone.now() + timedelta(hours=30)


class ResetPasswordRequest(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expire = models.DateTimeField(default=get_password_reset_token_expiry_date)

    @property
    def is_expired(self):
        return timezone.now() > self.expire




