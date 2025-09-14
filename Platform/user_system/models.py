#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from .forms import *
from hashlib import sha512
from uuid import uuid4
import time

user_group_list = (
    ('admin', u'Admin'),
    ('normal_user', u'User'),
)


class TimestampGenerator(object):

    def __init__(self, seconds=0):
        self.seconds = seconds

    def __call__(self):
        return int(time.time()) + self.seconds


class KeyGenerator(object):

    def __init__(self, length):
        self.length = length

    def __call__(self):
        key = sha512(uuid4().hex.encode('utf-8')).hexdigest()[0:self.length]
        return str(key)


class MyUserManager(BaseUserManager):
    """
    A custom user manager to deal with emails as unique identifiers for auth.
    """
    def create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError('The username must be set')
        user = self.model(username=username, **extra_fields)
        user.set_password(password) # Hashes the password
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    username = models.CharField(unique=True, max_length=50)
    password = models.CharField(max_length=50)

    objects = MyUserManager()

    name = models.CharField(max_length=50)
    sex = models.CharField(max_length=50)
    age = models.IntegerField()
    phone = models.CharField(max_length=50)
    email = models.EmailField()
    field = models.CharField(max_length=50)
    llm_frequency = models.CharField(max_length=50, choices=llm_frequency_choices)
    llm_history = models.CharField(max_length=50, choices=llm_history_choices)
    signup_time = models.DateTimeField()
    last_login = models.DateTimeField()
    login_num = models.IntegerField()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name', 'email']


class ResetPasswordRequest(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        )
    token = models.CharField(max_length=50, default=KeyGenerator(12).__call__())
    expire = models.IntegerField(default=TimestampGenerator(60*60*30).__call__())


