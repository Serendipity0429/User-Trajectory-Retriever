#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from .forms import *
from .models import User, ResetPasswordRequest
from .utils import *
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
import logging
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm


@csrf_exempt
def token_login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    username = request.POST.get('username')
    password = request.POST.get('password')

    # Assuming 'authenticate' is a custom utility function you have defined in utils.py
    # from .utils import authenticate
    error_code, user = authenticate(username, password)

    if error_code == 0 and user:
        # Authentication successful, generate JWT token
        logging.debug(f'User {username} authenticated successfully for token login')
        refresh = RefreshToken.for_user(user)
        user.login_num += 1
        user.last_login = now()
        user.save()

        return JsonResponse({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    else:
        logging.debug(f'User {username} authentication failed with error code {error_code}')
        error_messages = {
            1: 'User does not exist',
            2: 'Incorrect password',
        }
        return JsonResponse({
            'error': error_messages.get(error_code, 'Authentication failed'),
            'error_code': error_code
        }, status=401)


def login(request):
    form = AuthenticationForm(request, data=request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        auth_login(request, user)  # user_logged_in signal will be triggered here
        return redirect_to_prev_page(request, reverse('task_manager:home'))
    elif request.method == 'POST':
        error_message = "Invalid username or password."

    return render(
        request,
        'login.html',
        {
            'form': form,
            'error_message': error_message,
        }
    )


def signup(request):
    form = UserCreationForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        form.save()
        return HttpResponseRedirect(reverse('user_system:login'))
    elif request.method == 'POST':
        error_message = form.errors

    return render(
        request,
        'signup.html',
        {'form': form,
         'error_message': error_message,
        }
        )


def logout(request):
    auth_logout(request)
    return HttpResponseRedirect(reverse('user_system:login'))


@login_required
def info(request):
    return render(
        request,
        'info.html',
        {
            'cur_user': request.user,
        }
        )


@login_required
def edit_info(request):
    if request.method == 'POST':
        form = EditInfoForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('user_system:info'))
    else:
        form = EditInfoForm(instance=request.user)

    return render(
        request,
        'edit_info.html',
        {
            'cur_user': request.user,
            'form': form,
        }
    )


@login_required
def edit_password(request):
    form = EditPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        if request.user.check_password(form.cleaned_data['cur_password']):
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save()
            return HttpResponseRedirect(reverse('user_system:info'))
        else:
            error_message = 'Incorrect current password.'
    elif request.method == 'POST':
        error_message = form.errors


    return render(
        request,
        'edit_password.html',
        {
            'cur_user': request.user,
            'form': form,
            'error_message': error_message,
        }
        )


def forget_password(request):
    form = ForgetPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        try:
            user = User.objects.get(email=form.cleaned_data['email'])
            reset_request = ResetPasswordRequest.objects.create(user=user)
            # Assuming send_reset_password_email is a utility function you have defined
            # from .utils import send_reset_password_email
            send_reset_password_email(request, reset_request)
            return HttpResponseRedirect(reverse('user_system:login'))
        except User.DoesNotExist:
            error_message = 'Email address not found.'
    elif request.method == 'POST':
        error_message = form.errors

    return render(
        request,
        'forget_password.html',
        {
            'form': form,
            'error_message': error_message,
        }
        )


def reset_password(request, token_str):
    token = get_object_or_404(ResetPasswordRequest, token=token_str)
    
    if token.is_expired:
        return render(
            request,
            'reset_password.html',
            {
                'form': None,
                'error_message': 'This token has expired. Please request a new password reset.'
            }
        )

    form = ResetPasswordForm(request.POST or None)
    error_message = None

    if request.method == 'POST' and form.is_valid():
        user = token.user
        user.set_password(form.cleaned_data['new_password'])
        user.save()
        token.delete()
        return HttpResponseRedirect(reverse('user_system:login'))
    elif request.method == 'POST':
        error_message = form.errors

    return render(
        request,
        'reset_password.html',
        {
            'form': form,
            'error_message': error_message,
        }
        )
