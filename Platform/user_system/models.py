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
    extension_session_token = models.CharField(max_length=255, blank=True, null=True)
    last_login_from = models.GenericIPAddressField(blank=True, null=True)
    consent_agreed = models.BooleanField(default=False)
    agreed_consent_version = models.ForeignKey(
        'InformedConsent',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users'
    )

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
        ('frequently', u'Many times a day'),
        ('usually', u'About daily'),
        ('sometimes', u'A few times a week'),
        ('rarely', u'Less than weekly'),
    )
    LLM_HISTORY_CHOICES = (
        ('', u''),
        ('very short', u'less than one year'),
        ('short', u'one to three years'),
        ('long', u'three to five years'),
        ('very long', u'five years or longer'),
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
    ENGLISH_PROFICIENCY_CHOICES = (
        ('', u''),
        ('native', 'Native Speaker'),
        ('fluent', 'Fluent'),
        ('advanced', 'Advanced'),
        ('intermediate', 'Intermediate'),
        ('beginner', 'Beginner'),
    )
    WEB_SEARCH_PROFICIENCY_CHOICES = (
        ('', u''),
        ('expert', 'Expert'),
        ('advanced', 'Advanced'),
        ('intermediate', 'Intermediate'),
        ('beginner', 'Beginner'),
    )
    WEB_AGENT_FAMILIARITY_CHOICES = (
        ('', u''),
        ('not_familiar', 'Not familiar at all'),
        ('slightly_familiar', 'Slightly familiar'),
        ('moderately_familiar', 'Moderately familiar'),
        ('very_familiar', 'Very familiar'),
        ('expert', 'Expert'),
    )
    WEB_AGENT_FREQUENCY_CHOICES = (
        ('', u''),
        ('frequently', u'Many times a day'),
        ('usually', u'About daily'),
        ('sometimes', u'A few times a week'),
        ('rarely', u'Less than weekly'),
        ('never', u'Never'),
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
    english_proficiency = models.CharField(max_length=50, choices=ENGLISH_PROFICIENCY_CHOICES, blank=True)
    web_search_proficiency = models.CharField(max_length=50, choices=WEB_SEARCH_PROFICIENCY_CHOICES, blank=True)
    web_agent_familiarity = models.CharField(max_length=50, choices=WEB_AGENT_FAMILIARITY_CHOICES, blank=True)
    web_agent_frequency = models.CharField(max_length=50, choices=WEB_AGENT_FREQUENCY_CHOICES, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'


DEFAULT_CONSENT_CONTENT = """# Informed Consent Form

## Introduction
Welcome to our research study. Please read this document carefully before deciding to participate.

## Purpose
This study aims to understand user behavior in web search and interaction.

## Procedures
If you agree to participate, you will perform specific tasks on the web while your interactions are recorded.

## Data Collection
We will record your:

+ Browser interactions (clicks, scrolls, keystrokes)

+ Web pages visited during the tasks

## Confidentiality
All data collected will be anonymized and used solely for research purposes.

## Voluntary Participation
Your participation is voluntary, and you may withdraw at any time.

## Contact
If you have any questions, please contact the research team.
"""

class InformedConsent(models.Model):
    version = models.PositiveIntegerField(default=1, unique=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Informed Consent v{self.version}"

    @classmethod
    def get_latest(cls):
        obj = cls.objects.order_by('-version').first()
        if obj:
            return obj
        return cls(version=1, content=DEFAULT_CONSENT_CONTENT)