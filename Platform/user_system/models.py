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
    login_num = models.IntegerField(default=0)
    is_primary_superuser = models.BooleanField(default=False)

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


class Profile(models.Model):
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
    GENDER_CHOICES = (
        ('', u''),
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    OCCUPATION_CHOICES = (
        ('', u''),
        ('student', 'Student'),
        ('engineer', 'Engineer'),
        ('teacher', 'Teacher'),
        ('other', 'Other'),
    )
    EDUCATION_CHOICES = (
        ('', u''),
        ('high_school', 'High School'),
        ('bachelor', 'Bachelor\'s Degree'),
        ('master', 'Master\'s Degree'),
        ('phd', 'PhD'),
        ('other', 'Other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    icon = models.ImageField(default='profile_pics/default.jpg', upload_to='profile_pics')
    name = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, blank=True)
    age = models.IntegerField(default=0)
    phone = models.CharField(max_length=50, blank=True)
    occupation = models.CharField(max_length=50, choices=OCCUPATION_CHOICES, blank=True)
    education = models.CharField(max_length=50, choices=EDUCATION_CHOICES, blank=True)
    field_of_expertise = models.CharField(max_length=100, blank=True)
    llm_frequency = models.CharField(max_length=50, choices=LLM_FREQUENCY_CHOICES, blank=True)
    llm_history = models.CharField(max_length=50, choices=LLM_HISTORY_CHOICES, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'